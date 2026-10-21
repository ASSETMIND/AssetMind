import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.model.xai.shap_schema import ShapResult

# ==============================================================================
# Constants & Configuration
# ==============================================================================

# [디렉터리 계층 구조 설정]
DEFAULT_ARTIFACT_ROOT: str = "artifacts"  # 영속화 최상위 루트 디렉터리 경로
MODELS_DIR_NAME: str = "models"  # 모델 인스턴스 및 메타데이터 적재 경로
EVALUATION_DIR_NAME: str = "evaluation"  # 모델 검증 시각화 아티팩트 적재 경로
XAI_DIR_NAME: str = "xai"  # XAI 감사 계층 최상위 디렉터리
XAI_FIGURES_DIR_NAME: str = "figures"  # XAI 고해상도 시각화 플롯 적재 경로
XAI_DATA_DIR_NAME: str = "data"  # XAI 수리통계 데이터 아티팩트 적재 경로
STRATEGY_HANDOFF_DIR_NAME: str = "strategy_handoff"  # 백테스팅 전략 인계 계약 디렉터리

# [영속화 파일 식별자 설정]
CHAMPION_MODEL_FILENAME: str = "champion_regressor.joblib"  # 챔피언 모델 직렬화 바이너리 파일명
CHAMPION_METADATA_FILENAME: str = "champion_metadata.json"  # 챔피언 메타데이터 파일명
CV_VS_TEST_DUMBBELL_FILENAME: str = "cv_vs_test_dumbbell.png"  # 일반화 열화 덤벨 플롯 파일명
UNDERWATER_DRAWDOWN_FILENAME: str = "test_underwater_drawdown.png"  # 실현 드로다운 플롯 파일명
SHAP_GLOBAL_SUMMARY_FILENAME: str = "shap_global_summary.png"  # 글로벌 Beeswarm & Bar 플롯 파일명
SHAP_DEPENDENCE_FILENAME: str = "shap_dependence_interaction.png"  # 2차 상호작용 의존성 플롯 파일명
SHAP_REGIME_WATERFALL_FILENAME: str = "shap_regime_waterfall.png"  # 3대 극단 국면 폭포수 플롯 파일명
SHAP_DYNAMIC_ROLLING_FILENAME: str = "shap_dynamic_rolling_kospi.png"  # 동적 롤링 SHAP 플롯 파일명
SHAP_RISK_POLICY_FILENAME: str = "shap_risk_policy_boundary.png"  # 변곡점 포지션 사이징 플롯 파일명
SHAP_VALUES_FILENAME: str = "shap_values_test.parquet"  # Holdout 원시 SHAP 행렬 파일명
FEATURE_IMPORTANCE_FILENAME: str = "feature_importance_report.parquet"  # 피처별 통계 기여도 감사표 파일명
INFLECTION_POLICY_FILENAME: str = "inflection_policy_summary.parquet"  # [신규] 리스크 변곡점 컷오프 정책표 파일명
REGIME_COHORT_AUDIT_FILENAME: str = "regime_cohort_audit.parquet"  # [신규] 5대 시장 국면 정량 감사표 파일명
XAI_SUMMARY_FILENAME: str = "xai_summary.json"  # XAI 공리 메타데이터 파일명
TEST_FEATURES_TARGET_FILENAME: str = "test_features_and_target.parquet"  # Holdout 피처 및 타깃 파일명
TEST_PREDICTIONS_FILENAME: str = "test_predictions.parquet"  # 챔피언 모델 추론값 및 잔차 파일명

# [I/O 및 파라미터 규격 설정]
IMAGE_DPI: int = 300  # 시각화 이미지 저장 해상도
IMAGE_BBOX_INCHES: str = "tight"  # 여백 최소화 바운딩 박스 옵션
JSON_INDENT: int = 4  # JSON 직렬화 들여쓰기 공백 수
PARQUET_ENGINE: str = "pyarrow"  # Parquet I/O 처리 엔진
TARGET_COLUMN_FALLBACK: str = "target_return_20d"  # 기본 타깃 컬럼명 대체값

# ==============================================================================
# Public API Functions
# ==============================================================================

