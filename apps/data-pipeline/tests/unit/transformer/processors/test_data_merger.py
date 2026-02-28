import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

# [Target Modules]
# 실제 프로젝트 구조에 맞게 경로 조정 필요
from src.transformer.processors.data_merger import DataMerger

# [Dependencies & Interfaces]
from src.common.exceptions import (
    MergeKeyNotFoundError,
    MergeColumnCollisionError,
    MergeCardinalityError,
    MergeExecutionError,
    TransformerError
)

# ========================================================================================
# [Fixtures]
# ========================================================================================

@pytest.fixture(autouse=True)
def mock_logger_isolation():
    """Service Class의 로거 격리 픽스처 (로그 출력 차단)."""
    with patch("src.common.log.LogManager.get_logger") as mock_get_logger:
        mock_get_logger.return_value = MagicMock()
        yield mock_get_logger

@pytest.fixture
def mock_config():
    """ConfigManager 객체 모방"""
    return MagicMock()

@pytest.fixture
def base_left_df():
    """병합의 기준이 되는 정상적인 Left DataFrame"""
    return pd.DataFrame({
        "id": [1, 2, 3],
        "value_left": ["A", "B", "C"]
    })

@pytest.fixture
def base_right_df():
    """병합 대상이 되는 정상적인 Right DataFrame (1:1 조인용)"""
    return pd.DataFrame({
        "id": [1, 2, 3, 4],
        "value_right": ["X", "Y", "Z", "W"]
    })

@pytest.fixture
def empty_left_df():
    """로우(Row)가 없는 빈 Left DataFrame 반환"""
    return pd.DataFrame(columns=["id", "value_left"])

# ========================================================================================
# 1. 초기화 테스트 (Initialization)
# ========================================================================================

def test_init_01_valid_initialization(mock_config, base_right_df):
    """[INIT-01] [Standard] 유효한 right_df 및 지원되는 파라미터로 초기화 시 정상 생성"""
    # When
    merger = DataMerger(
        config=mock_config,
        right_df=base_right_df,
        join_type="left",
        on_keys=["id"]
    )
    
    # Then
    assert merger.join_type == "left"
    assert merger.on_keys == ["id"]
    assert merger.right_df.equals(base_right_df)

def test_init_02_invalid_right_df_type(mock_config):
    """[INIT-02] [Defensive] right_df 파라미터에 DataFrame이 아닌 값 주입 시 조기 차단"""
    # When & Then
    with pytest.raises(TransformerError, match="반드시 pandas DataFrame이어야 합니다") as exc_info:
        DataMerger(mock_config, right_df=None, join_type="left", on_keys=["id"])
        
    assert exc_info.value.should_retry is False

def test_init_03_unsupported_join_type(mock_config, base_right_df):
    """[INIT-03] [BVA] 지원하지 않는 join_type 문자열 주입 시 ValueError 발생"""
    # When & Then
    with pytest.raises(ValueError, match="지원하지 않는 join_type 입니다"):
        DataMerger(mock_config, right_df=base_right_df, join_type="cross", on_keys=["id"])

def test_init_04_empty_on_keys(mock_config, base_right_df):
    """[INIT-04] [BVA] 병합 기준 키 on_keys에 빈 리스트 주입 시 ValueError 발생"""
    # When & Then
    with pytest.raises(ValueError, match="최소 1개 이상의 병합 키가 필요합니다"):
        DataMerger(mock_config, right_df=base_right_df, join_type="left", on_keys=[])

# ========================================================================================
# 2. 파이프라인 흐름 및 데이터 검증 테스트 (Flow & Data Verification)
# ========================================================================================

def test_flow_01_left_join_success(mock_config, base_left_df, base_right_df):
    """[FLOW-01] [Standard] 1:1 관계를 만족하는 Left/Right 데이터의 병합 성공 검증"""
    # Given
    merger = DataMerger(mock_config, base_right_df, "left", ["id"])
    
    # When
    result_df = merger.transform(base_left_df)
    
    # Then
    assert len(result_df) == len(base_left_df)
    assert "value_right" in result_df.columns
    assert result_df.loc[result_df["id"] == 1, "value_right"].values[0] == "X"

def test_flow_02_inner_join_n_to_1(mock_config, base_right_df):
    """[FLOW-02] [Standard] N:1 관계(Left에 중복키 존재)의 데이터 병합 성공 검증"""
    # Given: Left에 중복된 ID(1) 존재
    left_df_n = pd.DataFrame({"id": [1, 1, 2], "value_left": ["A1", "A2", "B"]})
    merger = DataMerger(mock_config, base_right_df, "inner", ["id"])
    
    # When
    result_df = merger.transform(left_df_n)
    
    # Then
    assert len(result_df) == 3  # N:1 이므로 카디널리티 폭발 없음
    assert list(result_df["id"]) == [1, 1, 2]

def test_flow_03_outer_join_no_validation(mock_config, base_left_df, base_right_df):
    """[FLOW-03] [Defensive] m:1 제약이 없는 상태에서의 Outer 조인 성공 검증"""
    # Given
    merger = DataMerger(mock_config, base_right_df, "outer", ["id"])
    
    # When
    result_df = merger.transform(base_left_df)
    
    # Then
    # base_left_df에는 ID 4가 없으나 outer 조인이므로 ID 4가 포함되어 결과는 4로우여야 함
    assert len(result_df) == 4
    assert result_df["id"].nunique() == 4

