import copy
from typing import Any, Dict, List
import pandas as pd


# ==============================================================================
# Constants & Configuration
# ==============================================================================
# [탐색 공간 경계 감사 리포트 스키마 및 속성 설정]
ALGORITHM_COLUMN_NAME: str = "알고리즘 (Algorithm)"           # 경계 감사표 내 모델 식별 컬럼명
PARAMETER_COLUMN_NAME: str = "파라미터 명칭"                  # 경계 감사표 내 하이퍼파라미터 식별 컬럼명
BOUNDARY_HIT_ATTR_NAME: str = "has_boundary_hits"             # 결과 DTO 내 경계 도달 여부 플래그 속성명
BOUNDARY_DF_ATTR_NAME: str = "boundary_audit_dataframe"       # 결과 DTO 내 경계 감사 데이터프레임 속성명

# [전통 머신러닝(ML) 4종 기본 HPO 탐색 공간 설정]
ML_SEARCH_SPACES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "ElasticNet": {
        "alpha": {"type": "float", "low": 1e-3, "high": 2.0, "log": True},
        "l1_ratio": {"type": "float", "low": 0.01, "high": 0.99, "step": 0.01},
    },
    "XGBoost": {
        "objective": {
            "type": "categorical",
            "choices": ["reg:squarederror", "reg:pseudohubererror", "reg:absoluteerror"],
        },
        "n_estimators": {"type": "int", "low": 50, "high": 500, "step": 25},
        "max_depth": {"type": "int", "low": 2, "high": 4, "step": 1},
        "learning_rate": {"type": "float", "low": 0.005, "high": 0.20, "log": True},
        "min_child_weight": {"type": "int", "low": 10, "high": 30, "step": 1},
        "gamma": {"type": "float", "low": 1e-4, "high": 5.0, "log": True},
        "subsample": {"type": "float", "low": 0.50, "high": 1.00, "step": 0.05},
        "colsample_bytree": {"type": "float", "low": 0.40, "high": 1.00, "step": 0.05},
        "reg_alpha": {"type": "float", "low": 1e-3, "high": 10.0, "log": True},
        "reg_lambda": {"type": "float", "low": 1e-3, "high": 10.0, "log": True},
    },
    "RandomForest": {
        "n_estimators": {"type": "int", "low": 100, "high": 500, "step": 50},
        "max_depth": {"type": "int", "low": 2, "high": 5, "step": 1},
        "min_samples_split": {"type": "int", "low": 20, "high": 60, "step": 2},
        "min_samples_leaf": {"type": "int", "low": 10, "high": 30, "step": 1},
        "max_features": {"type": "float", "low": 0.30, "high": 1.00, "step": 0.05},
    },
    "CatBoost": {
        "loss_function": {
            "type": "categorical",
            "choices": ["RMSE", "MAE", "Huber:delta=1.0"],
        },
        # [설계 의도] 저표본(Low-ESS) 금융 시계열에서 대칭 트리(Oblivious Tree)의 고차 교차항 암기 및
        # 후기 잔차 과적합을 차단하기 위해 트리 깊이(2~4)와 부스팅 스텝을 제한하고 L2/분할 무작위성 규제를 강화함
        # (근거: Prokhorenkova et al., NeurIPS 2018; Gu, Kelly, & Xiu, RFS 2020)
        "iterations": {"type": "int", "low": 50, "high": 350, "step": 25},
        "depth": {"type": "int", "low": 2, "high": 4, "step": 1},
        "learning_rate": {"type": "float", "low": 0.005, "high": 0.08, "log": True},
        "l2_leaf_reg": {"type": "float", "low": 1.0, "high": 30.0, "log": True},
        "random_strength": {"type": "float", "low": 0.5, "high": 15.0, "log": True},
    },
}

