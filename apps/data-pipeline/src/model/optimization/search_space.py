import copy
from typing import Any, Dict, List

import pandas as pd


# [설계 의도] 3대 회귀 모델 실무 표준 탐색 공간 기본 템플릿
DEFAULT_SEARCH_SPACES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "ElasticNet": {
        "alpha": {"type": "float", "low": 1e-4, "high": 5.0, "log": True},
        "l1_ratio": {"type": "float", "low": 0.01, "high": 0.99}
    },
    "XGBoost": {
        "objective": {
            "type": "categorical",
            "choices": ["reg:squarederror", "reg:pseudohubererror", "reg:absoluteerror"]
        },
        "n_estimators": {"type": "int", "low": 50, "high": 350, "step": 20},
        "max_depth": {"type": "int", "low": 2, "high": 4, "step": 1},
        "learning_rate": {"type": "float", "low": 0.005, "high": 0.20, "log": True},
        "min_child_weight": {"type": "int", "low": 1, "high": 15, "step": 1},
        "gamma": {"type": "float", "low": 1e-3, "high": 5.0, "log": True},
        "subsample": {"type": "float", "low": 0.60, "high": 1.00},
        "colsample_bytree": {"type": "float", "low": 0.50, "high": 1.00},
        "reg_alpha": {"type": "float", "low": 1e-3, "high": 10.0, "log": True},
        "reg_lambda": {"type": "float", "low": 1e-3, "high": 10.0, "log": True}
    },
    "RandomForest": {
        "criterion": {
            "type": "categorical",
            "choices": ["squared_error", "friedman_mse"]
        },
        "n_estimators": {"type": "int", "low": 100, "high": 400, "step": 25},
        "max_depth": {"type": "int", "low": 2, "high": 7, "step": 1},
        "min_samples_split": {"type": "int", "low": 2, "high": 40, "step": 2},
        "min_samples_leaf": {"type": "int", "low": 1, "high": 10, "step": 1},
        "max_features": {"type": "float", "low": 0.20, "high": 1.00}
    }
}


def get_search_spaces() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    3대 모델의 기본 HPO 탐색 공간 딕셔너리의 깊은 복사본(Deepcopy)을 반환합니다.
    
    Returns:
        Dict[str, Dict[str, Dict[str, Any]]]: 모델명을 키로 하는 파라미터 탐색 범위 딕셔너리
    """
    # [설계 의도] 원본 불변성 보장을 위해 deepcopy 반환 (노트북에서 자유롭게 수정 가능)
    return copy.deepcopy(DEFAULT_SEARCH_SPACES)

def audit_search_space_boundaries(hpo_results: Dict[str, Any]) -> pd.DataFrame:
    """
    각 모델별 HPO 결과에서 탐색 공간의 경계값에 도달하여 추가 확장이 필요한 파라미터를 단일 감사표로 통합합니다.

    Args:
        hpo_results: 모델명을 키로 하고 TimeSeriesOptimizationResult DTO를 값으로 갖는 딕셔너리

    Returns:
        pd.DataFrame: 경계 도달 파라미터 통합 감사 데이터프레임 (도달 항목이 없을 경우 빈 DataFrame 반환)
    """
    # [설계 의도] 파라미터가 탐색 공간의 상/하한에 걸려 최적해 수렴이 제한된 경우를 감지하여 리포팅
    boundary_audit_frames: List[pd.DataFrame] = [
        res.boundary_audit_dataframe
        for res in hpo_results.values()
        if hasattr(res, "has_boundary_hits") and res.has_boundary_hits
    ]

    if not boundary_audit_frames:
        return pd.DataFrame()

    consolidated_audit_df = pd.concat(boundary_audit_frames, ignore_index=True)
    if "알고리즘 (Algorithm)" in consolidated_audit_df.columns and "파라미터 명칭" in consolidated_audit_df.columns:
        consolidated_audit_df.set_index(["알고리즘 (Algorithm)", "파라미터 명칭"], inplace=True)

    return consolidated_audit_df