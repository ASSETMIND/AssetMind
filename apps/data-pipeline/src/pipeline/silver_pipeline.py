"""
[모듈 제목]
Silver Layer (ETL) Reading, Transforming & Building Pipeline Service

[모듈 목적 및 상세 설명]
메달리온 아키텍처의 중간 계층인 실버 레이어를 총괄하는 구체 파이프라인 클래스입니다.
추상 인터페이스(`AbstractPipeline`)를 상속받아 내부 S3(Bronze)로부터 대량의 원천 데이터를 안전하게 읽어오는 읽기 단계(Reader),
각 도메인 테이블의 변수 타입 및 정적 스키마 무결성을 정제하는 변환 단계(Transformer), 
정제된 복수의 테이블을 분석 최적화 형태로 병합 및 조인하는 빌드 단계(Builder)를 순차적으로 오케스트레이션하여 
최종적으로 고성능 Parquet 로더 계층으로 위임합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Reader Phase: 설정에 지정된 Job ID 목록을 기반으로 Bronze S3 버킷에서 원천 파일 바이너리 로드.
2. Transformer Phase: 텍스트/JSON 포맷의 데이터를 Pandas DataFrame으로 변환 후 컬럼 타입(DateTime, Float 등) 캐스팅 및 정제.
3. Builder Phase: 비즈니스 키 기반으로 다중 테이블 컬럼을 와이드 데이터프레임(Wide DataFrame) 형태로 결합(Merge).
4. Loader Phase: 최종 결합된 데이터셋을 TransformedDTO에 캡슐화하여 S3ParquetLoader로 분산 파티셔닝 적재 위임.

주요 기능:
- [Staged ETL Pipeline] 단계별 격리 구조를 통한 연산 책임 분리 및 가시성(Observability) 확보.
- [Schema Standardization] 데이터 타입 및 누락값 정제를 통한 실버 데이터 레이크 무결성 보장.
- [Wide-Table Synthesis] 다운스트림(ML 모델 및 BI 대시보드) 분석 속도 극대화를 위한 디노멀라이제이션(Denormalization).

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 인메모리 일괄 변환(Staged Dataframe) vs 스트리밍 파이프라인:
  - 장점: Reader, Transformer, Builder 계층 간 데이터 전달 매개체가 Pandas DataFrame으로 단일화되어 디버깅이 직관적이며 조인(Join) 연산의 메모리 지역성 성능이 극대화됨.
  - 단점: 대규모 시계열 배치 데이터 처리 시 컨테이너의 순간 메모리 점유율(Memory Peak)이 상승할 수 있음.
  - 근거: 실버 레이어의 데이터 변환 특성상 테이블 간의 유기적인 조인과 시계열 윈도우 연산이 필수적입니다. Chunk 단위 스트리밍은 복잡한 다중 조인 구현을 극도로 어렵게 만들고 I/O 병목을 유발하므로, 인메모리 벡터 연산(Pandas)을 채택하여 연산 속도를 확보하는 대신 인프라 사양을 맞추는 스케일업 전략이 압도적으로 유리합니다.
"""

import asyncio
import datetime
import pandas as pd
from typing import Any, Dict, Optional

from src.common.decorators.log_decorator import log_decorator
from src.common.dtos import TransformedDTO
from src.common.exceptions import ETLError, LoaderError, TransformerError
from src.loader.loader_service import LoaderService
from src.pipeline.abstract_pipeline import AbstractPipeline

from src.reader.reader_service import ReaderService
from src.transformer.transformer_service import TransformerService
from src.builder.builder_service import BuilderService

# 글로벌 상태 코드 규격 준수
STATUS_SUCCESS = "SUCCESS"
STATUS_FAIL_PROCESS = "FAIL_PROCESSING"
STATUS_SYSTEM_ERROR = "CRITICAL_SYSTEM_ERROR"
STATUS_EMPTY = "EMPTY_JOBS"


