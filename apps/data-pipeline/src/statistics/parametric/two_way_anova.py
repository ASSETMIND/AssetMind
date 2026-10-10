from typing import Any, Dict, List, Literal, Tuple, Union
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.formula.api import ols

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_SIGNIFICANCE_LEVEL: float = 0.05                # 귀무가설(H0) 기각 판단 유의수준 (alpha)
SUPPORTED_ANOVA_METHODS: Tuple[str, ...] = ("rcbd",)    # 지원 알고리즘 패밀리 (확장 등록 가능)
DEFAULT_ANOVA_TYPE: int = 2                             # 주효과 검정을 위한 기본 분산분석 제곱합 유형 (Type-II SS)
MINIMUM_SAMPLE_SIZE: int = 4                            # 분산분석 수행을 위한 최소 관측치 수


# ==============================================================================
# Public API Functions
# ==============================================================================

def block_two_way_anova(
    response_values: Union[np.ndarray, pd.Series, list],
    block_factors: Union[np.ndarray, pd.Series, list],
    treatment_factors: Union[np.ndarray, pd.Series, list, Dict[str, Any], pd.DataFrame],
    method: Literal["rcbd"] = None,
    significance_level: float = DEFAULT_SIGNIFICANCE_LEVEL,
    anova_type: int = DEFAULT_ANOVA_TYPE
) -> Dict[str, Any]:
    """블록 요인을 통제한 이원배치 분산분석(Block Two-Way ANOVA)을 수행합니다.

    설계 실험계획법(RCBD) 원리에 따라 환경 블록(예: 시장 국면/Fold) 변동성을 통제하고,
    단일 또는 다중 전처리 요인(예: Impute, Detect, Refine)의 주효과 유의성을 검정합니다.

    Args:
        response_values: 연속형 반응 변수 관측치 시퀀스 (예: Composite Score).
        block_factors: 통제 대상인 블록 범주 관측치 시퀀스 (예: Fold ID).
        treatment_factors: 주 검정 대상 처리 요인 시퀀스, 딕셔너리, 또는 데이터프레임.
        method: 실행할 분산분석 알고리즘 (기본값: 'rcbd').
        significance_level: 가설 검정 유의수준 (기본값: 0.05).
        anova_type: 제곱합(Sum of Squares) 계산 유형 (기본값: 2 = Type-II SS).

    Returns:
        Dict[str, Any]:
            - anova_table: 표준 분산분석표 (pd.DataFrame).
            - treatment_p_value: 처리 요인의 최저 유의확률.
            - block_p_value: 블록 요인(시장 국면)의 유의확률.
            - is_treatment_significant: 처리 주효과의 통계적 유의성 여부 (p < alpha).
            - is_block_significant: 블록 효과의 통계적 유의성 여부 (p < alpha).
            - factor_p_values: 요인별 유의확률 딕셔너리.
            - method: 실행된 알고리즘 명칭.

    Raises:
        ValueError: 지원하지 않는 method가 입력되거나 배열 크기가 불일치할 경우 발생.
    """
    # 1. 분산분석 알고리즘 유효성 검증
    _validate_anova_method(method=method)

    # 2. 처리 요인 형태 표준화
    standardized_treatments: Dict[str, np.ndarray] = _standardize_treatment_factors(
        treatment_factors=treatment_factors
    )

    # 3. 유효 관측치 결측 제거 필터링
    clean_y, clean_blocks, clean_treatments = _filter_finite_observations(
        response_values=response_values,
        block_factors=block_factors,
        treatment_dict=standardized_treatments
    )

    # 4. 분산분석 최소 표본 크기 검증
    _validate_sample_size(clean_y=clean_y)

    # 5. OLS 회귀 모형 적합용 데이터프레임 및 포뮬러 조립
    analysis_frame, formula_string, factor_names = _construct_ols_payload(
        clean_y=clean_y,
        clean_blocks=clean_blocks,
        clean_treatments=clean_treatments
    )

    # 6. statsmodels OLS 회귀 모형 적합
    fitted_ols = _fit_ols_model(
        analysis_frame=analysis_frame,
        formula_string=formula_string
    )

    # 7. anova_type에 맞는 제곱합 분산분석표(ANOVA Table) 산출
    anova_table = _calculate_anova_table(
        fitted_ols=fitted_ols,
        anova_type=anova_type
    )

    # 8. 요인별 유의확률 파싱 및 주효과 추출
    factor_p_values, block_p_value = _extract_factor_p_values(
        anova_table=anova_table,
        factor_names=factor_names
    )

    # 9. 최종 검정 결과 번들 패키징 및 반환
    return _build_final_anova_result(
        anova_table=anova_table,
        factor_p_values=factor_p_values,
        block_p_value=block_p_value,
        significance_level=significance_level,
        method=method
    )