def deploy_single_model(
    champion_result: Any,
    shap_result: Any,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    evaluation_figures: Optional[Dict[str, plt.Figure]] = None,
    xai_figures: Optional[Dict[str, plt.Figure]] = None,
    artifact_root: Union[str, Path] = DEFAULT_ARTIFACT_ROOT,
) -> Dict[str, Path]:
    """챔피언 모델, 평가 지표, XAI 산출물 및 전략 인계 데이터를 프로덕션 규격으로 일괄 영속화합니다.

    Args:
        champion_result (Any): 챔피언 모델 선별 결과 DTO.
        shap_result (Any): SHAP 설명 가능성 결과 DTO.
        X_test (pd.DataFrame): DatetimeIndex가 보존된 Holdout Test 피처 행렬.
        y_test (pd.Series): Holdout Test 정답 레이블 시계열.
        evaluation_figures (Optional[Dict[str, plt.Figure]]): 평가 플롯 딕셔너리. Defaults to None.
        xai_figures (Optional[Dict[str, plt.Figure]]): XAI 플롯 딕셔너리. Defaults to None.
        artifact_root (Union[str, Path]): 최상위 저장 경로. Defaults to DEFAULT_ARTIFACT_ROOT.

    Returns:
        Dict[str, Path]: 생성된 아티팩트 계층별 물리 경로 매핑.

    Raises:
        ValueError: 입력 피처와 타깃의 행 크기가 불일치하거나 DatetimeIndex가 결손된 경우 발생.
    """
    _validate_deployment_inputs(X_test=X_test, y_test=y_test)

    target_directories: Dict[str, Path] = _prepare_artifact_directories(base_path=Path(artifact_root))

    _persist_model_layer(
        champion_result=champion_result,
        feature_names=X_test.columns.tolist(),
        destination_directory=target_directories[MODELS_DIR_NAME],
    )

    if evaluation_figures:
        _persist_evaluation_figures(
            figures=evaluation_figures,
            destination_directory=target_directories[EVALUATION_DIR_NAME],
        )

    _persist_xai_layer(
        shap_result=shap_result,
        evaluation_features=X_test,
        xai_figures=xai_figures,
        figures_directory=target_directories[XAI_FIGURES_DIR_NAME],
        data_directory=target_directories[XAI_DATA_DIR_NAME],
    )

    _persist_strategy_handoff_layer(
        model=champion_result.champion_model,
        X_test=X_test,
        y_test=y_test,
        destination_directory=target_directories[STRATEGY_HANDOFF_DIR_NAME],
    )

    return target_directories

# ==============================================================================
# Internal Helper Functions
# ==============================================================================

def _convert_to_serializable(value: Any) -> Any:
    """JSON 직렬화가 불가능한 객체를 표준 파이썬 기본형 타입으로 재귀 변환합니다."""
    if isinstance(value, (np.integer, np.int64, np.int32)):
        return int(value)
    if isinstance(value, (np.floating, np.float64, np.float32)):
        return float(value)
    if isinstance(value, (np.ndarray, pd.Series)):
        return value.tolist()
    if isinstance(value, (pd.Timestamp, pd.DatetimeIndex)):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _save_joblib(object_to_serialize: Any, destination_path: Path) -> None:
    """joblib 모듈을 사용하여 바이너리 모델 객체를 디스크에 영속화합니다."""
    joblib.dump(object_to_serialize, destination_path)


def _save_json(payload: Dict[str, Any], destination_path: Path) -> None:
    """딕셔너리 구조체를 JSON 파일로 안전하게 직렬화하여 저장합니다."""
    with open(destination_path, "w", encoding="utf-8") as file_buffer:
        json.dump(
            payload,
            file_buffer,
            ensure_ascii=False,
            indent=JSON_INDENT,
            default=_convert_to_serializable,
        )


def _save_parquet(dataframe: pd.DataFrame, destination_path: Path) -> None:
    """데이터프레임을 인덱스를 보존한 상태로 Parquet 포맷으로 디스크에 영속화합니다."""
    dataframe.to_parquet(destination_path, engine=PARQUET_ENGINE, index=True)


def _save_figure(figure: plt.Figure, destination_path: Path) -> None:
    """Matplotlib Figure 객체를 고해상도 이미지 파일로 영속화합니다."""
    figure.savefig(destination_path, dpi=IMAGE_DPI, bbox_inches=IMAGE_BBOX_INCHES)


def _validate_deployment_inputs(X_test: pd.DataFrame, y_test: pd.Series) -> None:
    """입력 피처와 타깃 데이터의 길이 정합성 및 DatetimeIndex 유효성을 검증합니다."""
    if len(X_test) != len(y_test):
        raise ValueError(f"X_test 행 수({len(X_test)})와 y_test 행 수({len(y_test)})가 일치하지 않습니다.")
    if X_test.empty or y_test.empty:
        raise ValueError("배포 대상인 X_test 또는 y_test가 비어 있습니다.")
    if not isinstance(X_test.index, pd.DatetimeIndex):
        raise ValueError("X_test의 인덱스가 DatetimeIndex 형식이 아닙니다.")


