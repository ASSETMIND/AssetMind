from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple
import numpy as np
import pandas as pd
from scipy import stats

from src.model.evaluation.metrics import (
    newey_west_tstat,
    signal_sharpe,
    sortino_ratio,
)
from src.statistics.bootstrap_resample import generate_bootstrap_indices
from src.statistics.error_control.type1_error_control import control_type1_error
from src.statistics.error_control.type2_error_control import compute_type2_error
from src.statistics.non_parametric.signed_rank_test import signed_rank_test
from src.statistics.parametric.paired_t_test import paired_t_test

# ==============================================================================
# Constants & Configuration
# ==============================================================================
# --- 가설 검정 및 검정력 유의수준 설정 ---
DEFAULT_SIGNIFICANCE_LEVEL: float = 0.05                                                # 가설 검정 기본 유의수준 (alpha)
DEFAULT_TARGET_POWER: float = 0.80                                                      # 목표 통계적 검정력 (1 - beta)
MIN_SHAPIRO_SAMPLE_SIZE: int = 3                                                        # Shapiro-Wilk 정규성 검정 최소 유효 표본 크기
MIN_EFFECTIVE_SAMPLE_SIZE: int = 2                                                      # 자유도(df >= 1) 확보를 위한 최소 유효 표본 크기

# --- 시계열 관측창 및 거버넌스 레짐 설정 ---
DEFAULT_HOLDING_PERIOD_DAYS: int = 20                                                   # 비중첩 블록 평가 및 CBB 블록 길이 (20영업일)
DEFAULT_EVALUATION_HORIZON_DAYS: int = 60                                               # 롤링 성과 지표 산출을 위한 관측 호라이즌 (60영업일)
BLOCK_STEP_HOLDING_PERIOD: int = 1                                                      # 일별 실현 수익률 원장 평가 단위 호라이즌
CALM_REGIME_GATE_THRESHOLD: float = 0.80                                                # 비개입 평온장 판정을 위한 기본 리스크 게이트 임계치
EFFECTIVE_CALM_QUANTILE: float = 0.70                                                   # 항등 구간 방어용 실질 평온장 게이트 상위 분위수 기준
DEFAULT_TOST_EQUIVALENCE_MARGIN: float = 0.0005                                         # 평온장 구간 일별 수익률 동등성 실무 마진 (±5 bps)

# --- 수치 안정성 및 스케일링 상수 설정 ---
ANNUAL_TRADING_DAYS: float = 252.0                                                      # 연율화 환산을 위한 연간 영업일 수
DOWNSIDE_STD_FLOOR_RATIO: float = 0.25                                                  # 하방 변동성 붕괴 방어를 위한 전체 표준편차 대비 최소 비율
MIN_DOWNSIDE_DEVIATION_FLOOR: float = 1e-4                                              # 하방 변동성 분모 최소 하한선
SORTINO_CLIP_BOUND: float = 5.0                                                         # 단일 윈도우 소르티노 지수 극단치 클리핑 상하한
ZERO_DIVISION_EPSILON: float = 1e-12                                                    # 분모 제로 나눗셈 및 분산 0 판정 미소 상수
PERCENTAGE_FACTOR: float = 100.0                                                        # 백분율(%) 변환 스케일링 계수

# --- 부트스트랩 리샘플링 및 신뢰구간 설정 ---
DEFAULT_BOOTSTRAP_ROUNDS: int = 5000                                                    # CBB 교차검증 반복 복원추출 횟수 (B)
DEFAULT_BOOTSTRAP_METHOD: Literal["cbb", "sb"] = "cbb"                                  # 기본 시계열 블록 부트스트랩 알고리즘
BOOTSTRAP_CI_LOWER_PERCENTILE: float = 2.5                                              # 부트스트랩 95% 신뢰구간 하한 백분위수
BOOTSTRAP_CI_UPPER_PERCENTILE: float = 97.5                                             # 부트스트랩 95% 신뢰구간 상한 백분위수

# --- 통계 알고리즘 라우팅 기본값 설정 ---
DEFAULT_PARAMETRIC_METHOD: Literal["student", "nadeau_bengio"] = "nadeau_bengio"        # 모수 검정 시계열 분산보정 기본 알고리즘
DEFAULT_NON_PARAMETRIC_METHOD: Literal["wilcoxon", "pratt"] = "pratt"                   # 비모수 부호순위검정 기본 알고리즘
DEFAULT_FWER_METHOD: Literal["bonferroni", "holm", "romano_wolf"] = "holm"              # 다중비교 제1종 오류 보정 기본 알고리즘
DEFAULT_TYPE2_METHOD: Literal["normal", "nct"] = "nct"                                  # 제2종 오류 비중심 t-분포 적분 기본 알고리즘

# --- 시뮬레이션 원장 기본 컬럼명 설정 ---
RAW_RETURN_COLUMN: str = "Strategy_1_Raw_Model__strategy_return"                        # 원시 모델 일별 전략 수익률 컬럼명
GATED_RETURN_COLUMN: str = "Strategy_2_XAI-Gated__strategy_return"                      # 방어 거버넌스 일별 전략 수익률 컬럼명
RAW_DRAWDOWN_COLUMN: str = "Strategy_1_Raw_Model__drawdown"                             # 원시 모델 일별 수중 낙폭 컬럼명
GATED_DRAWDOWN_COLUMN: str = "Strategy_2_XAI-Gated__drawdown"                           # 방어 거버넌스 일별 수중 낙폭 컬럼명
RISK_GATE_COLUMN: str = "composite_risk_gate"                                           # 일별 복합 리스크 게이트 가중치 컬럼명


