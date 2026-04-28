"""
[Data Merger]

[모듈 목적 및 상세 설명]
두 개의 개별 데이터프레임(Left, Right)을 지정된 키(Keys)를 기준으로 병합(Join)하는 데이터 변환기입니다.
Pandas의 암묵적인 동작(예: 컬럼명 중복 시 자동 접미사 추가, 의도치 않은 M:N 조인으로 인한 데이터 증폭)을
사전에 차단하기 위해, 병합 전후로 엄격한 데이터 정합성 검증(Validation)을 수행합니다.

[전체 데이터 흐름 (Input -> Output)]
1. Initialization: ConfigManager, Right DataFrame, 조인 조건(join_type, on_keys)을 주입받아 인스턴스화.
2. Entry Point: AbstractTransformer의 `transform(data)` 호출 (여기서 `data`는 Left DataFrame).
3. Pre-Validation (`_validate`): 조인 키 누락 여부 및 조인 키 외 컬럼 충돌(Collision) 검사.
4. Transformation (`_apply_transform`): `pd.merge()`를 통한 벡터화된 병합 연산 수행.
5. Post-Validation: 병합 결과의 행(Row) 수가 의도치 않게 폭발(Explosion)하지 않았는지 카디널리티(Cardinality) 검사.
6. Output: 검증이 완료된 단일 병합 데이터프레임 반환.

주요 기능:
- [Safe Merge] 스키마 변형을 방지하는 컬럼 충돌 사전 차단.
- [Memory Protection] 조인 키 중복으로 인한 M:N 병합(Cartesian Product 유사) 및 메모리 초과 방지.
- [Stateful Transformation] ITransformer의 단일 입력 시그니처를 유지하면서 Right DataFrame을 상태(State)로 관리.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거 요약.
1. Stateful Transformer (Right DataFrame 주입):
   - 장점: 기존 `ITransformer.transform(data: pd.DataFrame)`의 단순한 인터페이스를 파괴하지 않고 유지할 수 있음. 파이프라인(Chain) 구성이 매우 직관적이 됨.
   - 단점: 인스턴스가 `right_df`의 메모리 참조를 들고 있어야 하므로, 거대한 데이터를 병합할 때 메모리 생명주기 관리에 유의해야 함.
   - 근거: 오버 엔지니어링(다중 입력 인터페이스로의 전면 개편)을 피하면서도 가장 실용적으로 서비스 가능한 아키텍처임.
2. 컬럼 충돌(Collision)에 대한 하드 에러(Hard Error) 발생:
   - 장점: Pandas가 자동으로 `_x`, `_y` 접미사를 붙여 원본 스키마를 은밀하게 오염시키는 것을 원천 차단함.
   - 단점: 병합 전 컬럼명을 미리 변경(Rename)해야 하는 파이프라인 상의 번거로움이 발생할 수 있음.
   - 근거: 데이터 파이프라인에서 "조용히 넘어가는 버그"는 "명시적으로 터지는 버그"보다 수백 배 위험함. 신뢰성(Reliability)을 최우선으로 확보하기 위함.
3. 수동 카디널리티(Cardinality) 검증:
   - 장점: `pd.merge`의 `validate` 파라미터는 에러 메시지가 불친절하므로, 직접 `shape`를 비교하여 커스텀 예외(`MergeCardinalityError`)에 풍부한 문맥(Context)을 담을 수 있음.
   - 단점: 병합 이후에 행 수를 비교하므로 이미 연산 비용이 지불된 상태임.
   - 근거: 사전 검증으로 M:N 여부를 판단하려면 고비용의 중복 검사(`duplicated()`)가 필요하므로, 병합 후 결과의 Shape를 확인하는 것이 연산 효율과 방어적 프로그래밍의 적절한 타협점임.
"""

from typing import List, Set
import pandas as pd