# ==============================================================================
# Internal Helper Functions
# ==============================================================================

def _validate_anova_method(method: str) -> None:
    """지정된 분산분석 알고리즘의 지원 여부를 검증합니다."""
    if method not in SUPPORTED_ANOVA_METHODS:
        raise ValueError(
            f"지원하지 않는 분산분석 알고리즘입니다: '{method}'. "
            f"지원 알고리즘 목록: {SUPPORTED_ANOVA_METHODS}"
        )


def _standardize_treatment_factors(
    treatment_factors: Union[np.ndarray, pd.Series, list, Dict[str, Any], pd.DataFrame]
) -> Dict[str, np.ndarray]:
    """다양한 형태의 처리 요인 입력을 {요인명: 1차원배열} 딕셔너리 규격으로 변환합니다."""
    treatment_dict: Dict[str, np.ndarray] = {}

    # 1. DataFrame 입력: 각 컬럼명을 키로 하여 개별 1차원 배열 추출
    if isinstance(treatment_factors, pd.DataFrame):
        for col_name in treatment_factors.columns:
            treatment_dict[str(col_name)] = treatment_factors[col_name].to_numpy()

    # 2. Dict 입력: 각 요인별 값을 1차원 C-연속성 float/배열로 평탄화
    elif isinstance(treatment_factors, dict):
        for key, val in treatment_factors.items():
            treatment_dict[str(key)] = np.ascontiguousarray(val).flatten()

    # 3. 단일 시퀀스/배열 입력: 기본 단일 요인('Treatment') 키로 패키징
    else:
        treatment_dict["Treatment"] = np.ascontiguousarray(treatment_factors).flatten()

    return treatment_dict


def _filter_finite_observations(
    response_values: Union[np.ndarray, pd.Series, list],
    block_factors: Union[np.ndarray, pd.Series, list],
    treatment_dict: Dict[str, np.ndarray]
) -> Tuple[np.ndarray, np.ndarray, Dict[str, np.ndarray]]:
    """배열 길이 정합성을 검증하고 결측치(NaN/Inf)를 배제한 유효 관측치 세트를 반환합니다."""
    # 1. 반응 변수와 블록 요인을 1차원 float64 및 1차원 배열로 표준화
    y_array: np.ndarray = np.ascontiguousarray(response_values, dtype=np.float64).flatten()
    block_array: np.ndarray = np.ascontiguousarray(block_factors).flatten()
    sample_size: int = len(y_array)

    # 2. 블록 요인 및 각 처리 요인별 관측치 길이의 상호 일치 여부 검증
    if len(block_array) != sample_size:
        raise ValueError(f"반응 변수와 블록 요인의 길이가 일치하지 않습니다: {sample_size} != {len(block_array)}")

    for factor_name, factor_arr in treatment_dict.items():
        if len(factor_arr) != sample_size:
            raise ValueError(f"처리 요인 '{factor_name}'의 길이가 일치하지 않습니다: {len(factor_arr)} != {sample_size}")

    # 3. 반응 변수 기준 결측치(NaN) 및 무한대(Inf) 배제 마스크 생성
    finite_mask: np.ndarray = np.isfinite(y_array)

    # 4. 동일 인덱스 마스크를 일괄 적용하여 결측이 제거된 유효 관측치 세트 사출
    clean_y = y_array[finite_mask]
    clean_blocks = block_array[finite_mask]
    clean_treatments = {k: v[finite_mask] for k, v in treatment_dict.items()}

    return clean_y, clean_blocks, clean_treatments


def _validate_sample_size(clean_y: np.ndarray) -> None:
    """정제된 반응 변수의 크기가 분산분석 최소 요구 표본 수를 충족하는지 검증합니다."""
    if len(clean_y) < MINIMUM_SAMPLE_SIZE:
        raise ValueError(f"유효 관측치 수가 분산분석 최소 요구치({MINIMUM_SAMPLE_SIZE}) 미만입니다: {len(clean_y)}")