# ==============================================================================
# Public API Functions
# ==============================================================================
def evaluate_defense_governance(
    simulation_ledgers: pd.DataFrame,
    strategy_signals: pd.DataFrame,
    holding_period: int = DEFAULT_HOLDING_PERIOD_DAYS,
    eval_horizon: int = DEFAULT_EVALUATION_HORIZON_DAYS,
    alpha: float = DEFAULT_SIGNIFICANCE_LEVEL,
    tost_margin: float = DEFAULT_TOST_EQUIVALENCE_MARGIN,
    calm_gate_threshold: float = CALM_REGIME_GATE_THRESHOLD,
    num_bootstraps: int = DEFAULT_BOOTSTRAP_ROUNDS,
    bootstrap_method: Literal["cbb", "sb"] = DEFAULT_BOOTSTRAP_METHOD,
    parametric_method: Literal["student", "nadeau_bengio"] = DEFAULT_PARAMETRIC_METHOD,
    non_parametric_method: Literal["wilcoxon", "pratt"] = DEFAULT_NON_PARAMETRIC_METHOD,
    fwer_method: Literal["bonferroni", "holm", "romano_wolf"] = DEFAULT_FWER_METHOD,
    hypothesis_weights: Optional[Sequence[float]] = None,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """원시 대조군 대비 XAI 방어 거버넌스의 하방 리스크 억제 가설 검정 및 평온장 TOST 동등성 검정을 수행합니다.

    Args:
        simulation_ledgers (pd.DataFrame): 전략별 일별 수익률 및 수중 낙폭이 기록된 백테스트 원장 데이터프레임.
        strategy_signals (pd.DataFrame): 일별 복합 리스크 게이트(G_t) 및 포지션 신호가 기록된 데이터프레임.
        holding_period (int): 비중첩 유효 표본 환산 및 CBB 블록 길이 (기본값: 20영업일).
        eval_horizon (int): 롤링 MDD 및 롤링 Sortino 시계열 산출을 위한 관측창 길이 (기본값: 60영업일).
        alpha (float): 제1종 오류 제어, 정규성 분기 및 TOST 동등성 판정 유의수준 (기본값: 0.05).
        tost_margin (float): 평온장 구간 원시 성능 보존 판정을 위한 TOST 실무 마진 ±δ (기본값: 0.0005).
        calm_gate_threshold (float): 평온장 구간과 리스크 개입 구간을 분할하는 게이트 임계치 (기본값: 0.80).
        num_bootstraps (int): CBB 신뢰구간 및 Romano-Wolf 다중검정을 위한 부트스트랩 반복 횟수 (기본값: 5000).
        bootstrap_method (Literal["cbb", "sb"]): 시계열 블록 부트스트랩 리샘플링 알고리즘 ('cbb' 또는 'sb').
        parametric_method (Literal["student", "nadeau_bengio"]): 정규성 만족 시 대응표본 t-검정 알고리즘 (기본값: 'nadeau_bengio').
        non_parametric_method (Literal["wilcoxon", "pratt"]): 정규성 기각 시 부호순위검정 알고리즘 (기본값: 'pratt').
        fwer_method (Literal["bonferroni", "holm", "romano_wolf"]): 다중비교 제1종 오류 보정 알고리즘 (기본값: 'holm').
        hypothesis_weights (Optional[Sequence[float]]): 가설 3종(MDD, Sortino, 개입 낙폭)의 사전 중요도 가중치 시퀀스.
        seed (Optional[int]): 부트스트랩 리샘플링 재현성을 보장하기 위한 난수 시드 값.

    Returns:
        Dict[str, Any]:
            - hypothesis_audit_table: 하방 리스크 억제 단측 가설 검정 및 제1·2종 오류 감사표 (pd.DataFrame).
            - equivalence_audit_table: 평온장 원시 성능 보존 TOST 동등성 감사표 (pd.DataFrame).
            - guardrail_summary_table: 1차 핵심 지표 및 2차 가드레일 지표 비교 요약표 (pd.DataFrame).
            - raw_test_results: 개별 검정 통계량, 부트스트랩 신뢰구간 및 실행 설정 메타데이터 딕셔너리.

    Raises:
        KeyError: 필수 수익률, 낙폭 또는 리스크 게이트 컬럼이 입력 데이터프레임에 누락된 경우.
        ValueError: 원장과 신호 데이터의 시계열 길이가 불일치하거나 가중치 차원이 부적합한 경우.
    """
    # 1. 백테스트 원장 및 신호 데이터프레임의 정합성을 검증하고 1차원 수치 벡터를 추출
    raw_returns, gated_returns, raw_drawdowns, gated_drawdowns, risk_gates = (
        _extract_aligned_governance_vectors(
            simulation_ledgers=simulation_ledgers,
            strategy_signals=strategy_signals,
        )
    )

    # 2. 리스크 게이트 임계치 및 유효 표본 조건을 기반으로 평온장/개입 구간 마스크를 분할
    calm_mask, intervention_mask, effective_gate_threshold, calm_regime_label = (
        _resolve_governance_regime_masks(
            raw_returns=raw_returns,
            gated_returns=gated_returns,
            risk_gates=risk_gates,
            calm_gate_threshold=calm_gate_threshold,
            min_calm_samples=holding_period,
        )
    )

    # 3. 하방 리스크 억제 3대 가설에 대해 정규성 진단 기반 모수/비모수 동적 라우팅 및 부트스트랩 수행
    raw_hypothesis_records, aligned_bootstrap_matrix = _run_hybrid_downside_tests(
        raw_returns=raw_returns,
        gated_returns=gated_returns,
        raw_drawdowns=raw_drawdowns,
        gated_drawdowns=gated_drawdowns,
        intervention_mask=intervention_mask,
        effective_gate_threshold=effective_gate_threshold,
        holding_period=holding_period,
        eval_horizon=eval_horizon,
        alpha=alpha,
        parametric_method=parametric_method,
        non_parametric_method=non_parametric_method,
        num_bootstraps=num_bootstraps,
        bootstrap_method=bootstrap_method,
        seed=seed,
    )

    # 4. 가설별 중요도 가중치를 확정하고 다중비교 제1종 오류(FWER) 및 제2종 오류(β) 통제 감사표 생성
    resolved_weights: np.ndarray = _resolve_hypothesis_weights(
        bootstrap_matrix=aligned_bootstrap_matrix,
        hypothesis_weights=hypothesis_weights,
    )
    hypothesis_audit_table: pd.DataFrame = _apply_error_controls_to_hypotheses(
        hypothesis_records=raw_hypothesis_records,
        bootstrap_matrix=aligned_bootstrap_matrix,
        fwer_method=fwer_method,
        hypothesis_weights=resolved_weights,
        alpha=alpha,
    )

    # 5. 비개입 평온장 구간의 원시 수익률 보존 여부를 검증하는 TOST 동등성 감사표 생성
    equivalence_audit_table: pd.DataFrame = _run_non_intervention_tost_audit(
        raw_returns=raw_returns,
        gated_returns=gated_returns,
        calm_mask=calm_mask,
        calm_regime_label=calm_regime_label,
        holding_period=holding_period,
        tost_margin=tost_margin,
        alpha=alpha,
        parametric_method=parametric_method,
        non_parametric_method=non_parametric_method,
    )

    # 6. 1차 핵심 성과 지표 및 2차 가드레일 지표 대조 요약표 생성
    guardrail_summary_table: pd.DataFrame = _build_guardrail_summary_table(
        raw_returns=raw_returns,
        gated_returns=gated_returns,
        raw_drawdowns=raw_drawdowns,
        gated_drawdowns=gated_drawdowns,
        calm_mask=calm_mask,
        holding_period=holding_period,
    )

    return {
        "hypothesis_audit_table": hypothesis_audit_table,
        "equivalence_audit_table": equivalence_audit_table,
        "guardrail_summary_table": guardrail_summary_table,
        "raw_test_results": {
            "downside_tests": raw_hypothesis_records,
            "holding_period": holding_period,
            "eval_horizon": eval_horizon,
            "effective_gate_threshold": effective_gate_threshold,
            "alpha": alpha,
            "tost_margin": tost_margin,
            "num_bootstraps": num_bootstraps,
            "fwer_method": fwer_method,
            "hypothesis_weights": list(resolved_weights),
        },
    }


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _extract_aligned_governance_vectors(
    simulation_ledgers: pd.DataFrame,
    strategy_signals: pd.DataFrame,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """원장 및 신호 데이터프레임의 필수 컬럼 존재 여부와 시계열 정렬을 검증하고 1차원 배열을 추출합니다."""
    # 1. 원장 및 신호 데이터프레임의 필수 컬럼 존재 여부 검증
    required_ledger_columns: Tuple[str, ...] = (
        RAW_RETURN_COLUMN,
        GATED_RETURN_COLUMN,
        RAW_DRAWDOWN_COLUMN,
        GATED_DRAWDOWN_COLUMN,
    )
    for column_name in required_ledger_columns:
        if column_name not in simulation_ledgers.columns:
            raise KeyError(f"simulation_ledgers에 필수 컬럼이 누락되었습니다: '{column_name}'")

    if RISK_GATE_COLUMN not in strategy_signals.columns:
        raise KeyError(f"strategy_signals에 필수 컬럼이 누락되었습니다: '{RISK_GATE_COLUMN}'")

    # 2. 두 데이터프레임 간 관측치 길이 정합성 검증
    if len(simulation_ledgers) != len(strategy_signals):
        raise ValueError(
            f"원장과 신호 데이터의 시계열 길이가 불일치합니다: "
            f"{len(simulation_ledgers)} != {len(strategy_signals)}"
        )

    # 3. 수리 통계 연산을 위한 연속 메모리(Contiguous) 1차원 배열 추출
    raw_returns: np.ndarray = np.ascontiguousarray(simulation_ledgers[RAW_RETURN_COLUMN], dtype=np.float64)
    gated_returns: np.ndarray = np.ascontiguousarray(simulation_ledgers[GATED_RETURN_COLUMN], dtype=np.float64)
    raw_drawdowns: np.ndarray = np.ascontiguousarray(simulation_ledgers[RAW_DRAWDOWN_COLUMN], dtype=np.float64)
    gated_drawdowns: np.ndarray = np.ascontiguousarray(simulation_ledgers[GATED_DRAWDOWN_COLUMN], dtype=np.float64)
    risk_gates: np.ndarray = np.ascontiguousarray(strategy_signals[RISK_GATE_COLUMN], dtype=np.float64)

    return raw_returns, gated_returns, raw_drawdowns, gated_drawdowns, risk_gates


def _resolve_governance_regime_masks(
    raw_returns: np.ndarray,
    gated_returns: np.ndarray,
    risk_gates: np.ndarray,
    calm_gate_threshold: float,
    min_calm_samples: int,
) -> Tuple[np.ndarray, np.ndarray, float, str]:
    """평온장 및 리스크 개입 구간의 유효 표본 수와 비영(non-zero) 분산을 점검하여 상호 배타적 마스크 쌍을 반환합니다."""
    # 1. 기본 임계치 기준 평온장 마스크 및 수익률 차분 산출
    strict_calm_mask: np.ndarray = risk_gates >= calm_gate_threshold
    strict_diffs: np.ndarray = (
        gated_returns[strict_calm_mask] - raw_returns[strict_calm_mask]
        if np.any(strict_calm_mask)
        else np.empty(0, dtype=np.float64)
    )
    non_zero_count: int = int(np.sum(np.abs(strict_diffs) > ZERO_DIVISION_EPSILON))

    # 2. 최소 표본 수 및 비영 차분 조건 충족 여부에 따라 절대 임계치 또는 상위 분위수 레짐 확정
    if int(np.sum(strict_calm_mask)) >= min_calm_samples and non_zero_count >= MIN_SHAPIRO_SAMPLE_SIZE:
        calm_mask: np.ndarray = strict_calm_mask
        effective_threshold: float = calm_gate_threshold
        calm_label: str = f"Non-Intervention Calm (G_t >= {calm_gate_threshold:.2f})"
    else:
        effective_threshold = float(np.quantile(risk_gates, EFFECTIVE_CALM_QUANTILE))
        calm_mask = risk_gates >= effective_threshold
        top_pct: int = int(round((1.0 - EFFECTIVE_CALM_QUANTILE) * PERCENTAGE_FACTOR))
        calm_label = f"Effective Calm Regime (G_t >= {effective_threshold:.4f}, Top {top_pct}%)"

    # 3. 평온장의 여집합으로 리스크 개입 구간 마스크 생성 및 빈 마스크 방어
    intervention_mask: np.ndarray = ~calm_mask
    if not np.any(intervention_mask):
        intervention_mask = np.ones_like(risk_gates, dtype=bool)

    return calm_mask, intervention_mask, effective_threshold, calm_label


def _run_hybrid_downside_tests(
    raw_returns: np.ndarray,
    gated_returns: np.ndarray,
    raw_drawdowns: np.ndarray,
    gated_drawdowns: np.ndarray,
    intervention_mask: np.ndarray,
    effective_gate_threshold: float,
    holding_period: int,
    eval_horizon: int,
    alpha: float,
    parametric_method: Literal["student", "nadeau_bengio"],
    non_parametric_method: Literal["wilcoxon", "pratt"],
    num_bootstraps: int,
    bootstrap_method: Literal["cbb", "sb"],
    seed: Optional[int],
) -> Tuple[List[Dict[str, Any]], np.ndarray]:
    """하방 리스크 억제 3대 가설에 대해 모수/비모수 동적 라우팅 주검정과 CBB 부트스트랩 교차검증을 결합 집행합니다."""
    # 1. 3대 하방 리스크 가설별 대응 표본 시계열 쌍(Gated vs Raw) 생성
    paired_series_specs: List[Dict[str, Any]] = _build_downside_hypothesis_series_specs(
        raw_returns=raw_returns,
        gated_returns=gated_returns,
        raw_drawdowns=raw_drawdowns,
        gated_drawdowns=gated_drawdowns,
        intervention_mask=intervention_mask,
        effective_gate_threshold=effective_gate_threshold,
        holding_period=holding_period,
        eval_horizon=eval_horizon,
    )

    records: List[Dict[str, Any]] = []
    aligned_bootstrap_columns: List[np.ndarray] = []

    # 2. 가설별 정규성 진단, 동적 라우팅 가설 검정 및 시계열 블록 부트스트랩 순차 집행
    for index, spec in enumerate(paired_series_specs):
        sample_a: np.ndarray = spec["sample_a"]
        sample_b: np.ndarray = spec["sample_b"]
        alternative: Literal["less", "greater"] = spec["alternative"]
        n_obs: int = len(sample_a)
        effective_n: int = _compute_effective_sample_size(n_obs=n_obs, holding_period=holding_period)
        block_len: int = min(max(1, holding_period), n_obs)

        # 차분 벡터 정규성 검정 및 모수/비모수 검정 라우팅
        diff_vector: np.ndarray = sample_a - sample_b
        shapiro_p: float = _check_normality_shapiro(differences=diff_vector)
        routed_result: Dict[str, Any] = _route_paired_significance_test(
            sample_a=sample_a,
            sample_b=sample_b,
            effective_n=effective_n,
            shapiro_p=shapiro_p,
            alpha=alpha,
            alternative=alternative,
            parametric_method=parametric_method,
            non_parametric_method=non_parametric_method,
        )

        # 시계열 블록 부트스트랩 신뢰구간 및 Romano-Wolf용 귀무 벡터 산출
        hypothesis_seed: Optional[int] = None if seed is None else seed + index
        ci_lower, ci_upper, aligned_boot_vector = _compute_bootstrap_ci_and_null_vector(
            differences=diff_vector,
            alternative=alternative,
            block_size=block_len,
            num_bootstraps=num_bootstraps,
            bootstrap_method=bootstrap_method,
            seed=hypothesis_seed,
        )
        aligned_bootstrap_columns.append(aligned_boot_vector)

        records.append({
            "hypothesis_name": spec["name"],
            "metric_name": spec["metric"],
            "routed_test": f"{routed_result['test_label']} + {bootstrap_method.upper()}(b={block_len})",
            "sample_size": n_obs,
            "effective_sample_size": effective_n,
            "shapiro_p": shapiro_p,
            "mean_difference": routed_result["mean_difference"],
            "bootstrap_ci": f"[{ci_lower:.6f}, {ci_upper:.6f}]",
            "effect_size": routed_result["effect_size"],
            "statistic": routed_result["statistic"],
            "p_value": routed_result["p_value"],
            "alternative": alternative,
        })

    # 3. 부트스트랩 차분 벡터들을 (B x M) 행렬로 병합하여 반환
    aligned_bootstrap_matrix: np.ndarray = np.column_stack(aligned_bootstrap_columns)
    return records, aligned_bootstrap_matrix


def _build_downside_hypothesis_series_specs(
    raw_returns: np.ndarray,
    gated_returns: np.ndarray,
    raw_drawdowns: np.ndarray,
    gated_drawdowns: np.ndarray,
    intervention_mask: np.ndarray,
    effective_gate_threshold: float,
    holding_period: int,
    eval_horizon: int,
) -> List[Dict[str, Any]]:
    """하방 리스크 3대 가설 검정을 위한 시점별 대응 표본 시계열 쌍(Gated vs Raw)과 메타 명세를 생성합니다."""
    # 1. 롤링 관측 윈도우 크기 확정 및 롤링 최대 낙폭(|MDD|) 시계열 산출
    rolling_window: int = max(holding_period, eval_horizon)
    raw_rolling_mdd: np.ndarray = _compute_rolling_max_drawdown_series(
        drawdowns=raw_drawdowns,
        window=rolling_window,
        min_periods=holding_period,
    )
    gated_rolling_mdd: np.ndarray = _compute_rolling_max_drawdown_series(
        drawdowns=gated_drawdowns,
        window=rolling_window,
        min_periods=holding_period,
    )

    # 2. 롤링 소르티노 지수(Sortino Ratio) 시계열 산출
    raw_rolling_sortino: np.ndarray = _compute_rolling_sortino_series(
        returns=raw_returns,
        window=rolling_window,
        min_periods=holding_period,
    )
    gated_rolling_sortino: np.ndarray = _compute_rolling_sortino_series(
        returns=gated_returns,
        window=rolling_window,
        min_periods=holding_period,
    )

    # 3. 리스크 개입 구간(G_t < threshold)의 일별 절대 수중 낙폭 추출
    raw_intervention_dd: np.ndarray = np.abs(raw_drawdowns[intervention_mask])
    gated_intervention_dd: np.ndarray = np.abs(gated_drawdowns[intervention_mask])

    # 4. 가설별 대립가설 방향(less/greater)을 포함한 검정 명세 리스트 구성
    return [
        {
            "name": "H1_Risk_MDD_Suppression",
            "metric": f"Rolling Maximum Drawdown |MDD| ({rolling_window}d)",
            "sample_a": gated_rolling_mdd,
            "sample_b": raw_rolling_mdd,
            "alternative": "less",
        },
        {
            "name": "H1_Risk_Sortino_Improvement",
            "metric": f"Rolling Sortino Ratio ({rolling_window}d)",
            "sample_a": gated_rolling_sortino,
            "sample_b": raw_rolling_sortino,
            "alternative": "greater",
        },
        {
            "name": "H1_Risk_Intervention_Drawdown_Suppression",
            "metric": f"Intervention |Drawdown| (G_t < {effective_gate_threshold:.4f})",
            "sample_a": gated_intervention_dd,
            "sample_b": raw_intervention_dd,
            "alternative": "less",
        },
    ]


def _compute_effective_sample_size(n_obs: int, holding_period: int) -> int:
    """전체 관측 일수와 보유 호라이즌을 기반으로 비중첩 유효 표본 크기(N_eff)를 산출합니다."""
    return max(MIN_EFFECTIVE_SAMPLE_SIZE, n_obs // max(1, holding_period))


def _compute_rolling_max_drawdown_series(
    drawdowns: np.ndarray,
    window: int,
    min_periods: int,
) -> np.ndarray:
    """일별 수중 낙폭 벡터로부터 지정된 관측창 기준 롤링 최대 낙폭(|MDD|) 시계열을 산출합니다."""
    # 1. 수중 낙폭을 절대값으로 변환하고 유효 롤링 윈도우 경계 설정
    abs_drawdowns: np.ndarray = np.abs(drawdowns)
    effective_window: int = max(1, min(window, len(abs_drawdowns)))
    effective_min_periods: int = max(1, min(min_periods, effective_window))

    # 2. 롤링 최대값 산출 및 초기 결측 구간 역방향 패딩
    rolling_mdd_series: pd.Series = (
        pd.Series(abs_drawdowns)
        .rolling(window=effective_window, min_periods=effective_min_periods)
        .max()
        .bfill()
    )
    return np.ascontiguousarray(rolling_mdd_series.to_numpy(dtype=np.float64))


def _compute_rolling_sortino_series(
    returns: np.ndarray,
    window: int,
    min_periods: int,
) -> np.ndarray:
    """일별 수익률 벡터로부터 지정된 관측창 기준 연율화 롤링 소르티노 지수 시계열을 산출합니다."""
    # 1. 유효 롤링 윈도우 설정 및 음수 수익률 제곱 시계열 구성
    n_samples: int = len(returns)
    effective_window: int = max(MIN_EFFECTIVE_SAMPLE_SIZE, min(window, n_samples))
    effective_min_periods: int = max(MIN_EFFECTIVE_SAMPLE_SIZE, min(min_periods, effective_window))

    return_series: pd.Series = pd.Series(returns, dtype=np.float64)
    downside_squared_series: pd.Series = np.minimum(0.0, return_series) ** 2

    # 2. 롤링 평균, 전체 표준편차 및 하방 편차(Downside Deviation) 산출
    rolling_mean: np.ndarray = (
        return_series.rolling(window=effective_window, min_periods=effective_min_periods)
        .mean()
        .bfill()
        .to_numpy(dtype=np.float64)
    )
    rolling_std: np.ndarray = (
        return_series.rolling(window=effective_window, min_periods=effective_min_periods)
        .std(ddof=1)
        .bfill()
        .fillna(0.0)
        .to_numpy(dtype=np.float64)
    )
    rolling_downside_dev: np.ndarray = np.sqrt(
        downside_squared_series.rolling(window=effective_window, min_periods=effective_min_periods)
        .mean()
        .bfill()
        .fillna(0.0)
        .to_numpy(dtype=np.float64)
    )

    # 3. 분모 붕괴 방어용 하한선 적용 후 연율화 소르티노 지수 산출 및 클리핑
    effective_downside_dev: np.ndarray = np.maximum(
        np.maximum(rolling_downside_dev, DOWNSIDE_STD_FLOOR_RATIO * rolling_std),
        MIN_DOWNSIDE_DEVIATION_FLOOR,
    )
    raw_rolling_sortino: np.ndarray = np.sqrt(ANNUAL_TRADING_DAYS) * (rolling_mean / effective_downside_dev)
    return np.ascontiguousarray(
        np.clip(raw_rolling_sortino, -SORTINO_CLIP_BOUND, SORTINO_CLIP_BOUND),
        dtype=np.float64,
    )


def _check_normality_shapiro(differences: np.ndarray) -> float:
    """차분 시계열 벡터에 대해 Shapiro-Wilk 정규성 검정을 수행하고 p-value를 반환합니다."""
    # 1. 유한한 관측치 필터링 및 최소 표본/분산 충족 여부 확인
    clean_diff: np.ndarray = differences[np.isfinite(differences)]
    if len(clean_diff) < MIN_SHAPIRO_SAMPLE_SIZE:
        return 1.0
    if float(np.std(clean_diff, ddof=1)) <= ZERO_DIVISION_EPSILON:
        return 1.0

    # 2. Shapiro-Wilk 정규성 검정 수행
    _, p_value = stats.shapiro(clean_diff)
    return float(p_value)


def _route_paired_significance_test(
    sample_a: np.ndarray,
    sample_b: np.ndarray,
    effective_n: int,
    shapiro_p: float,
    alpha: float,
    alternative: Literal["two-sided", "greater", "less"],
    parametric_method: Literal["student", "nadeau_bengio"],
    non_parametric_method: Literal["wilcoxon", "pratt"],
) -> Dict[str, Any]:
    """Shapiro-Wilk 정규성 진단 결과에 따라 유효 표본 스케일이 반영된 대응표본 t-검정 또는 부호순위검정으로 라우팅합니다."""
    n_obs: int = len(sample_a)

    # 1. 정규성 만족(p >= alpha) 시: 모수적 대응표본 t-검정 수행
    if shapiro_p >= alpha:
        nb_ratio: Optional[float] = (
            max(ZERO_DIVISION_EPSILON, (1.0 / float(effective_n)) - (1.0 / float(max(n_obs, 1))))
            if parametric_method == "nadeau_bengio"
            else None
        )
        param_res: Dict[str, Any] = paired_t_test(
            sample_a_values=sample_a,
            sample_b_values=sample_b,
            method=parametric_method,
            alternative=alternative,
            test_train_ratio=nb_ratio,
        )
        return {
            "test_label": f"Paired t-test ({parametric_method})",
            "statistic": float(param_res["statistic"]),
            "p_value": float(param_res["p_value"]),
            "mean_difference": float(param_res["mean_difference"]),
            "effect_size": float(param_res["cohen_dz"]),
        }

    # 2. 정규성 기각(p < alpha) 시: 비모수 부호순위검정 수행 및 자기상관 유효표본 스케일 보정
    non_param_res: Dict[str, Any] = signed_rank_test(
        sample_a_values=sample_a,
        sample_b_values=sample_b,
        method=non_parametric_method,
        alternative=alternative,
    )
    autocorr_scale: float = float(np.sqrt(float(effective_n) / float(max(n_obs, 1))))
    adjusted_z: float = float(non_param_res["z_statistic"]) * autocorr_scale

    if alternative == "two-sided":
        adjusted_p: float = float(np.clip(stats.norm.sf(np.abs(adjusted_z)) * 2.0, 0.0, 1.0))
    elif alternative == "greater":
        adjusted_p = float(np.clip(stats.norm.sf(adjusted_z), 0.0, 1.0))
    else:
        adjusted_p = float(np.clip(stats.norm.cdf(adjusted_z), 0.0, 1.0))

    # 3. 표준화 효과 크기(Cohen's dz) 산출 후 결과 반환
    differences: np.ndarray = sample_a - sample_b
    sample_std: float = max(float(np.std(differences, ddof=1)), ZERO_DIVISION_EPSILON)
    standardized_dz: float = float(non_param_res["mean_difference"]) / sample_std

    return {
        "test_label": f"Signed-Rank ({non_parametric_method})",
        "statistic": adjusted_z,
        "p_value": adjusted_p,
        "mean_difference": float(non_param_res["mean_difference"]),
        "effect_size": standardized_dz,
    }


def _compute_bootstrap_ci_and_null_vector(
    differences: np.ndarray,
    alternative: Literal["less", "greater"],
    block_size: int,
    num_bootstraps: int,
    bootstrap_method: Literal["cbb", "sb"],
    seed: Optional[int],
) -> Tuple[float, float, np.ndarray]:
    """시계열 블록 부트스트랩을 수행하여 평균 차분의 95% 신뢰구간과 대립가설 정렬 부트스트랩 벡터를 산출합니다."""
    # 1. 시계열 블록 부트스트랩 인덱스 행렬 생성
    n_samples: int = len(differences)
    bootstrap_indices: np.ndarray = generate_bootstrap_indices(
        n_samples=n_samples,
        num_bootstraps=num_bootstraps,
        block_size=block_size,
        method=bootstrap_method,
        seed=seed,
    )

    # 2. 복원추출 표본별 평균 차분 및 95% 백분위수 신뢰구간 산출
    boot_mean_diffs: np.ndarray = np.mean(differences[bootstrap_indices], axis=1)
    ci_lower: float = float(np.percentile(boot_mean_diffs, BOOTSTRAP_CI_LOWER_PERCENTILE))
    ci_upper: float = float(np.percentile(boot_mean_diffs, BOOTSTRAP_CI_UPPER_PERCENTILE))

    # 3. 대립가설 방향에 맞춰 부트스트랩 분포 부호 정렬
    aligned_vector: np.ndarray = -boot_mean_diffs if alternative == "less" else boot_mean_diffs
    return ci_lower, ci_upper, aligned_vector


def _apply_error_controls_to_hypotheses(
    hypothesis_records: List[Dict[str, Any]],
    bootstrap_matrix: np.ndarray,
    fwer_method: Literal["bonferroni", "holm", "romano_wolf"],
    hypothesis_weights: np.ndarray,
    alpha: float,
) -> pd.DataFrame:
    """개별 가설 검정 결과에 다중비교 제1종 오류 보정과 비중첩 유효표본 기준 제2종 오류 감사를 결합합니다."""
    # 1. 가설별 원시 유의확률 추출 및 다중비교 제1종 오류(FWER) 보정 수행
    raw_p_values: List[float] = [record["p_value"] for record in hypothesis_records]
    fwer_result: Dict[str, Any] = control_type1_error(
        p_values=raw_p_values,
        method=fwer_method,
        alpha=alpha,
        bootstrap_matrix=bootstrap_matrix if fwer_method == "romano_wolf" else None,
        weights=list(hypothesis_weights),
    )

    adjusted_p_values: np.ndarray = fwer_result["adjusted_p_values"]
    reject_flags: np.ndarray = fwer_result["reject"]

    # 2. 각 가설의 유효 표본 크기 기준 제2종 오류(β) 및 사후 검정력(1-β) 산출
    table_rows: List[Dict[str, Any]] = []
    for index, record in enumerate(hypothesis_records):
        type2_result: Dict[str, Any] = compute_type2_error(
            effect_size=record["effect_size"],
            sample_size=record["effective_sample_size"],
            alternative=record["alternative"],
            method=DEFAULT_TYPE2_METHOD,
            alpha=alpha,
            target_power=DEFAULT_TARGET_POWER,
        )
        table_rows.append({
            "Hypothesis": record["hypothesis_name"],
            "Metric": record["metric_name"],
            "Sample Size (N)": record["sample_size"],
            "Normality (Shapiro p)": round(record["shapiro_p"], 4),
            "Routed Test": record["routed_test"],
            "Weight (w)": round(float(hypothesis_weights[index]), 2),
            "Mean Diff (Risk - Raw)": round(record["mean_difference"], 6),
            "Bootstrap 95% CI": record["bootstrap_ci"],
            "Effect Size (dz)": round(record["effect_size"], 4),
            "Statistic": round(record["statistic"], 4),
            "Raw p-value": round(record["p_value"], 6),
            "Adj p-value": round(float(adjusted_p_values[index]), 6),
            "Post-hoc Power (1-β)": round(float(type2_result["power"]), 4),
            "Type II Error (β)": round(float(type2_result["beta"]), 4),
            f"Reject H0 (α={alpha})": bool(reject_flags[index]),
        })

    # 3. 숫자 인덱스(0, 1, 2...)를 제거하기 위해 Hypothesis 컬럼을 인덱스로 설정하여 반환
    return pd.DataFrame(table_rows).set_index("Hypothesis")


def _run_non_intervention_tost_audit(
    raw_returns: np.ndarray,
    gated_returns: np.ndarray,
    calm_mask: np.ndarray,
    calm_regime_label: str,
    holding_period: int,
    tost_margin: float,
    alpha: float,
    parametric_method: Literal["student", "nadeau_bengio"],
    non_parametric_method: Literal["wilcoxon", "pratt"],
) -> pd.DataFrame:
    """평온장 구간에서 원시 수익률 보존 여부를 정규성 진단 기반 모수/비모수 동적 라우팅 TOST 검정으로 입증합니다."""
    # 1. 평온장 구간의 수익률 차분 벡터 추출 및 기술통계량 산출
    raw_calm_returns: np.ndarray = raw_returns[calm_mask]
    gated_calm_returns: np.ndarray = gated_returns[calm_mask]
    diff_series: np.ndarray = gated_calm_returns - raw_calm_returns
    calm_days: int = len(diff_series)
    mean_diff: float = float(np.mean(diff_series))

    # 2. 수익률 차분이 완전히 0인 항등 보존 구간일 경우 결정론적 동등성 즉시 판정
    if float(np.std(diff_series, ddof=1)) <= ZERO_DIVISION_EPSILON and abs(mean_diff) <= tost_margin:
        return pd.DataFrame([{
            "Regime": calm_regime_label,
            "Calm Days (N)": calm_days,
            "Equivalence Margin (±δ)": f"±{tost_margin:.4f}",
            "Mean Return Diff": round(mean_diff, 6),
            "Normality (Shapiro p)": 1.0,
            "Routed Test": "Deterministic Equivalence (Zero Diff)",
            "Lower Bound p-val (> -δ)": 0.0,
            "Upper Bound p-val (< +δ)": 0.0,
            "TOST Combined p-val": 0.0,
            "Equivalence Established": True,
        }]).set_index("Regime")

    # 3. 정규성 진단 후 하한(> -δ) 및 상한(< +δ) 단측 검정을 각각 라우팅 실행
    shapiro_p: float = _check_normality_shapiro(differences=diff_series)
    effective_calm_n: int = _compute_effective_sample_size(n_obs=calm_days, holding_period=holding_period)

    lower_res: Dict[str, Any] = _route_paired_significance_test(
        sample_a=gated_calm_returns,
        sample_b=raw_calm_returns - tost_margin,
        effective_n=effective_calm_n,
        shapiro_p=shapiro_p,
        alpha=alpha,
        alternative="greater",
        parametric_method=parametric_method,
        non_parametric_method=non_parametric_method,
    )
    upper_res: Dict[str, Any] = _route_paired_significance_test(
        sample_a=gated_calm_returns,
        sample_b=raw_calm_returns + tost_margin,
        effective_n=effective_calm_n,
        shapiro_p=shapiro_p,
        alpha=alpha,
        alternative="less",
        parametric_method=parametric_method,
        non_parametric_method=non_parametric_method,
    )

    # 4. 두 단측 검정의 최대 p-value로 TOST 결합 유의확률을 확정하고 숫자 인덱스 제거 후 반환
    lower_p_val: float = float(lower_res["p_value"])
    upper_p_val: float = float(upper_res["p_value"])
    tost_p_value: float = max(lower_p_val, upper_p_val)

    return pd.DataFrame([{
        "Regime": calm_regime_label,
        "Calm Days (N)": calm_days,
        "Equivalence Margin (±δ)": f"±{tost_margin:.4f}",
        "Mean Return Diff": round(mean_diff, 6),
        "Normality (Shapiro p)": round(shapiro_p, 4),
        "Routed Test": f"TOST {lower_res['test_label']}",
        "Lower Bound p-val (> -δ)": round(lower_p_val, 6),
        "Upper Bound p-val (< +δ)": round(upper_p_val, 6),
        "TOST Combined p-val": round(tost_p_value, 6),
        "Equivalence Established": bool(tost_p_value < alpha),
    }]).set_index("Regime")


def _build_guardrail_summary_table(
    raw_returns: np.ndarray,
    gated_returns: np.ndarray,
    raw_drawdowns: np.ndarray,
    gated_drawdowns: np.ndarray,
    calm_mask: np.ndarray,
    holding_period: int,
) -> pd.DataFrame:
    """1차 핵심 지표 및 2차 가드레일 지표 대조 요약표를 생성합니다."""
    # 1. 1차 핵심 성과 지표(MDD, Sortino, Sharpe) 산출
    raw_mdd_pct: float = float(np.min(raw_drawdowns)) * PERCENTAGE_FACTOR
    gated_mdd_pct: float = float(np.min(gated_drawdowns)) * PERCENTAGE_FACTOR
    unit_weights: np.ndarray = np.ones_like(raw_returns)

    raw_sortino_val: float = float(
        sortino_ratio(y_true=raw_returns, y_pred=unit_weights, holding_period=BLOCK_STEP_HOLDING_PERIOD)
    )
    gated_sortino_val: float = float(
        sortino_ratio(y_true=gated_returns, y_pred=unit_weights, holding_period=BLOCK_STEP_HOLDING_PERIOD)
    )

    raw_sharpe_val: float = float(
        signal_sharpe(y_true=raw_returns, y_pred=unit_weights, holding_period=BLOCK_STEP_HOLDING_PERIOD)
    )
    gated_sharpe_val: float = float(
        signal_sharpe(y_true=gated_returns, y_pred=unit_weights, holding_period=BLOCK_STEP_HOLDING_PERIOD)
    )

    # 2. 2차 가드레일 지표(Newey-West HAC 유의성 및 평온장 Drag Ratio) 산출
    raw_nw_t, raw_nw_p = newey_west_tstat(y_true=raw_returns, y_pred=unit_weights, holding_period=holding_period)
    gated_nw_t, gated_nw_p = newey_west_tstat(y_true=gated_returns, y_pred=unit_weights, holding_period=holding_period)
    drag_ratio_pct: float = _compute_calm_regime_drag_ratio(
        raw_returns=raw_returns,
        gated_returns=gated_returns,
        calm_mask=calm_mask,
    )

    # 3. 지표 명세 기반 요약 행 생성 및 멀티 인덱스 설정을 통한 숫자 인덱스 제거
    metric_specs: Tuple[Tuple[str, str, float, float, int], ...] = (
        ("Primary (Downside)", "Maximum Drawdown (%)", raw_mdd_pct, gated_mdd_pct, 2),
        ("Primary (Downside)", "Sortino Ratio", raw_sortino_val, gated_sortino_val, 3),
        ("Primary (Risk-Adj)", "Annualized Sharpe Ratio", raw_sharpe_val, gated_sharpe_val, 3),
        ("Guardrail (HAC Significance)", "Newey-West t-statistic", float(raw_nw_t), float(gated_nw_t), 3),
        ("Guardrail (HAC Significance)", "Newey-West p-value", float(raw_nw_p), float(gated_nw_p), 6),
        ("Guardrail (Calm Regime Preservation)", "Calm Regime Drag Ratio (%)", 0.0, drag_ratio_pct, 4),
    )

    summary_rows: List[Dict[str, Any]] = [
        {
            "Metric Category": category,
            "Metric Name": name,
            "Strategy 1 (Raw Model)": round(raw_val, decimals),
            "Strategy 2 (XAI-Gated)": round(gated_val, decimals),
            "Delta (Risk - Raw)": round(gated_val - raw_val, decimals),
        }
        for category, name, raw_val, gated_val, decimals in metric_specs
    ]

    return pd.DataFrame(summary_rows).set_index(["Metric Category", "Metric Name"])


def _compute_calm_regime_drag_ratio(
    raw_returns: np.ndarray,
    gated_returns: np.ndarray,
    calm_mask: np.ndarray,
) -> float:
    """확정된 평온장 구간에서 원시 누적 수익 대비 거버넌스의 수익 잠식률(Drag Ratio, %)을 산출합니다."""
    # 1. 평온장 표본 부재 또는 원시 누적 수익 0 근접 시 예외 방어
    if not np.any(calm_mask):
        return 0.0

    raw_calm_sum: float = float(np.sum(raw_returns[calm_mask]))
    gated_calm_sum: float = float(np.sum(gated_returns[calm_mask]))
    if abs(raw_calm_sum) <= ZERO_DIVISION_EPSILON:
        return 0.0

    # 2. 원시 누적 수익 대비 잠식 비율(%) 산출
    return float(((raw_calm_sum - gated_calm_sum) / abs(raw_calm_sum)) * PERCENTAGE_FACTOR)


def _resolve_hypothesis_weights(
    bootstrap_matrix: np.ndarray,
    hypothesis_weights: Optional[Sequence[float]],
) -> np.ndarray:
    """사용자 지정 가중치가 없으면 부트스트랩 정밀도 기반 동적 가중치를 산출하고 합계 1.0으로 정규화합니다."""
    # 1. 미지정 시 부트스트랩 역표준오차(SNR) 기반 동적 가중치 산출
    if hypothesis_weights is None:
        return _compute_bootstrap_precision_weights(bootstrap_matrix=bootstrap_matrix)

    # 2. 사용자 지정 가중치 배열 변환 및 합계 1.0 정규화
    weight_array: np.ndarray = np.ascontiguousarray(hypothesis_weights, dtype=np.float64).flatten()
    return weight_array / max(float(np.sum(weight_array)), ZERO_DIVISION_EPSILON)


def _compute_bootstrap_precision_weights(
    bootstrap_matrix: np.ndarray,
) -> np.ndarray:
    """부트스트랩 차분 행렬(B x M)의 무차원 정밀도(역표준오차 SNR)를 기반으로 동적 가설 가중치를 산출합니다."""
    # 1. 가설별 부트스트랩 평균 및 표준오차 산출
    bootstrap_means: np.ndarray = np.mean(bootstrap_matrix, axis=0)
    bootstrap_standard_errors: np.ndarray = np.maximum(
        np.std(bootstrap_matrix, axis=0, ddof=1),
        ZERO_DIVISION_EPSILON,
    )

    # 2. 신호 대 잡음비(SNR) 기반 정밀도 점수 계산 및 정규화
    precision_scores: np.ndarray = np.maximum(
        bootstrap_means / bootstrap_standard_errors,
        ZERO_DIVISION_EPSILON,
    )
    return precision_scores / float(np.sum(precision_scores))