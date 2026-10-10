"""
[모듈 목적 및 상세 설명]
금융 시계열 파이프라인의 데이터 누수(Look-ahead Bias / Data Leakage)를 수리적으로 완벽히 차단하며, 
모델 학습 및 검증을 위해 데이터를 시간 순서에 따라 분할하는 DatasetSplitter 모듈입니다.
미래 1개월 Horizon(T+20) 타겟 중복에 따른 오버피팅을 방지하기 위해 Purged Embargo Gap을 격리하며, 
정답 라벨(y) 미도래 구간인 최신 20영업일은 실시간 추론 전용(X_inference) 데이터로 분리합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: Gold Feature Engineering 완료 통합 데이터프레임(`df: pd.DataFrame`).
2. Inference Isolation: 미래 T+20 타겟이 NaN인 최신 N거래일(20일)을 `X_inference`로 사전 격리.
3. Feature & Target Isolation: 정답 라벨(`target_return_20d`)을 y로 분리하고, 지정된 제외 피처(`exclude_features`)를 X 행렬에서 제거.
4. Time-series Partitioning: 설정된 모드(`train_test` 또는 `train_val_test`)에 맞춰 시간 순서대로 파티션 분할 및 Purged Gap 삽입.
5. Output: 분할된 X, y 데이터프레임/시리즈 패키지 딕셔너리(`Dict[str, Union[pd.DataFrame, pd.Series]]`) 반환.

주요 기능:
- [Data Leakage Prevention via Purged Gap] Train과 Test(또는 Val) 경계면에 20영업일 Purged Gap을 물리적으로 버려 미래 정보 유출 차단.
- [Inference Set Isolation] 정답 미도래 최신 20일 구간을 X_inference로 독립 적재하여 라이브 추론 준비.
- [Flexible Feature Exclusion] 사용자 지정 제외 피처 명단(exclude_features)을 X 행렬 구축 시 동적으로 제거.
- [Structured Audit Reporting] summarize() 메서드를 통해 분할 상태 메타데이터를 구조화된 pd.DataFrame으로 사출.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- Purged Gap 데이터 삭제 vs 학습 데이터 보유량 극대화:
  - 장점: 20일간의 데이터를 차단하여 Look-ahead Bias로 인한 백테스팅 오버피팅 착시 현상을 수리적으로 100% 예방함.
  - 단점: Train/Test 경계면당 20영업일의 유효 시계열 샘플 손실 발생.
  - 근거: 금융 시계열 모델링에서 데이터 누수로 인한 백테스팅 신뢰성 붕괴 방지가 샘플 20개 보존보다 압도적으로 중요함.
"""

import math
from typing import Dict, List, Optional, Tuple, Union
import pandas as pd

from src.common.exceptions import DatasetSplitExecutionError

VALID_MODES: List[str] = ["train_test", "train_val_test"]