def _prepare_artifact_directories(base_path: Path) -> Dict[str, Path]:
    """아티팩트 계층별 물리적 디렉터리 경로를 생성하고 매핑을 반환합니다."""
    directory_mapping: Dict[str, Path] = {
        MODELS_DIR_NAME: base_path / MODELS_DIR_NAME,
        EVALUATION_DIR_NAME: base_path / EVALUATION_DIR_NAME,
        XAI_FIGURES_DIR_NAME: base_path / XAI_DIR_NAME / XAI_FIGURES_DIR_NAME,
        XAI_DATA_DIR_NAME: base_path / XAI_DIR_NAME / XAI_DATA_DIR_NAME,
        STRATEGY_HANDOFF_DIR_NAME: base_path / STRATEGY_HANDOFF_DIR_NAME,
    }

    for target_path in directory_mapping.values():
        target_path.mkdir(parents=True, exist_ok=True)

    return directory_mapping


def _prepare_shap_dataframe(
    raw_shap_values: Any,
    index: pd.Index,
    columns: List[str],
) -> pd.DataFrame:
    """원시 SHAP 다차원 배열을 DatetimeIndex 기반 2차원 데이터프레임으로 변환합니다."""
    if isinstance(raw_shap_values, pd.DataFrame):
        shap_dataframe: pd.DataFrame = raw_shap_values.copy()
        shap_dataframe.index = index
        return shap_dataframe

    extracted_array: np.ndarray = np.asarray(raw_shap_values)
    if extracted_array.ndim == 3:
        extracted_array = extracted_array[:, :, 0]

    return pd.DataFrame(data=extracted_array, index=index, columns=columns)


def _resolve_or_compute_importance_report(
    shap_result: Any,
    shap_dataframe: pd.DataFrame,
    evaluation_features: pd.DataFrame,
) -> pd.DataFrame:
    """shap_result 객체에서 중요도 감사표를 추출하거나 원시 SHAP 행렬로부터 표준 감사표를 도출합니다."""
    # [설계 의도] 기 산출된 중요도 보고서가 표준 컬럼("Feature Name", "Signal Corr")을 모두 갖춘 경우 즉시 반환
    for attr_candidate in [
        "feature_importance_report",
        "importance_report",
        "global_importance_report",
    ]:
        if hasattr(shap_result, attr_candidate):
            candidate_obj = getattr(shap_result, attr_candidate)
            if (
                isinstance(candidate_obj, pd.DataFrame)
                and not candidate_obj.empty
                and "Feature Name" in candidate_obj.columns
                and "Signal Corr" in candidate_obj.columns
            ):
                return candidate_obj

    # [설계 의도] Feature Name 컬럼 명시, SHAP 변동성(Std) 및 신호 상관계수(Signal Corr)를 결합하여 loader 호환 표준 감사표 생성
    mean_abs_shap = np.abs(shap_dataframe.values).mean(axis=0)
    std_shap = np.std(shap_dataframe.values, axis=0)
    total_importance = float(np.sum(mean_abs_shap)) if np.sum(mean_abs_shap) > 0 else 1.0

    records: List[Dict[str, Any]] = []
    for idx, feature_col in enumerate(shap_dataframe.columns):
        col_shap = shap_dataframe[feature_col].values
        col_feature = evaluation_features[feature_col].values

        valid_mask = np.isfinite(col_feature) & np.isfinite(col_shap)
        corr_val: float = 0.0
        if np.sum(valid_mask) > 1 and np.std(col_feature[valid_mask]) > 0 and np.std(col_shap[valid_mask]) > 0:
            corr_val = float(np.corrcoef(col_feature[valid_mask], col_shap[valid_mask])[0, 1])

        records.append({
            "Feature Name": feature_col,
            "Mean |SHAP|": float(mean_abs_shap[idx]),
            "Contribution Ratio": float(mean_abs_shap[idx] / total_importance * 100.0),
            "SHAP Std": float(std_shap[idx]),
            "Signal Corr": corr_val,
        })

    report_dataframe = pd.DataFrame(records).sort_values(by="Mean |SHAP|", ascending=False).reset_index(drop=True)
    report_dataframe["Rank"] = report_dataframe.index + 1
    return report_dataframe