def _construct_ols_payload(
    clean_y: np.ndarray,
    clean_blocks: np.ndarray,
    clean_treatments: Dict[str, np.ndarray]
) -> Tuple[pd.DataFrame, str, List[str]]:
    """statsmodels 회귀 포뮬러 및 OLS 입력 프레임을 조립합니다."""
    # 1. 반응 변수와 블록 요인을 기본 분석 딕셔너리로 초기화
    payload_data: Dict[str, np.ndarray] = {
        "Target_Response": clean_y,
        "Block_Factor": clean_blocks
    }
    formula_components: List[str] = ["C(Block_Factor)"]
    sanitized_factor_names: List[str] = []

    # 2. OLS formula 특수문자 에러 방지를 위해 변수명을 정규화하고 처리 요인 수식 항 생성
    for idx, (factor_name, factor_values) in enumerate(clean_treatments.items()):
        safe_key = f"Factor_{idx}_{factor_name}".replace(" ", "_").replace("-", "_")
        payload_data[safe_key] = factor_values
        formula_components.append(f"C({safe_key})")
        sanitized_factor_names.append(safe_key)

    # 3. OLS 입력용 DataFrame 및 최종 회귀 포뮬러 문자열 조립
    analysis_frame = pd.DataFrame(payload_data)
    formula_string = f"Target_Response ~ {' + '.join(formula_components)}"

    return analysis_frame, formula_string, sanitized_factor_names


def _fit_ols_model(
    analysis_frame: pd.DataFrame,
    formula_string: str
) -> Any:
    """구조화된 수식과 데이터를 바탕으로 statsmodels OLS 모형을 적합합니다."""
    return ols(formula=formula_string, data=analysis_frame).fit()


def _calculate_anova_table(
    fitted_ols: Any,
    anova_type: int
) -> pd.DataFrame:
    """적합된 OLS 모형으로부터 anova_type에 맞는 분산분석표를 산출합니다."""
    return sm.stats.anova_lm(fitted_ols, typ=anova_type)


def _extract_factor_p_values(
    anova_table: pd.DataFrame,
    factor_names: List[str]
) -> Tuple[Dict[str, float], float]:
    """분산분석표에서 블록 및 처리 요인의 p-value를 파싱합니다."""
    factor_p_values: Dict[str, float] = {}

    # 1. 정규화된 키(Factor_{idx}_{name}) 기준으로 ANOVA 표에서 처리 요인별 p-value 추출
    for factor_key in factor_names:
        table_row = f"C({factor_key})"
        original_name = "_".join(factor_key.split("_")[2:]) if factor_key.startswith("Factor_") else factor_key

        if table_row in anova_table.index and "PR(>F)" in anova_table.columns:
            factor_p_values[original_name] = float(anova_table.loc[table_row, "PR(>F)"])
        else:
            factor_p_values[original_name] = 1.0

    # 2. 블록 요인(시장 국면/Fold) 행에서 블록 p-value 추출
    block_row = "C(Block_Factor)"
    block_p_value = (
        float(anova_table.loc[block_row, "PR(>F)"])
        if block_row in anova_table.index and "PR(>F)" in anova_table.columns
        else 1.0
    )

    return factor_p_values, block_p_value


def _build_final_anova_result(
    anova_table: pd.DataFrame,
    factor_p_values: Dict[str, float],
    block_p_value: float,
    significance_level: float,
    method: str
) -> Dict[str, Any]:
    """최종 검정 통계량, p-value 및 Omnibus 유의성 판정 결과를 패키징합니다."""
    # 1. 다중 전처리 요인 중 최저 p-value 산출
    min_treatment_p = min(factor_p_values.values()) if factor_p_values else 1.0

    # 2. 전처리 요인 중 단 하나라도 유의수준 미만인지 옴니버스 게이트 유의성 판정
    is_treatment_significant = any(p < significance_level for p in factor_p_values.values())

    # 3. 블록 요인(시장 국면)의 분산 유의성 여부 판정
    is_block_significant = bool(block_p_value < significance_level)

    # 4. 검정표 및 판정 지표를 포함하는 최종 결과 딕셔너리 반환
    return {
        "anova_table": anova_table,
        "treatment_p_value": min_treatment_p,
        "block_p_value": block_p_value,
        "is_treatment_significant": is_treatment_significant,
        "is_block_significant": is_block_significant,
        "factor_p_values": factor_p_values,
        "method": method
    }