def test_edge_01_empty_left_dataframe(mock_config, empty_left_df, base_right_df):
    """[EDGE-01] [BVA] 행(Row)이 0개인 빈 Left DataFrame 병합 통과 검증"""
    # Given
    merger = DataMerger(mock_config, base_right_df, "left", ["id"])
    
    # When
    result_df = merger.transform(empty_left_df)
    
    # Then
    assert result_df.empty
    assert "value_right" in result_df.columns  # 스키마는 정상적으로 결합되어야 함

# ========================================================================================
# 3. 스키마 검증 테스트 (Schema Validation)
# ========================================================================================

def test_val_01_missing_key_in_left(mock_config, base_left_df, base_right_df):
    """[VAL-01] [Defensive] left_df에 on_keys로 지정된 컬럼 누락 시 에러 발생"""
    # Given: Left DF에서 기준 키 삭제
    invalid_left = base_left_df.drop(columns=["id"])
    merger = DataMerger(mock_config, base_right_df, "left", ["id"])
    
    # When & Then
    with pytest.raises(MergeKeyNotFoundError, match="Left 데이터프레임에 없습니다"):
        merger.transform(invalid_left)

def test_val_02_missing_key_in_right(mock_config, base_left_df, base_right_df):
    """[VAL-02] [Defensive] right_df에 on_keys로 지정된 컬럼 누락 시 에러 발생"""
    # Given: Right DF에서 기준 키 삭제 후 초기화
    invalid_right = base_right_df.drop(columns=["id"])
    merger = DataMerger(mock_config, invalid_right, "left", ["id"])
    
    # When & Then
    with pytest.raises(MergeKeyNotFoundError, match="Right 데이터프레임에 없습니다"):
        merger.transform(base_left_df)

def test_val_03_column_collision(mock_config, base_left_df, base_right_df):
    """[VAL-03] [Defensive] 조인 키를 제외하고 양쪽에 동일한 이름의 컬럼 존재 시 에러 발생"""
    # Given: 양쪽에 'status'라는 중복 컬럼 강제 생성 (스키마 오염 원인)
    base_left_df["status"] = "active"
    base_right_df["status"] = "inactive"
    
    merger = DataMerger(mock_config, base_right_df, "left", ["id"])
    
    # When & Then
    with pytest.raises(MergeColumnCollisionError, match="스키마 오염이 예상됩니다"):
        merger.transform(base_left_df)

# ========================================================================================
# 4. 예외 처리 테스트 (Error Handling)
# ========================================================================================

def test_err_01_cardinality_explosion_mn_join(mock_config, base_left_df):
    """[ERR-01] [Fault Injection] Right 데이터에 조인 키가 중복되어 M:N 카디널리티 폭발 발생 시 차단"""
    # Given: Right DF에 ID 1이 두 번 등장하도록 조작 (Left에도 ID 1이 있으므로 1:N -> M:N 위험)
    right_df_duplicate = pd.DataFrame({
        "id": [1, 1, 2],
        "value_right": ["X1", "X2", "Y"]
    })
    
    # join_type="left"일 경우 validate='m:1' 제약조건이 활성화됨
    merger = DataMerger(mock_config, right_df_duplicate, "left", ["id"])
    
    # When & Then
    with pytest.raises(MergeCardinalityError, match="카디널리티 제약 조건 위반"):
        merger.transform(base_left_df)

@patch("src.transformer.processors.data_merger.pd.merge")
def test_err_02_system_execution_error(mock_pd_merge, mock_config, base_left_df, base_right_df):
    """[ERR-02] [Fault Injection] pd.merge 호출 중 런타임/시스템 에러 발생 시 래핑 검증"""
    # Given
    # 내부 pandas 병합 엔진에서 메모리 초과 등 예상치 못한 시스템 에러 발생 시뮬레이션
    mock_pd_merge.side_effect = MemoryError("System Out Of Memory")
    merger = DataMerger(mock_config, base_right_df, "left", ["id"])
    
    # When & Then
    with pytest.raises(MergeExecutionError, match="치명적 오류 발생") as exc_info:
        merger.transform(base_left_df)
        
    assert isinstance(exc_info.value.original_exception, MemoryError)

# ========================================================================================
# 5. 상태 및 멱등성 테스트 (State & Idempotency)
# ========================================================================================

def test_stat_01_idempotency_and_state_immutability(mock_config, base_left_df, base_right_df):
    """[STAT-01] [Idempotency] 단일 인스턴스에 대해 여러 번 호출해도 상태(right_df)가 오염되지 않음"""
    # Given
    merger = DataMerger(mock_config, base_right_df, "left", ["id"])
    original_right_shape = base_right_df.shape
    
    # When: 동일한 입력으로 3회 연속 호출
    result_1 = merger.transform(base_left_df)
    result_2 = merger.transform(base_left_df)
    result_3 = merger.transform(base_left_df)
    
    # Then
    assert result_1.equals(result_2) and result_2.equals(result_3)
    
    # 상태 불변성 검증: 내부 right_df가 원본 형태와 정확히 일치하는지 확인
    assert merger.right_df.shape == original_right_shape
    assert merger.right_df.equals(base_right_df)