def _extract_champion_metadata(champion_result: Any, feature_names: List[str]) -> Dict[str, Any]:
    """챔피언 선별 결과로부터 피처 목록, 하이퍼파라미터 및 5대 게이트 리포트를 추출합니다."""
    model_instance: Any = champion_result.champion_model
    hyperparameters: Dict[str, Any] = {}
    if hasattr(model_instance, "get_params"):
        hyperparameters = model_instance.get_params()

    metadata: Dict[str, Any] = {
        "model_name": str(getattr(champion_result, "champion_model_name", "champion_regressor")),
        "feature_names": feature_names,
        "feature_count": len(feature_names),
        "hyperparameters": hyperparameters,
    }

    if hasattr(champion_result, "champion_summary_report") and isinstance(champion_result.champion_summary_report, pd.DataFrame):
        metadata["champion_summary_report"] = champion_result.champion_summary_report.to_dict(orient="records")
    if hasattr(champion_result, "audit_report") and isinstance(champion_result.audit_report, pd.DataFrame):
        metadata["audit_report"] = champion_result.audit_report.to_dict(orient="records")

    return metadata


def _extract_xai_summary(shap_result: Any, sample_count: int) -> Dict[str, Any]:
    """ShapResult 객체로부터 기댓값, 표본 크기 및 가산성 공리 오차를 추출합니다."""
    base_value_raw: Any = getattr(shap_result, "base_value", 0.0)
    base_value: float = float(np.mean(base_value_raw))

    # [설계 의도] ShapResult.additivity_audit 객체로부터 직접 수치를 획득하고, 부재 시 리포트 DataFrame 파싱
    max_additivity_error: Optional[float] = None
    if hasattr(shap_result, "additivity_audit") and shap_result.additivity_audit is not None:
        max_additivity_error = float(shap_result.additivity_audit.maximum_absolute_error)
    else:
        for audit_candidate in ["audit_summary_report", "axiom_report", "additivity_report"]:
            if hasattr(shap_result, audit_candidate):
                audit_obj = getattr(shap_result, audit_candidate)
                if isinstance(audit_obj, pd.DataFrame) and not audit_obj.empty:
                    for col in ["max_residual", "max_error", "absolute_error_max", "max_additivity_error"]:
                        if col in audit_obj.columns:
                            max_additivity_error = float(audit_obj[col].iloc[0])
                            break
                    if max_additivity_error is not None:
                        break

    bg_samples: int = int(getattr(shap_result, "background_samples_count", getattr(shap_result, "background_sample_size", 0)))

    return {
        "model_name": str(getattr(shap_result, "model_name", "champion_regressor")),
        "base_value_expected_f_x": base_value,
        "evaluation_sample_size": sample_count,
        "background_sample_size": bg_samples,
        "max_additivity_axiom_error": max_additivity_error,
    }