# [딥러닝(DL) 4종 기본 HPO 탐색 공간 설정]
DL_SEARCH_SPACES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "TabularResNet": {
        # [설계 의도] 소수 정예 피처(8개) 환경에서 과매개변수화 및 무검증(X_val=None) 100 에포크 과적합을 방지하기 위해
        # 은닉 차원·블록 깊이를 경량화하고 스펙트럼 조기 종료(max_epochs 25~50) 및 그래디언트 클리핑을 공통 적용함
        # (근거: Gorishniy et al., NeurIPS 2021; Kadra et al., NeurIPS 2021; Yao et al., 2007)
        "hidden_dim": {"type": "categorical", "choices": [32, 64, 128]},
        "num_blocks": {"type": "int", "low": 1, "high": 2, "step": 1},
        "dropout_rate": {"type": "float", "low": 0.20, "high": 0.50, "step": 0.05},
        "learning_rate": {"type": "float", "low": 1e-4, "high": 2e-3, "log": True},
        "weight_decay": {"type": "float", "low": 5e-4, "high": 1e-1, "log": True},
        "batch_size": {"type": "categorical", "choices": [64, 128]},
        "max_epochs": {"type": "int", "low": 25, "high": 50, "step": 5},
        "grad_clip_norm": {"type": "float", "low": 0.50, "high": 1.00, "step": 0.25},
    },
    "DCNv2": {
        # [설계 의도] 고차 다항식 교차항의 외삽 폭발(GDR·RIR 급증)을 차단하기 위해 Cross Layer를 1~2층으로 제한하고,
        # 강한 L2 정규화 하한(1e-3)과 에포크 상한 제어(25~50)를 결합하여 일반화 안정성과 탐색 속도를 동시에 확보함
        # (근거: Wang et al., WWW 2021; Grinsztajn et al., NeurIPS 2022; Yao et al., 2007)
        "num_cross_layers": {"type": "int", "low": 1, "high": 2, "step": 1},
        "deep_hidden_dims": {
            "type": "categorical",
            "choices": [(32, 16), (64, 32), (64, 64)],
        },
        "dropout_rate": {"type": "float", "low": 0.25, "high": 0.50, "step": 0.05},
        "learning_rate": {"type": "float", "low": 1e-4, "high": 2e-3, "log": True},
        "weight_decay": {"type": "float", "low": 1e-3, "high": 1e-1, "log": True},
        "batch_size": {"type": "categorical", "choices": [64, 128]},
        "max_epochs": {"type": "int", "low": 25, "high": 50, "step": 5},
        "grad_clip_norm": {"type": "float", "low": 0.50, "high": 1.00, "step": 0.25},
    },
    "FTTransformer": {
        # [설계 의도] 어텐션 헤드당 최소 차원(d_k >= 4) 보장을 위해 d_token을 [16, 32]로 정렬하고,
        # 무검증 100 에포크 MSE 학습에 의한 팻테일(Kurtosis=7.01) 암기(OOF RMSE 과소화로 인한 RIR 폭발)를 막기 위해
        # 에포크 상한(20~40)과 강한 그래디언트 클리핑(0.25~0.50, Huber 유사 효과) 및 L2 감쇠(>=5e-3)를 강제함
        # (근거: Gorishniy et al., NeurIPS 2021; Advani et al., 2020; Zhang et al., ICLR 2020)
        "d_token": {"type": "categorical", "choices": [16, 32]},
        "num_heads": {"type": "categorical", "choices": [2, 4]},
        "num_layers": {"type": "int", "low": 1, "high": 2, "step": 1},
        "ffn_factor": {"type": "float", "low": 0.75, "high": 1.25, "step": 0.25},
        "dropout_rate": {"type": "float", "low": 0.25, "high": 0.45, "step": 0.05},
        "learning_rate": {"type": "float", "low": 1e-4, "high": 4e-4, "log": True},
        "weight_decay": {"type": "float", "low": 5e-3, "high": 1e-1, "log": True},
        "batch_size": {"type": "categorical", "choices": [64, 128]},
        "max_epochs": {"type": "int", "low": 20, "high": 40, "step": 5},
        "grad_clip_norm": {"type": "float", "low": 0.25, "high": 0.50, "step": 0.25},
    },
    "TCN": {
        # [설계 의도] 채널 단위 드롭아웃(nn.Dropout1d)과 BatchNorm1d 결합 시 발생하는 추론 분산 왜곡(Variance Shift)을
        # 차단하기 위해 배치 정규화를 비활성화(use_batch_norm=False)하고 채널 드롭아웃을 적정 범위(0.15~0.35)로 조정하며,
        # 20일 시계열 수용장(seq_len 10~20, 채널 16~32)과 에포크 제한(20~40)으로 예측력(Score)과 RIR·GDR을 동시 확보함
        # (근거: Bai, Kolter, & Koltun, arXiv:1803.01271; Li et al., CVPR 2019; Yao et al., 2007)
        "sequence_length": {"type": "int", "low": 10, "high": 20, "step": 5},
        "hidden_channels": {
            "type": "categorical",
            "choices": [(16, 16), (32, 16), (32, 32)],
        },
        "kernel_size": {"type": "categorical", "choices": [2, 3]},
        "use_batch_norm": {"type": "categorical", "choices": [False]},
        "dropout_rate": {"type": "float", "low": 0.15, "high": 0.35, "step": 0.05},
        "learning_rate": {"type": "float", "low": 2e-4, "high": 1e-3, "log": True},
        "weight_decay": {"type": "float", "low": 5e-3, "high": 1e-1, "log": True},
        "batch_size": {"type": "categorical", "choices": [64, 128]},
        "max_epochs": {"type": "int", "low": 20, "high": 40, "step": 5},
        "grad_clip_norm": {"type": "float", "low": 0.25, "high": 0.50, "step": 0.25},
    },
}

