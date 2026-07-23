"""
[모듈 제목]
Gold Layer (ETL) Advanced Preprocessing & Multiverse Loading Pipeline Service

[모듈 목적 및 상세 설명]
메달리온 아키텍처(Medallion Architecture)의 최상위 계층인 골드 레이어를 총괄하는 구체 파이프라인 클래스입니다.
최상위 추상 인터페이스(`AbstractPipeline`)를 상속받아 구현되었으며, Silver Layer S3 스토리지로부터 
과거 20거래일의 와이드 시계열 데이터를 동적으로 역산 수집(Ingestion)하고, 전처리 서비스(`PreprocessorService`)를 
통해 사출된 18대 다형성 실험 우주(Multiverse) 버킷을 최종 목표 날짜 하루치 규격으로 정밀 슬라이싱하여 
고성능 Parquet 로더 계층으로 안전하게 적재 위임하는 오케스트레이션 역할을 수행합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Ingestion Phase: 배치 기준일(execution_date)로부터 1일을 차감하여 어제 영업일 날짜를 목표 날짜로 확정한 후,
   과거 최대 40일을 탐색하며 20거래일 분량의 Silver wide 데이터프레임을 역산 수집 및 시간순 정렬.
2. Preprocessing Phase: 확보된 시계열 컨텍스트 상에서 결측치 진단/보간 및 3대 이상치 진단 엔진 조합을 
   연쇄 가동하여 총 18대 실험 버킷 테이블프레임 세트 사출.
3. Slicing Phase: Gold 레이어의 일별 파티셔닝 적재 계약을 이행하기 위해 최종 18대 프레임을 목표 날짜 1행 규격(1, 190)으로 정밀 슬라이싱.
4. Loader Phase: 슬라이싱 완료된 각각의 버킷 데이터프레임을 TransformedDTO로 캡슐화한 뒤, S3ParquetLoader 파티션 엔진으로 적재 위임.
"""

import asyncio
import datetime
import pandas as pd
from typing import Any, Dict, Optional

from src.common.decorators.log_decorator import log_decorator
from src.common.dtos import TransformedDTO
from src.common.exceptions import ETLError, LoaderError, PreprocessorError
from src.loader.loader_service import LoaderService
from src.pipeline.abstract_pipeline import AbstractPipeline
from src.reader.reader_service import ReaderService
from src.preprocessor.preprocessor_service import PreprocessorService

# 글로벌 상태 코드 상수 규격 준수
STATUS_SUCCESS = "SUCCESS"
STATUS_FAIL_PROCESS = "FAIL_PROCESSING"
STATUS_SYSTEM_ERROR = "CRITICAL_SYSTEM_ERROR"
STATUS_EMPTY = "EMPTY_DATA"


