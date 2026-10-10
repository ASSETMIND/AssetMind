import copy
import os
from typing import Any, Dict, Optional, Union
import joblib
import pandas as pd


def save_champion_dataset(
    champion_partitions: Union[Dict[str, Any], Dict[str, Dict[str, Any]]],
    champion_dataset_id: Optional[str] = None,
    output_artifact_path: str = "champion_dataset.pkl",
) -> Dict[str, Any]:
    """챔피언 데이터셋 파티션을 로컬 파일로 직렬화 저장하고 5대 파티션 무결성을 검증합니다.

    Args:
        champion_partitions (Union[Dict[str, Any], Dict[str, Dict[str, Any]]]):
            최종 정예화 완료 파티션(refined_champion_partitions) 또는
            model_ready_repository 저장소.
        champion_dataset_id (Optional[str]):
            저장소에서 버킷을 추출할 경우 사용할 챔피언 ID (기본값: None).
        output_artifact_path (str):
            저장할 아티팩트 파일 경로 (기본값: "champion_dataset.pkl").

    Returns:
        Dict[str, Any]: 저장 파일 크기 및 파티션별 Shape 메타데이터 딕셔너리.
    """
    # 1. 원본 메모리 보호를 위한 deepcopy 및 대상 파티션 추출
    if champion_dataset_id is not None and champion_dataset_id in champion_partitions:
        partitions: Dict[str, Any] = copy.deepcopy(champion_partitions[champion_dataset_id])
    else:
        partitions = copy.deepcopy(champion_partitions)

    # 2. 불필요한 중간 메타데이터 정리
    partitions.pop("_scaled_candidate_pool", None)

    # 3. 파일 직렬화 영속화 (joblib)
    joblib.dump(partitions, output_artifact_path)
    file_size_kb: float = os.path.getsize(output_artifact_path) / 1024.0

    # 4. 역직렬화 무결성 검증 (5대 필수 파티션 확인)
    restored_partitions = joblib.load(output_artifact_path)
    for key in ("X_train", "y_train", "X_test", "y_test", "X_inference"):
        assert key in restored_partitions, f"파티션 무결성 검증 실패: '{key}' 누락"

    return {
        "artifact_path": output_artifact_path,
        "file_size_kb": round(file_size_kb, 2),
        "n_features": restored_partitions["X_train"].shape[1],
        "train_shape": restored_partitions["X_train"].shape,
        "test_shape": restored_partitions["X_test"].shape,
        "inference_shape": restored_partitions["X_inference"].shape,
    }