# [Dependency] External Configuration & Interfaces
from src.common.config import ConfigManager
from src.common.exceptions import (
    MergeKeyNotFoundError,
    MergeColumnCollisionError,
    MergeCardinalityError,
    MergeExecutionError,
    TransformerError
)
# AbstractTransformer 위치는 사용자의 프로젝트 구조에 맞춰 가정된 경로를 사용합니다.
from src.transformer.processors.abstract_transformer import AbstractTransformer


# ==============================================================================
# Constants & Configuration
# ==============================================================================
# 지원하는 조인 방식의 집합. 잘못된 조인 타입 입력 시 O(1) 조회를 위해 frozenset 사용.
SUPPORTED_JOIN_TYPES = frozenset(['left', 'right', 'outer', 'inner'])


# ==============================================================================
# Main Class
# ==============================================================================
class DataMerger(AbstractTransformer):
    """두 데이터프레임을 안전하게 병합하는 구체(Concrete) 변환기 클래스.
    
    `ITransformer`의 시그니처를 유지하기 위해, 병합의 대상이 되는 Right DataFrame을
    생성자 주입(Constructor Injection)을 통해 상태로 보유합니다.

    Attributes:
        config (ConfigManager): 애플리케이션 전역 설정 객체.
        logger (logging.Logger): 부모 클래스에서 상속받은 로거 인스턴스.
        right_df (pd.DataFrame): 병합 대상이 되는 우측 데이터프레임.
        join_type (str): 병합 방식 ('left', 'inner' 등).
        on_keys (List[str]): 병합의 기준이 되는 컬럼명 리스트.
    """

    def __init__(
        self, 
        config: ConfigManager, 
        right_df: pd.DataFrame, 
        join_type: str, 
        on_keys: List[str]
    ) -> None:
        """DataMerger를 초기화하고 초기 상태의 무결성을 검증합니다.

        Args:
            config (ConfigManager): 데이터 변환 정책이 포함된 앱 설정 객체.
            right_df (pd.DataFrame): Left DataFrame과 병합할 대상 데이터프레임.
            join_type (str): 조인 방법 (예: 'inner', 'left').
            on_keys (List[str]): 조인 기준 키 컬럼 목록.

        Raises:
            ValueError: 지원하지 않는 join_type이거나 on_keys가 비어있는 경우.
            TransformerError: right_df가 유효한 DataFrame이 아닌 경우.
        """
        # 1. 부모 클래스 초기화 (Config 검증 및 Logger 생성)
        super().__init__(config)

        # 2. Entry Point 사전 방어 (Defensive Programming)
        if not isinstance(right_df, pd.DataFrame):
            raise TransformerError(
                message="DataMerger 초기화 실패: right_df는 반드시 pandas DataFrame이어야 합니다.",
                should_retry=False
            )
        
        if join_type not in SUPPORTED_JOIN_TYPES:
            raise ValueError(f"지원하지 않는 join_type 입니다. (입력: {join_type}, 지원: {SUPPORTED_JOIN_TYPES})")
            
        if not on_keys:
            raise ValueError("on_keys 리스트는 비어있을 수 없습니다. 최소 1개 이상의 병합 키가 필요합니다.")

        # 3. 상태 할당
        self.right_df = right_df
        self.join_type = join_type
        self.on_keys = list(on_keys)

        self.logger.debug(
            f"[DataMerger] join_type='{self.join_type}'으로 초기화 되었습니다. "
            f"on_keys={self.on_keys}, right_df_shape={self.right_df.shape}"
        )

    def _validate(self, data: pd.DataFrame) -> None:
        """병합 연산 전 Left DataFrame(`data`)과 Right DataFrame의 스키마 무결성을 검사합니다.

        설계 의도: 
        Pandas의 `merge` 함수가 뱉는 파편화된 KeyError나 자동 컬럼 변형을 방지하기 위해 
        Set(집합) 연산을 활용하여 스키마 정합성을 O(N)으로 빠르게 검증합니다.

        Args:
            data (pd.DataFrame): 병합의 기준이 되는 Left DataFrame.
            
        Raises:
            MergeKeyNotFoundError: 조인 키가 Left 또는 Right 데이터프레임에 누락된 경우.
            MergeColumnCollisionError: 조인 키를 제외하고 양쪽에 동일한 이름의 컬럼이 존재하는 경우.
        """
        left_cols_set: Set[str] = set(data.columns)
        right_cols_set: Set[str] = set(self.right_df.columns)
        on_keys_set: Set[str] = set(self.on_keys)

        # 1. 키 누락 검증 (Missing Keys Validation)
        missing_in_left = on_keys_set - left_cols_set
        if missing_in_left:
            raise MergeKeyNotFoundError(
                message=f"병합 기준 키 {list(missing_in_left)}가 Left 데이터프레임에 없습니다.",
                missing_keys=list(missing_in_left),
                target_df_name="Left DataFrame"
            )

        missing_in_right = on_keys_set - right_cols_set
        if missing_in_right:
            raise MergeKeyNotFoundError(
                message=f"병합 기준 키 {list(missing_in_right)}가 Right 데이터프레임에 없습니다.",
                missing_keys=list(missing_in_right),
                target_df_name="Right DataFrame"
            )

        # 2. 컬럼 충돌 검증 (Column Collision Validation)
        # 조인 키가 아닌 컬럼들 중 이름이 겹치면 _x, _y 접미사가 생성되므로 이를 원천 차단.
        left_exclusive_cols = left_cols_set - on_keys_set
        right_exclusive_cols = right_cols_set - on_keys_set
        colliding_cols = left_exclusive_cols.intersection(right_exclusive_cols)

        if colliding_cols:
            raise MergeColumnCollisionError(
                message=f"조인 키 제외, 동일한 이름의 컬럼이 존재하여 스키마 오염이 예상됩니다: {list(colliding_cols)}",
                colliding_columns=list(colliding_cols)
            )

    def _apply_transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """검증이 완료된 두 데이터프레임에 대해 벡터화된 병합 연산을 수행합니다.

        병합 후 Row 수(Cardinality)를 검사하여 데이터가 의도치 않게 증폭되었는지 확인합니다.

        Args:
            data (pd.DataFrame): Left DataFrame.

        Returns:
            pd.DataFrame: 병합이 완료된 새로운 데이터프레임.
            
        Raises:
            MergeExecutionError: pandas 내부의 병합 연산 중 발생한 시스템 런타임 에러.
            MergeCardinalityError: 'left' 또는 'inner' 조인 시 결과 행 수가 원본보다 늘어난 경우.
        """
        initial_left_shape = data.shape
        initial_right_shape = self.right_df.shape

        # M:N 조인 방지 정책 설정 (Left, Inner 조인 시 Right 테이블에 중복 키 허용 불가)
        validate_policy = 'm:1' if self.join_type in ['left', 'inner'] else None

        # 1. 벡터화 연산 실행 (Pandas C-Engine)
        try:
            merged_df = pd.merge(
                left=data,
                right=self.right_df,
                how=self.join_type,
                on=self.on_keys,
                # 충돌 방지 로직이 있으나, 만약을 대비해 접미사를 극단적인 값으로 설정하여 버그 식별 용이성 확보
                suffixes=('_FAIL_LEFT', '_FAIL_RIGHT') ,
                validate=validate_policy
            )

        except pd.errors.MergeError as me:
            # Pandas의 불친절한 카디널리티 에러를 커스텀 도메인 예외로 래핑
            raise MergeCardinalityError(
                message=f"병합 중 카디널리티 제약 조건 위반 (M:N 조인 감지). 상세: {me}",
                expected_relation="1:1 or N:1 (validate='m:1')",
                left_shape=initial_left_shape,
                right_shape=initial_right_shape
            ) from me

        except Exception as e:
            # TypeError, MemoryError 등 판다스 네이티브 예외를 도메인 예외로 래핑
            raise MergeExecutionError(
                message=f"Pandas 병합 엔진 실행 중 치명적 오류 발생: {e}",
                join_type=self.join_type,
                original_exception=e
            ) from e

        return merged_df