class SilverPipeline(AbstractPipeline):
    """S3 Bronze 소스 판독, 데이터 스키마 표준화, 광역 테이블 병합 및 Parquet 적재를 조율하는 실버 파이프라인 오케스트레이터."""

    def __init__(self, task_name: str) -> None:
        """부모의 초기화 체인을 구동하고 실버 레이어 ETL에 필수적인 하위 서브 컴포넌트들을 바인딩합니다."""
        super().__init__(task_name=task_name)
        
        # [설계 의도] 각 연산 단계별 단일 책임 원칙(SRP) 적용을 위한 인스턴스 격리 생성
        self._reader_service = ReaderService(target_reader="s3_zstd")
        self._transformer_service = TransformerService()
        self._builder_service = BuilderService()
        self._loader_service = LoaderService(target_loader=self._task_policy.target_loader)

    @log_decorator()
    async def run_batch(self, execution_date: Optional[str] = None, extract_mode: str = "TODAY") -> Dict[str, Any]:
        """실버 레이어에 할당된 다중 원천 테이블을 읽어오고 대량의 정형 데이터셋으로 변환/적재하는 배치 프로세스를 구동합니다.

        Args:
            execution_date (Optional[str]): 외부 스케줄러(Airflow)에서 유입된 데이터 대상 날짜.
            extract_mode (str): 추출 모드 규격.

        Returns:
            Dict[str, Any]: 실버 파이프라인 가동 통계 및 최종 성공 여부 보고서 구조체.
        """
        job_ids = self._task_policy.extract_jobs
        if not job_ids:
            return {"status": STATUS_EMPTY, "total": 0, "success": 0, "fail": 0, "details": []}

        if not execution_date:
            execution_date = datetime.now().strftime("%Y%m%d")

        try:
            if not execution_date:
                execution_date = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")

            self._logger.info(f"[{self._task_name}] Silver ETL 파이프라인을 시작합니다. (기준일: {execution_date})")

            # 개별 Job ID 순회 및 Chunk 단위 DataFrame 병합 프로세스 구축 
            transformed_dfs = []
            success_count = 0
            skip_count = 0
            fail_count = 0
            job_details = []

            # 설정에 지정된 Job ID 목록(List[str])을 순회하며 개별 스토리지 I/O 및 변환 가동
            for job_id in self._task_policy.extract_jobs:
                job_chunks = []
                try:
                    # 1. Reader: 파라미터 구조 계약조건에 일치하도록 단일 job_id와 execution_date를 정확히 인계
                    raw_data_stream = self._reader_service.read_stream(
                        job_id=job_id,
                        execution_date=execution_date,
                        source_layer="bronze"
                    )

                    # 2. Transformer: Reader가 반환한 제너레이터 스트림을 통째로 위임하여 가공 파이프라인 스트림을 형성
                    transformed_stream = self._transformer_service.transform_stream(
                        job_id=job_id,
                        data_stream=raw_data_stream
                    )
                    
                    # 3. Execution: 변환이 완료되어 순차적으로 Yield되는 정제 DataFrame 청크들을 수집
                    for df in transformed_stream:
                        job_chunks.append(df)
                    
                    # 하나의 Job에서 파생된 복수의 청크 DataFrame을 단일 도메인 테이블로 수렴 결합
                    if job_chunks:
                        job_df = pd.concat(job_chunks, ignore_index=True)
                    else:
                        job_df = pd.DataFrame()

                    if job_df.empty:
                        status = "SKIPPED_EMPTY"
                        reason = "입력 데이터프레임이 완전히 비어 있습니다. (과거 백필 공백 또는 휴장일)"
                        skip_count += 1
                        job_details.append({"job_id": job_id, "status": status, "reason": reason})
                    elif "trade_date" not in job_df.columns:
                        status = "SKIPPED_MISSING_KEY"
                        reason = f"필수 조인 키('trade_date')가 스키마 변환 후 유실되었습니다. (보유 컬럼: {list(job_df.columns)})"
                        skip_count += 1
                        job_details.append({"job_id": job_id, "status": status, "reason": reason})
                        # 다운스트림 빌더 계층의 조인 연산 크래시를 방지하기 위해 안전한 빈 구조체로 대체
                        job_df = pd.DataFrame()
                    else:
                        status = "SUCCESS"
                        success_count += 1
                        job_details.append({"job_id": job_id, "status": status, "reason": None})
                        
                except TransformerError as te:
                    status = "FAIL_TRANSFORM"
                    fail_count += 1
                    job_details.append({"job_id": job_id, "status": status, "reason": str(te.message)})
                    job_df = pd.DataFrame()
                except Exception as e:
                    status = "FAIL_UNKNOWN"
                    fail_count += 1
                    job_details.append({"job_id": job_id, "status": status, "reason": str(e)})
                    job_df = pd.DataFrame()
                    
                transformed_dfs.append(job_df)

            self._reader_service.log_batch_summary()
            self._transformer_service.log_batch_summary()

            # 3. Builder: 비즈니스 키 기반으로 다중 테이블 컬럼을 와이드 데이터프레임(Wide DataFrame) 형태로 결합(Merge).
            final_df = self._builder_service.execute_build(
                transformed_dfs, self._task_policy.extract_jobs, "trade_date"
            )

            if final_df.empty:
                self._logger.warning(
                    f"[{self._task_name}] 해당 실행일자({execution_date})에 병합된 금융 지표 데이터가 없습니다. "
                    f"(글로벌 휴장일 또는 데이터 수집 공백) 적재를 생략하고 파이프라인을 정상 완료합니다."
                )
                return {
                    "status": STATUS_SUCCESS,
                    "task_name": self._task_name,
                    "execution_date": execution_date,
                    "error_info": None
                }

            final_df = final_df.copy()

            final_df["year"] = final_df["trade_date"].astype(str).str[0:4]
            final_df["month"] = final_df["trade_date"].astype(str).str[4:6]
            final_df["day"] = final_df["trade_date"].astype(str).str[6:8]

            # 4. Loader: 최종 결합된 데이터셋을 TransformedDTO에 캡슐화하여 S3ParquetLoader로 분산 파티셔닝 적재 위임.
            transformed_dto = TransformedDTO(
                data=final_df,
                meta={
                    "task_name": self._task_name,
                    "execution_date": execution_date,
                    "layer": "silver"
                }
            )

            is_loaded = await asyncio.to_thread(self._loader_service.execute_load, transformed_dto)
            
            if is_loaded:
                # [설계 의도] 브론즈 규격과 완벽히 통일된 형태의 정산 요약본 생성 및 요약 로깅 수행
                summary = {
                    "status": STATUS_SUCCESS,
                    "task_name": self._task_name,
                    "execution_date": execution_date,
                    "total_jobs": len(job_ids),
                    "success_jobs": success_count,
                    "skip_jobs": skip_count,
                    "fail_jobs": fail_count,
                    "details": job_details
                }
                self._logger.info(
                    f"실버 파이프라인 가동 완료 - 총 {len(job_ids)}건 중 "
                    f"[성공: {success_count}건 / 스킵: {skip_count}건 / 실패: {fail_count}건]"
                )
                for detail in job_details:
                    if detail["status"] in ["SKIPPED_EMPTY", "SKIPPED_MISSING_KEY"]:
                        self._logger.warning(
                            f"데이터 스킵 대상 Job ID: {detail['job_id']} | 사유: {detail['reason']}"
                        )
                return summary
            else:
                raise LoaderError("S3 Parquet 적재 엔진이 최종 실패(False)를 반환했습니다.")

        except TransformerError as te:
            self._logger.error(f"[{self._task_name}] Silver 트랜스포머 단계에서 복구 불가능한 연산 에러 발생.")
            return {"status": STATUS_FAIL_PROCESS, "task_name": self._task_name, "error_info": te.to_dict()}
            
        except LoaderError as le:
            self._logger.error(f"[{self._task_name}] Silver 파이프라인 물리 스토리지 적재 실패.")
            return {"status": STATUS_FAIL_PROCESS, "task_name": self._task_name, "error_info": le.to_dict()}
            
        except Exception as e:
            self._logger.critical(f"[{self._task_name}] Silver 오케스트레이터 내부에서 예측하지 못한 치명적 시스템 에러 발생: {e}")
            unexpected_error = ETLError(message=f"Silver 파이프라인 시스템 런타임 크래시: {e}", should_retry=False)
            return {"status": STATUS_SYSTEM_ERROR, "task_name": self._task_name, "error_info": unexpected_error.to_dict()}