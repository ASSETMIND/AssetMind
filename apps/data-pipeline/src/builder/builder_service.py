"""
[모듈 제목]
Data Pipeline Builder Service Module

[모듈 목적 및 상세 설명]
Silver 데이터 파이프라인의 최종 단계인 병합(Merger) 연산을 캡슐화하는 파사드(Facade) 서비스 계층입니다.
순수 연산 함수인 병합 로직을 감싸 상위 오케스트레이터가 일관된 추상화 수준에서 통신할 수 있도록 지원하며,
사전 검증(Pre-condition)과 메모리 및 예외 관리(Error Handling)를 중앙에서 통제합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: TransformerService를 통과한 N개의 데이터프레임 리스트와 각 데이터프레임의 식별자(Job IDs).
2. Validation: 데이터프레임 존재 여부, 식별자 리스트와의 길이 일치 여부 등 정합성 사전 검증.
3. Execution: 내부 병합 모듈(merger.py)의 순수 함수를 호출하여 고속 가로 병합 수행.
4. Output: 병합 연산 중 발생한 예외를 시스템 규격에 맞게 래핑하거나, 성공 시 단일 Wide DataFrame 반환.

주요 기능:
- [Facade Interface] 상위 제어기가 내부 병합 알고리즘(Pandas, Polars 등)을 몰라도 되도록 캡슐화.
- [Pre-condition Validation] 병합 연산(CPU/Memory Intensive) 전 인풋 데이터의 무결성을 검증하여 불필요한 OOM 및 연산 낭비 차단.
- [Exception Translation] 하위 모듈의 네이티브 에러(KeyError, InvalidIndexError 등)를 파이프라인 표준 예외로 번역(Translation).

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약. 반드시 모든 코드 내용을 작성. 가혹할정도로 코드를 재확인하면서 작성.
1. 순수 연산 모듈(merger)과 서비스 계층(BuilderService)의 분리:
   - 장점: 파이프라인 제어기(Controller)의 코드가 얇아지고(Thin), Reader/Transformer와 동일한 추상화 수준(Service)을 유지하여 아키텍처의 일관성이 극대화됨. 향후 엔진(Pandas -> Polars/PySpark) 교체 시 상위 오케스트레이터 코드 수정이 불필요함.
   - 단점: 단순히 함수 하나를 호출하기 위해 클래스(Boilerplate)를 하나 더 거쳐야 하므로, 극미한 수준의 함수 호출 오버헤드가 발생함.
   - 근거: 엔터프라이즈 데이터 파이프라인에서는 마이크로초 단위의 성능 최적화보다 유지보수성과 인터페이스 일관성(OCP 준수)이 시스템의 장기적인 안정성에 압도적으로 기여하므로 이 계층 분리를 강제함.
2. 예외 래핑(Exception Wrapping) 및 로깅의 중앙화:
   - 장점: 연산 중 발생하는 저수준의 에러(Pandas Error)를 비즈니스 도메인 에러(BuilderError)로 감싸서(Wrap) 상위로 던짐으로써, 오케스트레이터가 예외를 우아하게 처리할 수 있게 함.
   - 단점: 에러 스택 트레이스(Stack Trace)가 한 뎁스(Depth) 깊어짐.
   - 근거: 파이프라인 붕괴 시 하위 모듈에서 날것의 에러가 터져 나오는 것보다, 에러의 발생 지점(Builder)을 정확히 명시하는 것이 빠른 트러블슈팅에 유리하므로 방어적 프로그래밍을 적용함.
"""

from typing import List
import pandas as pd

from src.common.exceptions import BuilderError, BuilderServiceError
from src.common.log import LogManager
from src.common.decorators.log_decorator import log_decorator

from src.builder.processors.merger import build_wide_table


class BuilderService:
    """Silver 데이터 병합(Builder) 파이프라인의 생명주기를 총괄하는 서비스 클래스."""

    def __init__(self) -> None:
        """BuilderService 초기화 및 로거 인스턴스 할당."""
        self._logger = LogManager.get_logger(self.__class__.__name__)

    @log_decorator(logger_name="BuilderService")
    def execute_build(self, dfs: List[pd.DataFrame], job_ids: List[str], merge_key: str) -> pd.DataFrame:
        """검증된 다수의 DataFrame을 단일 Wide Table로 병합합니다.

        Args:
            dfs (List[pd.DataFrame]): 변환이 완료된 데이터프레임 리스트.
            job_ids (List[str]): 각 데이터프레임의 출처를 식별하는 Job ID 리스트.
            merge_key (str): 병합의 기준이 되는 컬럼명 (예: 'trade_date').

        Returns:
            pd.DataFrame: 병합이 완료된 단일 와이드 데이터프레임.

        Raises:
            BuilderError: 입력 데이터 검증 실패 또는 병합 중 시스템 에러 발생 시.
        """
        self._logger.info(f"[{len(job_ids)}개 지표] Wide Table 병합 작업을 시작합니다. (Key: {merge_key})")

        # 1. 사전 검증 (Pre-condition Validation)
        if not dfs or not job_ids:
            self._logger.warning("병합할 데이터프레임 또는 Job ID 리스트가 비어있습니다. 빈 데이터프레임을 반환합니다.")
            return pd.DataFrame()

        if len(dfs) != len(job_ids):
            raise BuilderServiceError(
                message=f"데이터프레임 개수({len(dfs)})와 Job ID 개수({len(job_ids)})가 불일치합니다."
            )

        # 2. 본 연산 실행 (Execution)
        try:
            wide_df = build_wide_table(dfs=dfs, job_ids=job_ids, merge_key=merge_key)
            
            if wide_df.empty:
                self._logger.warning("병합 연산은 성공했으나, 결과 데이터프레임이 비어있습니다.")
            else:
                self._logger.info(f"병합 완료: {wide_df.shape[0]} Rows x {wide_df.shape[1]} Cols")
                
            return wide_df
            
        except BuilderError as be:
            raise be
        except Exception as e:
            raise BuilderServiceError(
                message=f"병합 연산 중 예기치 않은 오류 발생: {e}", 
                original_exception=e
            ) from e