def _build_predictions_contract(
    model: Any,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> pd.DataFrame:
    """챔피언 모델 추론값, 정답 타깃 및 잔차를 결합하여 백테스팅 인계 데이터프레임을 생성합니다."""
    predictions: np.ndarray = model.predict(X_test)
    y_true_values: np.ndarray = y_test.values

    return pd.DataFrame(
        data={
            "target_true": y_true_values,
            "prediction": predictions,
            "residual": y_true_values - predictions,
        },
        index=X_test.index,
    )


def _persist_model_layer(
    champion_result: Any,
    feature_names: List[str],
    destination_directory: Path,
) -> None:
    """챔피언 모델 바이너리와 종합 메타데이터 JSON을 영속화합니다."""
    model_path: Path = destination_directory / CHAMPION_MODEL_FILENAME
    _save_joblib(object_to_serialize=champion_result.champion_model, destination_path=model_path)

    metadata_payload: Dict[str, Any] = _extract_champion_metadata(
        champion_result=champion_result,
        feature_names=feature_names,
    )
    metadata_path: Path = destination_directory / CHAMPION_METADATA_FILENAME
    _save_json(payload=metadata_payload, destination_path=metadata_path)


def _persist_evaluation_figures(
    figures: Dict[str, plt.Figure],
    destination_directory: Path,
) -> None:
    """평가 계층의 덤벨 플롯과 언더워터 플롯 이미지를 저장합니다."""
    key_mapping: Dict[str, str] = {
        "dumbbell": CV_VS_TEST_DUMBBELL_FILENAME,
        "underwater": UNDERWATER_DRAWDOWN_FILENAME,
    }

    for key, figure_obj in figures.items():
        if figure_obj is not None:
            filename: str = key_mapping.get(key, f"{key}.png")
            _save_figure(figure=figure_obj, destination_path=destination_directory / filename)


def _persist_xai_figures(
    figures: Dict[str, plt.Figure],
    destination_directory: Path,
) -> None:
    """5대 핵심 XAI 시각화 이미지를 표준 파일명으로 저장합니다."""
    key_mapping: Dict[str, str] = {
        "global_summary": SHAP_GLOBAL_SUMMARY_FILENAME,
        "interaction": SHAP_DEPENDENCE_FILENAME,
        "waterfall": SHAP_REGIME_WATERFALL_FILENAME,
        "rolling": SHAP_DYNAMIC_ROLLING_FILENAME,
        "inflection": SHAP_RISK_POLICY_FILENAME,
    }

    for key, figure_obj in figures.items():
        if figure_obj is not None:
            filename: str = key_mapping.get(key, f"{key}.png")
            _save_figure(figure=figure_obj, destination_path=destination_directory / filename)


def _persist_xai_layer(
    shap_result: Any,
    evaluation_features: pd.DataFrame,
    xai_figures: Optional[Dict[str, plt.Figure]],
    figures_directory: Path,
    data_directory: Path,
) -> None:
    """XAI 시각화 이미지 및 원시 SHAP 행렬, 감사 보고서 아티팩트를 일괄 영속화합니다."""
    if xai_figures:
        _persist_xai_figures(figures=xai_figures, destination_directory=figures_directory)

    # 1. 원시 SHAP 행렬 Parquet 저장
    shap_dataframe: pd.DataFrame = _prepare_shap_dataframe(
        raw_shap_values=shap_result.shap_values,
        index=evaluation_features.index,
        columns=evaluation_features.columns.tolist(),
    )
    _save_parquet(dataframe=shap_dataframe, destination_path=data_directory / SHAP_VALUES_FILENAME)

    # 2. 피처 중요도 및 신호 감사표 Parquet 저장
    importance_dataframe: pd.DataFrame = _resolve_or_compute_importance_report(
        shap_result=shap_result,
        shap_dataframe=shap_dataframe,
        evaluation_features=evaluation_features,
    )
    _save_parquet(dataframe=importance_dataframe, destination_path=data_directory / FEATURE_IMPORTANCE_FILENAME)

    # 3. [신규 영속화] 리스크 변곡점 컷오프 정책 감사표 Parquet 저장
    if getattr(shap_result, "inflection_policy_result", None) is not None:
        policy_df = shap_result.inflection_policy_result.policy_summary_dataframe
        if isinstance(policy_df, pd.DataFrame) and not policy_df.empty:
            _save_parquet(dataframe=policy_df, destination_path=data_directory / INFLECTION_POLICY_FILENAME)

    # 4. [신규 영속화] 5대 시장 국면 정량 코호트 감사표 Parquet 저장
    if getattr(shap_result, "regime_cohort_result", None) is not None:
        regime_df = shap_result.regime_cohort_result.regime_audit_dataframe
        if isinstance(regime_df, pd.DataFrame) and not regime_df.empty:
            _save_parquet(dataframe=regime_df, destination_path=data_directory / REGIME_COHORT_AUDIT_FILENAME)

    # 5. 요약 통계 JSON 저장
    xai_summary_payload: Dict[str, Any] = _extract_xai_summary(
        shap_result=shap_result,
        sample_count=len(evaluation_features),
    )
    _save_json(payload=xai_summary_payload, destination_path=data_directory / XAI_SUMMARY_FILENAME)


def _persist_strategy_handoff_layer(
    model: Any,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    destination_directory: Path,
) -> None:
    """백테스팅 연동용 피처-타깃 정답 행렬과 모델 예측 계약 Parquet을 영속화합니다."""
    features_and_target: pd.DataFrame = X_test.copy()
    target_name: str = str(y_test.name) if y_test.name is not None else TARGET_COLUMN_FALLBACK
    features_and_target[target_name] = y_test.values
    _save_parquet(
        dataframe=features_and_target,
        destination_path=destination_directory / TEST_FEATURES_TARGET_FILENAME,
    )

    prediction_contract: pd.DataFrame = _build_predictions_contract(
        model=model,
        X_test=X_test,
        y_test=y_test,
    )
    _save_parquet(
        dataframe=prediction_contract,
        destination_path=destination_directory / TEST_PREDICTIONS_FILENAME,
    )