class DatasetSplitter:
    """금융 시계열 데이터 누수 방지 및 파티션 분할을 집행하는 엔진 클래스입니다."""
    def __init__(
        self,
        split_ratios: Union[Tuple[float, ...], List[float]] = (0.8, 0.2),
        target_column: str = "target_return_20d",
        exclude_features: Optional[Union[str, List[str]]] = None,
        forecast_horizon: int = 20
    ) -> None:
        """DatasetSplitter 생성자 메서드입니다.

        Args:
            split_ratios (Union[Tuple[float, ...], List[float]]): 분할 비율 배열 ((0.8, 0.2) 또는 (0.6, 0.2, 0.2)). Defaults to (0.8, 0.2).
            target_column (str): 예측 대상 정답 타겟 컬럼명. Defaults to 'target_return_20d'.
            exclude_features (Optional[Union[str, List[str]]]): X 행렬 구축 시 제외할 피처 컬럼명 또는 리스트. Defaults to None.
            forecast_horizon (int): 예측 Horizon 및 Purged Gap 거래일 수. Defaults to 20.

        Raises:
            DatasetSplitExecutionError: split_ratios 길이가 2/3가 아니거나 합이 1.0이 아닐 경우 발생.
        """
        # 비율 배열의 길이가 2 또는 3인지 검증하여 분할 차수 결정
        if len(split_ratios) not in [2, 3]:
            raise DatasetSplitExecutionError(
                message=f"split_ratios는 2개(Train/Test) 또는 3개(Train/Val/Test) 요소여야 합니다. (유입: {len(split_ratios)}개)",
                forecast_horizon=forecast_horizon
            )

        # 부동소수점 오차를 고려해 비율 합계가 1.0인지 검증
        if not math.isclose(sum(split_ratios), 1.0, rel_tol=1e-5):
            raise DatasetSplitExecutionError(
                message=f"split_ratios의 합은 1.0이어야 합니다. (현재 합계: {sum(split_ratios):.4f})",
                forecast_horizon=forecast_horizon
            )

        self.split_ratios = tuple(split_ratios)
        self.target_column = target_column
        self.exclude_features = exclude_features
        self.forecast_horizon = forecast_horizon

    def split(
        self, 
        df: pd.DataFrame
    ) -> Dict[str, Union[pd.DataFrame, pd.Series]]:
        """통합 데이터프레임을 수신하여 시간 순서에 따라 파티션을 분할합니다.

        Args:
            df (pd.DataFrame): 데이터 분할을 수행할 데이터프레임.

        Returns:
            Dict[str, Union[pd.DataFrame, pd.Series]]: 분할된 X, y 데이터 패키지.

        Raises:
            DatasetSplitExecutionError: 필수 컬럼 누락 또는 데이터 수량 부족 시 발생.
        """
        # 1. 필수 타겟 컬럼 존재 여부를 선제 검증
        self._validate_schema(df)

        try:
            # 2. target_column 및 사용자 지정 제외 피처(exclude_features)를 동적으로 파악하여 X 행렬 구축 준비
            drop_target_columns = [self.target_column]
            if self.exclude_features:
                if isinstance(self.exclude_features, str):
                    drop_target_columns.append(self.exclude_features)
                elif isinstance(self.exclude_features, list):
                    drop_target_columns.extend(self.exclude_features)

            # 3. 정답 라벨(y)이 NaN인 최신 N거래일을 X_inference로 사전 격리
            inference_mask = df[self.target_column].isna()
            feature_matrix_all = df.drop(columns=drop_target_columns, errors="ignore")
            X_inference = feature_matrix_all[inference_mask].iloc[-self.forecast_horizon:]
            
            # 4. 정답 y가 완벽히 존재하는 과거 유효 데이터셋만 정출
            valid_dataframe = df[~inference_mask].copy()
            feature_matrix = valid_dataframe.drop(columns=drop_target_columns, errors="ignore")
            target_vector = valid_dataframe[self.target_column]

            # 5. split_ratios 배열 길이에 따라 2단 또는 3단 분할 동적 위임
            if len(self.split_ratios) == 2:
                return self._split_train_test(
                    feature_matrix=feature_matrix,
                    target_vector=target_vector,
                    X_inference=X_inference
                )
            else:
                return self._split_train_val_test(
                    feature_matrix=feature_matrix,
                    target_vector=target_vector,
                    X_inference=X_inference
                )

        except DatasetSplitExecutionError:
            # 이미 커스텀 예외로 래핑된 경우는 그대로 상위 전파
            raise
        except Exception as original_error:
            # 연산 도중 발생한 예외를 DatasetSplitExecutionError 구조화 예외로 재래핑하여 원인 추적성 보장
            raise DatasetSplitExecutionError(
                message=f"시계열 데이터셋 분할 연산 중 크래시 발생: {str(original_error)}",
                split_mode=self.mode,
                forecast_horizon=self.forecast_horizon,
                original_exception=original_error
            ) from original_error

    def summarize(
        self, 
        split_datasets: Dict[str, Union[pd.DataFrame, pd.Series]]
    ) -> pd.DataFrame:
        """분할된 파티션 패키지의 상태와 메타데이터를 구조화된 pd.DataFrame으로 사출합니다.

        Args:
            split_datasets (Dict[str, Union[pd.DataFrame, pd.Series]]): split() 메서드의 반환 결과물.

        Returns:
            pd.DataFrame: 파티션 명칭, 기간 범위, 행렬 규격, 역할 비고를 담은 리포트 프레임.
        """
        summary_records = []

        # 파티션 딕셔너리 키를 순회하며 메타데이터(시작일, 종료일, 행x열 셰이프, 역할 설명)를 수집
        for partition_name, data_object in split_datasets.items():
            # DatetimeIndex 기준 시작 및 종료 날짜 추출
            if isinstance(data_object.index, pd.DatetimeIndex) and len(data_object) > 0:
                start_date = data_object.index[0].strftime("%Y-%m-%d")
                end_date = data_object.index[-1].strftime("%Y-%m-%d")
                date_range_str = f"{start_date} ~ {end_date}"
            else:
                date_range_str = "-"

            # 자료구조 타입에 따른 표준 튜플 규격 표기
            if isinstance(data_object, pd.DataFrame):
                rows_count, columns_count = data_object.shape
                shape_str = f"({rows_count:,}, {columns_count:,})"
            elif isinstance(data_object, pd.Series):
                rows_count = len(data_object)
                shape_str = f"{rows_count:,}"
            else:
                shape_str = "-"

            # 파티션 역할 비고 명세 매핑
            role_description = self._get_description(partition_name)

            summary_records.append({
                "Partition": partition_name,
                "Date Range": date_range_str,
                "Shape": shape_str,
                "Role": role_description
            })

        summary_dataframe = pd.DataFrame(summary_records)
        return summary_dataframe

    def _split_train_test(
        self,
        feature_matrix: pd.DataFrame,
        target_vector: pd.Series,
        X_inference: pd.DataFrame
    ) -> Dict[str, Union[pd.DataFrame, pd.Series]]:
        """Train / Purged Gap / Test 2단 분할을 연산하는 내부 헬퍼 메서드입니다."""
        total_rows = len(feature_matrix)
        effective_rows = total_rows - self.forecast_horizon
        
        # 1. 비율 기준 분할 경계 인덱스 및 Purged Gap 종단 인덱스 산출
        train_end_index = int(effective_rows * self.split_ratios[0])
        gap_end_index = train_end_index + self.forecast_horizon

        # 2. Train 파티션 슬라이싱
        X_train = feature_matrix.iloc[:train_end_index]
        y_train = target_vector.iloc[:train_end_index]

        # 3. Purged Gap 격리 (X 행렬만 관리)
        purged_gap = feature_matrix.iloc[train_end_index:gap_end_index]

        # 4. Out-of-Sample Test 파티션 슬라이싱
        X_test = feature_matrix.iloc[gap_end_index:]
        y_test = target_vector.iloc[gap_end_index:]

        return {
            "X_train": X_train,
            "y_train": y_train,
            "purged_gap": purged_gap,
            "X_test": X_test,
            "y_test": y_test,
            "X_inference": X_inference
        }

    def _split_train_val_test(
        self,
        feature_matrix: pd.DataFrame,
        target_vector: pd.Series,
        X_inference: pd.DataFrame
    ) -> Dict[str, Union[pd.DataFrame, pd.Series]]:
        """Train / Purged Gap 1 / Validation / Purged Gap 2 / Test 3단 분할을 연산하는 내부 헬퍼 메서드입니다."""
        total_rows = len(feature_matrix)

        total_gap_rows = self.forecast_horizon * 2
        effective_rows = total_rows - total_gap_rows

        train_length = int(effective_rows * self.split_ratios[0])
        val_length = int(effective_rows * self.split_ratios[1])
        
        # 1. 3단 분할 순차 경계 인덱스 계산 (Train ➔ Gap1 ➔ Validation ➔ Gap2 ➔ Test)
        train_end_index = train_length
        gap1_end_index = train_end_index + self.forecast_horizon
        validation_end_index = gap1_end_index + val_length
        gap2_end_index = validation_end_index + self.forecast_horizon

        # 2. Train 파티션
        X_train = feature_matrix.iloc[:train_end_index]
        y_train = target_vector.iloc[:train_end_index]

        # 3. Purged Gap 1
        purged_gap_1 = feature_matrix.iloc[train_end_index:gap1_end_index]

        # 4. Validation 파티션 (Optuna HPO 및 Early Stopping 전용)
        X_val = feature_matrix.iloc[gap1_end_index:validation_end_index]
        y_val = target_vector.iloc[gap1_end_index:validation_end_index]

        # 5. Purged Gap 2
        purged_gap_2 = feature_matrix.iloc[validation_end_index:gap2_end_index]

        # 6. Test 파티션 (최종 챔피언 검증 단 1회 전용)
        X_test = feature_matrix.iloc[gap2_end_index:]
        y_test = target_vector.iloc[gap2_end_index:]

        return {
            "X_train": X_train,
            "y_train": y_train,
            "purged_gap_1": purged_gap_1,
            "X_val": X_val,
            "y_val": y_val,
            "purged_gap_2": purged_gap_2,
            "X_test": X_test,
            "y_test": y_test,
            "X_inference": X_inference
        }

    def _validate_schema(self, df: pd.DataFrame) -> None:
        """시계열 분할 집행 전 필수 타겟 컬럼의 존재 여부를 검증합니다.

        Args:
            df (pd.DataFrame): 데이터 분할을 진행할 데이터프레임.

        Raises:
            DatasetSplitExecutionError: 필수 타겟 컬럼(target_column)이 데이터프레임에 존재하지 않을 경우 발생.
        """
        # target_column 필수 존재 여부 체크 (exclude_features는 선택적 드랍 대상이므로 미존재 시에도 errors="ignore" 처리)
        if self.target_column not in df.columns:
            raise DatasetSplitExecutionError(
                message=f"시계열 분할을 위한 필수 타겟 컬럼이 존재하지 않습니다: {self.target_column}",
                split_mode=self.mode,
                forecast_horizon=self.forecast_horizon
            )

    @staticmethod
    def _get_description(partition_name: str) -> str:
        """파티션 키 명칭에 따른 역할 설명 문자열을 반환합니다."""
        role_map = {
            "X_train": "모델 가중치 학습용 피처 세트",
            "y_train": "모델 가중치 학습용 타겟 벡터",
            "purged_gap": "데이터 누수 방지용 삭제 구간 (Purged Gap)",
            "purged_gap_1": "데이터 누수 방지용 삭제 구간 1 (Train ➔ Val)",
            "X_val": "하이퍼파라미터 최적화(HPO) 피처 세트",
            "y_val": "하이퍼파라미터 최적화(HPO) 타겟 벡터",
            "purged_gap_2": "데이터 누수 방지용 삭제 구간 2 (Val ➔ Test)",
            "X_test": "최종 검증(Out-of-Sample) 피처 세트",
            "y_test": "최종 검증(Out-of-Sample) 타겟 벡터",
            "X_inference": "실시간 추론 및 페이퍼 트레이딩 피처 세트 (y 결손)"
        }
        return role_map.get(partition_name, "Partition Data")