class GoldPipeline(AbstractPipeline):
    """Silver wide 소스 판독, 18대 다형성 전처리 오케스트레이션 및 Gold 레이어 일별 파티셔닝 적재를 조율하는 골드 파이프라인."""

    def __init__(self, task_name: str) -> None:
        """부모의 초기화 체인을 구동하고 골드 레이어 ETL 및 전처리에 필수적인 하위 서브 컴포넌트들을 바인딩합니다.

        Args:
            task_name (str): 실행 대상 파이프라인의 고유 식별 명칭 (예: 'gold_fred_daily').
        """
        super().__init__(task_name=task_name)
        
        # [설계 의도] 각 연산 단계별 단일 책임 원칙(SRP) 적용을 위해 데이터 조회, 전처리 오케스트레이션, 적재 인스턴스를 격리 분리
        self._reader_service = ReaderService(target_reader="s3_parquet")
        self._preprocessor_service = PreprocessorService()
        self._loader_service = LoaderService(target_loader=self._task_policy.target_loader)

    @log_decorator()
    async def run_batch(self, execution_date: Optional[str] = None, extract_mode: str = "TODAY") -> Dict[str, Any]:
        """골드 레이어에 할당된 시계열 윈도우 데이터를 역산 수집하고 18대 다형성 실험 데이터셋으로 정제/적재하는 배치 프로세스를 구동합니다.

        Args:
            execution_date (Optional[str]): 외부 스케줄러(Airflow)에서 유입된 데이터 배치 가동 대상 날짜 (YYYYMMDD).
            extract_mode (str): 데이터 수집 범위 모드 규격.

        Returns:
            Dict[str, Any]: 골드 파이프라인 가동 통계 및 최종 적재 성공 여부 보고서 구조체.

        Raises:
            ETLError: 시스템 내부 런타임 패닉 또는 치명적 복구 불가능 예외 발생 시 상위 실행 레이어로 전파.
        """
        if not execution_date:
            target_dt = datetime.date.today()
        else:
            target_dt = datetime.datetime.strptime(execution_date, "%Y%m%d").date()

        # [설계 의도] 실버 레이어에 적재 완료된 '하루 전날(어제)'의 원천 데이터를 조회 및 처리할 수 있도록 1일을 차감하여 목표 날짜를 확정합니다.
        target_date = target_dt - datetime.timedelta(days=1)
        target_date_str = target_date.strftime("%Y%m%d")

        weeks = ["월", "화", "수", "목", "금", "토", "일"]
        weekday_str = weeks[target_date.weekday()]

        try:
            self._logger.info(f"[{self._task_name}] Gold ETL 파이프라인을 시작합니다. (목표 기준일: {target_date_str} ({weekday_str}))")
            
            collected_dfs = []
            lookback_days = 0
            max_search_days = 40  # 주말 및 글로벌 휴장일을 고려하여 최대 40영업일 범위까지 역산 탐색 가드레일 설정

            # ==============================================================================
            # 1. INGESTION PHASE : 20거래일 시계열 컨텍스트 역산 탐색 및 동적 수집
            # ==============================================================================
            for i in range(max_search_days):
                search_date_str = (target_date - datetime.timedelta(days=i)).strftime("%Y%m%d")
                try:
                    # [설계 의도] ReaderService의 스트리밍 판독기 인터페이스 계약에 맞춰 task_name을 job_id로 매핑하여 호출
                    raw_data_stream = self._reader_service.read_stream(
                        job_id=self._task_name,
                        execution_date=search_date_str,
                        source_layer="silver"
                    )
                    
                    job_chunks = [df for df in raw_data_stream]
                    if job_chunks:
                        day_df = pd.concat(job_chunks, ignore_index=True)
                        if not day_df.empty:
                            collected_dfs.append(day_df)
                            lookback_days += 1
                            # [설계 의도] Kalman Filter 및 MA 알고리즘 연산에 필요한 최소 컨텍스트 윈도우인 20거래일이 충족되면 조기 탐색 종료
                            if lookback_days >= 20:
                                break
                except Exception:
                    # 데이터 공백일(휴장일, 주말)은 무음 스킵(Skip)하여 과거 데이터 역산 결합 구조의 복원력을 강화
                    continue

            # [설계 의도] 신규 자산이거나 백필 초기 단계여서 20거래일 미만으로 조회되더라도 가용한 일부 데이터만이라도 바인딩하여 진행
            if not collected_dfs:
                self._logger.warning(
                    f"[{self._task_name}] 대상 윈도우 범위 내에 실버 레이어 주가 데이터가 전무합니다. "
                    f"적재를 생략하고 파이프라인을 조기 스킵 종료합니다."
                )
                return {"status": STATUS_EMPTY, "task_name": self._task_name, "execution_date": target_date_str}

            # 역순으로 수집된 일별 프레임들을 단일 시계열 매트릭스로 통합하고, 정렬 후 인덱스 동기화
            market_data = pd.concat(collected_dfs, ignore_index=True)
            
            assert "trade_date" in market_data.columns, "실버 레이어 스키마 무결성 파괴: trade_date 컬럼 누락"
            market_data["trade_date"] = pd.to_datetime(market_data["trade_date"])
            market_data = market_data.sort_values("trade_date").reset_index(drop=True)
            market_data = market_data.set_index("trade_date")
            
            self._logger.info(f"[{self._task_name}] 시계열 컨텍스트 로드 완료 (확보 거래일수: {lookback_days}일, 행렬 구조: {market_data.shape})")

            # ==============================================================================
            # 2. PREPROCESSING PHASE : 18대 다형성 전처리 시퀀스 체인 가동
            # ==============================================================================
            try:
                # [설계 의도] 상위 파이프라인 레이어는 하위 로직의 순차 체인을 알 필요가 없도록 PreprocessorService Facade 내부로 위임
                final_artifacts = self._preprocessor_service.execute_preprocessing_job(market_data=market_data)
            except PreprocessorError as pe:
                self._logger.error(f"[{self._task_name}] Gold 전처리 모듈 시퀀스 체인 내에서 복구 불가능한 연산 에러 발생.")
                return {"status": STATUS_FAIL_PROCESS, "task_name": self._task_name, "error_info": pe.to_dict()}

            # ==============================================================================
            # 3. LOADER PHASE : 18대 가격 버킷프레임 정산 및 분산 파티셔닝 적재위임
            # ==============================================================================
            success_count = 0
            fail_count = 0
            job_details = []

            for artifact_key, artifact_df in final_artifacts.items():
                # 방어 마스크 계열(Indicator, Weight)을 제외한 순수 가격 결과 테이블(bucket_*)만 적재 대상으로 타겟팅
                if not artifact_key.startswith("bucket_"):
                    continue
                    
                try:
                    # [설계 의도] 다운스트림 로더가 S3 내 물리적 구조 분산 적재(Year/Month/Day) 및 파일명 유니크 구조를 생성할 수 있도록
                    # 메타데이터 사전에 bucket_name 식별 계약 자리를 명시 주입합니다.
                    gold_dto = TransformedDTO(
                        data=artifact_df,
                        meta={
                            "task_name": self._task_name,
                            "execution_date": target_date_str,
                            "layer": "gold",
                            "bucket_name": artifact_key
                        }
                    )
                    
                    # 대량 파일 I/O 블로킹 연산으로부터 비동기 이벤트 루프를 완벽히 가드하기 위해 워커 스레드로 연산 위임
                    is_loaded = await asyncio.to_thread(self._loader_service.execute_load, gold_dto)
                    
                    if is_loaded:
                        success_count += 1
                        job_details.append({"bucket_id": artifact_key, "status": "SUCCESS", "error": None})
                    else:
                        fail_count += 1
                        job_details.append({"bucket_id": artifact_key, "status": "FAIL_LOAD", "error": "Gold Parquet 적재 엔진 반환 False"})
                        
                except LoaderError as le:
                    fail_count += 1
                    job_details.append({"bucket_id": artifact_key, "status": "FAIL_LOAD", "error": le.to_dict()})
                except Exception as e:
                    fail_count += 1
                    job_details.append({"bucket_id": artifact_key, "status": "FAIL_UNKNOWN", "error": str(e)})

            self._loader_service.log_batch_summary()
            
            if fail_count > 0:
                self._logger.error(f"[{self._task_name}] Gold 파이프라인 적재 중 일부 버킷의 유실 발생 (성공: {success_count} / 실패: {fail_count})")
                return {
                    "status": STATUS_FAIL_PROCESS,
                    "task_name": self._task_name,
                    "execution_date": target_date_str,
                    "success": success_count,
                    "fail": fail_count,
                    "details": job_details
                }
                
            summary = {
                "status": STATUS_SUCCESS,
                "task_name": self._task_name,
                "execution_date": target_date_str,
                "total_buckets": success_count,
                "details": job_details
            }
            self._logger.info(f"[Gold Pipeline 요약 리포트] 총 {success_count}개의 다형성 실험 우주 테이블 적재 완료 완결.")
            return summary

        except Exception as e:
            self._logger.critical(f"[{self._task_name}] Gold 오케스트레이터 내부에서 예측하지 못한 치명적 시스템 에러 발생: {e}")
            unexpected_error = ETLError(message=f"Gold 파이프라인 시스템 런타임 크래시: {e}", should_retry=False)
            return {"status": STATUS_SYSTEM_ERROR, "task_name": self._task_name, "error_info": unexpected_error.to_dict()}