# [전체 8종 단일 회귀 모델 통합 HPO 탐색 공간 기본 템플릿]
DEFAULT_SEARCH_SPACES: Dict[str, Dict[str, Dict[str, Any]]] = {
    **ML_SEARCH_SPACES,
    **DL_SEARCH_SPACES,
}


# ==============================================================================
# Public API Functions
# ==============================================================================
def get_search_spaces() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """전체 단일 회귀 모델(ML 4종 및 DL 4종)의 기본 HPO 탐색 공간 깊은 복사본을 반환합니다.

    Returns:
        Dict[str, Dict[str, Dict[str, Any]]]: 모델 식별명을 키로 하는 파라미터 탐색 범위 딕셔너리.
    """
    # 1. 외부 수정에 의한 원본 탐색 공간 오염 방지를 위해 깊은 복사본 반환
    return copy.deepcopy(DEFAULT_SEARCH_SPACES)


def audit_search_space_boundaries(hpo_results: Dict[str, Any]) -> pd.DataFrame:
    """각 모델별 HPO 결과에서 탐색 공간 경계값에 도달한 파라미터를 단일 감사표로 통합합니다.

    Args:
        hpo_results (Dict[str, Any]): 모델명을 키로 하고 최적화 결과 DTO를 값으로 갖는 딕셔너리.

    Returns:
        pd.DataFrame: 경계 도달 파라미터 통합 감사 데이터프레임 (해당 항목이 없을 경우 빈 DataFrame).
    """
    # 1. 모델별 최적화 결과에서 경계 도달이 발생한 감사 데이터프레임 목록 추출
    boundary_audit_frames: List[pd.DataFrame] = _extract_boundary_audit_frames(
        hpo_results=hpo_results
    )

    # 2. 추출된 감사 데이터프레임을 단일 테이블로 병합 및 인덱스 정렬 후 반환
    return _consolidate_audit_dataframes(audit_frames=boundary_audit_frames)


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _extract_boundary_audit_frames(hpo_results: Dict[str, Any]) -> List[pd.DataFrame]:
    """최적화 결과 딕셔너리에서 경계값 도달 플래그가 활성화된 감사 데이터프레임만 추출합니다."""
    # 1. 결과 DTO를 순회하며 경계 도달(has_boundary_hits)이 참인 데이터프레임만 필터링하여 반환
    return [
        getattr(result, BOUNDARY_DF_ATTR_NAME)
        for result in hpo_results.values()
        if getattr(result, BOUNDARY_HIT_ATTR_NAME, False)
    ]


def _consolidate_audit_dataframes(audit_frames: List[pd.DataFrame]) -> pd.DataFrame:
    """개별 모델의 경계 감사 데이터프레임 리스트를 단일 멀티인덱스 데이터프레임으로 병합합니다."""
    # 1. 경계에 도달한 모델이 하나도 없는 경우 즉시 빈 데이터프레임 반환
    if not audit_frames:
        return pd.DataFrame()

    # 2. 추출된 데이터프레임 리스트를 행 방향으로 통합
    consolidated_audit_df: pd.DataFrame = pd.concat(audit_frames, ignore_index=True)

    # 3. 필수 식별 컬럼이 존재하는 경우 알고리즘 및 파라미터 명칭을 멀티 인덱스로 설정하여 반환
    index_columns: List[str] = [ALGORITHM_COLUMN_NAME, PARAMETER_COLUMN_NAME]
    if all(col in consolidated_audit_df.columns for col in index_columns):
        consolidated_audit_df.set_index(index_columns, inplace=True)

    return consolidated_audit_df