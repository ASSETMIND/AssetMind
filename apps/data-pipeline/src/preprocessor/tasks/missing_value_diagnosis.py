"""
[MissingValueDiagnosisTask]

[슬라이딩 윈도우 내 고차원 다변량 금융 시계열의 시공간적 결측 패턴을 진단하여 하위 ML 모델용 통계적 마스크 및 가중치를 생성하는 단일 태스크]

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 클렌징 레이어를 통과하여 유입된, 셰이프가 물리적으로 보존된 상태의 원본 시계열 데이터프레임 (인덱스: 타임스탬프, 컬럼: 190종 이상의 자산코드).
2. Initialization: 인스턴스 기동 시 슬라이딩 룩백 윈도우 크기(20일), 단기/장기 결측 판단을 위한 비율 임계치(10%, 25%), 시장 휴장일 판정을 위한 단면 임계치(95%)를 주입받아 내부 일수(Days) 경계선으로 변환 및 자산별 독립 연산 준비.
3. Execution:
   - 가격 데이터 내 0.00 상수를 찾아 NaN과 통합한 통합 불리언 결측 매트릭스 식별.
   - 시간축 기준 각 자산별 블록 ID 그룹화를 통한 최대 연속 결측장(Run-Length) 연산.
   - 단면축 기준 타임스탬프별 동시 결측 비율을 계산하여 95% 이상 누락 시점(휴장일) 추출.
   - 6일 이상 장기 결측 자산의 위치를 탐색하여 지시자 마스크(True) 및 타겟 샘플 가중치 매트릭스(0.0) 동적 생성.
4. Output: 후행 대치 레이어 및 ML 다운스트림 모델(Ridge, XGBoost, LSTM)이 참조할 고정 규격의 진단 메타데이터 리포트(딕셔너리 구조체) 반환.

주요 기능:
- 숨은 결측치 식별 (Identify Hidden Missing): 시스템 오류나 공급사 정책으로 유입되는 가짜 데이터인 0.00 상수를 도메인 특성에 맞게 통합 결측 매트릭스로 판별하여 상관관계 통계 왜곡 원천 차단.
- 연속 결측장 진단 (Analyze Temporal Missing Run-Length): 윈도우 내 자산별 연속 결측 일수를 연산하여 단기(1~2일: Ffill) 및 중기(3~5일: KNN/MICE) 알고리즘으로의 정밀 라우팅 이정표 제공.
- 단면 공통 결측 진단 (Analyze Cross-Sectional Co-Missingness): 특정 시점에 전체 자산의 95% 이상이 동시 누락된 일자를 식별 및 격리하여, 타 변수를 참조하는 다변량 알고리즘의 행렬 연산 불능 에러(Singular Matrix Error) 예방.
- 통계적 마스킹 및 지시자 생성 (Statistical Masking): 장기 결측 자산의 물리적 Drop을 금지하는 대신, 피처 영역에는 결측 지시자 마스크를 결합하고 타겟 영역에는 샘플 가중치를 0.0으로 세팅하여 모델 스스로 손실 역전파 오차 계산 시 해당 구간을 배제(Neutralization)하도록 인프라 신호 제공.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 0.00 상수 결측치 일괄 판별 vs 컨텍스트별 유효성 정밀 검증:
  - 장점: 가격(Price) 데이터에서 시스템 오류나 수집 공백으로 유입되는 가짜 0.00 데이터를 완벽히 잡아내어, 후행 대치 알고리즘이 왜곡된 공분산 통계량을 학습해 전체 자산의 상관관계를 파괴하는 연쇄 재앙을 선제 차단함.
  - 단점: 향후 수익률(Log Return) 데이터나 특정 채권 금리 변동폭 등 실제 유효한 0.00이 존재할 수 있는 컨텍스트 환경으로 파이프라인이 확장될 경우, 정상 데이터를 결측으로 무조건 오탐지하여 정보 손실이 발생할 위험이 상존함.
  - 근거: 현재 모듈의 입력단은 클렌징 레이어를 갓 통과한 원시 가격(Raw Price) 기반 자산 데이터프레임이므로 가격이 물리적으로 0.00이 될 수 없다는 도메인 확실성이 보장됨. 따라서 오탐지 리스크 제어 비용보다 하위 모델이 가짜 데이터를 바탕으로 오염되는 것을 막는 방어 비용의 가치가 압도적으로 큼.

- 슬라이딩 윈도우 기반 동적 마스킹 및 가중치 제로화 vs 장기 결측 자산 컬럼 물리적 드랍(Drop):
  - 장점: 하위 앙상블 모델군(Ridge, XGBoost, LSTM)의 행렬 연산 및 인풋 텐서 셰이프([Batch, TimeStep, Feature])의 완벽한 일치성을 보장하여, 특정 자산의 오염 때문에 파이프라인 전체가 붕괴되는 인프라 다운타임을 차단함.
  - 단점: 20일 중 6일 이상 비어 있는 신뢰성 낮은 오염 자산 데이터를 안전 상수(0.00)로 보존한 채 지시자 프레임워크와 가중치 프레임워크를 상주시켜야 하므로 피처 차원이 늘어나고 인메모리 제어 비용이 소폭 증가함.
  - 근거: 정적 행렬 셰이프에 극도로 민감한 프로덕션 ML 시스템 특성상, 차원 불일치로 인한 전체 파이프라인 붕괴 리스크 비용이 마스크 프레임워크 유지에 따른 미시적인 메모리 점유 및 피처 확장 비용보다 훨씬 가혹함.

- 단면 공통 결측 비율 임계치 격리(95% 이상 일자 추출) vs 개별 자산 이웃 참조(MICE/KNN) 일괄 강행:
  - 장점: 전 세계 금융시장 전체 휴장일이나 벤더사 전체 시스템 다운(Blackout) 일자를 사전에 완벽히 격리(Short-Circuiting)함으로써, 동시점에 참조할 주변 변수(이웃 자산)가 아예 존재하지 않아 다변량 연산 시 발생하는 특이 행렬 에러(Singular Matrix Error) 등을 상위 인프라 수준에서 안전하게 무력화함.
  - 단점: 95% 미만 ~ 90% 수준의 광역 결측일 경우 격리 대상에서 제외되므로 후행 알고리즘으로 진입 시 여전히 높은 연산 부하를 유발하거나 데이터 누수(Data Leakage) 경계선 리스크에 노출될 수 있음.
  - 근거: 190종 이상의 대규모 고차원 자산 중 95% 이상이 동시에 증발하는 현상은 개별 자산의 이벤트가 아닌 시스템적 이벤트가 확실하므로, 파이프라인 무결성 방어를 위해 확정적 경계선으로 격리 신호를 발행하는 아키텍처가 타당함.
"""

import numpy as np
import pandas as pd

from src.common.decorators import log_decorator
from src.common.exceptions import EmptyInputDataError, InsufficientLookbackWindowError


# ==============================================================================
# Main Class/Functions
# ==============================================================================
class MissingValueDiagnosis:
    """슬라이딩 윈도우 기반으로 금융 자산의 연속 결측장 및 단면 공통 결측을 진단하는 태스크 클래스."""

    def __init__(
        self,
        lookback_window_size: int = 20,
        short_gap_threshold_ratio: float = 0.10,
        medium_gap_threshold_ratio: float = 0.25,
        co_missing_threshold_ratio: float = 0.95,
    ) -> None:
        """진단에 필요한 시간적, 공간적 도메인 위험 임계치 파라미터를 초기화합니다.

        Args:
            lookback_window_size (int): 슬라이딩 윈도우 크기 (기본값: 1개월 거래일 기준 20일).
            short_gap_threshold_ratio (float): 단기 결측을 정의하는 임계 비율 (기본값: 10%).
            medium_gap_threshold_ratio (float): 중기/장기 결측을 분기하는 위험 임계 비율 (기본값: 25%).
            co_missing_threshold_ratio (float): 전체 시장 휴장 또는 시스템 붕괴를 판단하는 단면 임계 비율 (기본값: 0.95).
        """
        self._lookback_window_size = lookback_window_size
        self._short_gap_threshold_ratio = short_gap_threshold_ratio
        self._medium_gap_threshold_ratio = medium_gap_threshold_ratio
        self._co_missing_threshold_ratio = co_missing_threshold_ratio

        self._short_gap_threshold_days = int(self._lookback_window_size * self._short_gap_threshold_ratio)
        self._long_gap_threshold_days = int(self._lookback_window_size * self._medium_gap_threshold_ratio)

    @log_decorator()
    def execute(self, market_data_verified: pd.DataFrame) -> dict:
        """오케스트레이터로부터 데이터를 위임받아 3대 원자적 진단 시퀀스를 단방향으로 제어하는 메인 실행 메서드.

        Args:
            market_data_verified (pd.DataFrame): 셰이프가 보존된 상태의 수집 완료 데이터프레임 (인덱스: 타임스탬프, 컬럼: 자산코드).

        Returns:
            dict: 다음의 규격을 완벽히 충족하는 최종 출력 메타데이터 리포트:
                - market_holiday_timestamps (list): 전 자산 동시 결측 일자 문자열 리스트
                - asset_max_run_length (dict): 자산별 최대 연속 결측 거래일수 매핑 구조체
                - missing_indicator_mask (pd.DataFrame): 입력 피처(X) 방어용 불리언 마스크
                - target_sample_weights (pd.DataFrame): 예측 타겟(Y) 오차 역전파 차단용 가중치 마스크

        Raises:
            EmptyInputDataError: 입력 데이터프레임이 비어있을(Empty) 경우 발생.
            InsufficientLookbackWindowError: 로드된 거래일수가 슬라이딩 윈도우 크기 설정값보다 작을 경우 발생.
        """
        # [Fail-Fast 구조 비즈니스 가드레일 유효성 검증]
        if market_data_verified.empty:
            raise EmptyInputDataError(
                message="진단 태스크의 입력 데이터프레임이 빈 상태(Empty DataFrame)로 유입되어 연산을 기동할 수 없습니다."
            )

        if len(market_data_verified) < self._lookback_window_size:
            raise InsufficientLookbackWindowError(
                message=(
                    f"유입된 데이터의 시계열 길이({len(market_data_verified)}일)가 "
                    f"설정된 슬라이딩 룩백 윈도우 크기({self._lookback_window_size}일)보다 부족하여 시공간 통계 진단이 불가능합니다."
                ),
                current_length=len(market_data_verified),
                required_window_size=self._lookback_window_size
            )

        # 3대 시공간 진단 및 통계적 가중치 생성 서브루틴 구동
        missing_matrix = self._identify_hidden_missing(market_data_verified=market_data_verified)
        asset_max_run_length = self._calculate_temporal_run_length(missing_matrix=missing_matrix)
        market_holiday_timestamps = self._analyze_cross_sectional_missingness(missing_matrix=missing_matrix)
        missing_indicator_mask, target_sample_weights = self._generate_statistical_masks(
            missing_matrix=missing_matrix, asset_max_run_length=asset_max_run_length
        )

        missing_value_diagnosis_report = {
            "market_holiday_timestamps": market_holiday_timestamps,
            "asset_max_run_length": asset_max_run_length,
            "missing_indicator_mask": missing_indicator_mask,
            "target_sample_weights": target_sample_weights,
        }

        return missing_value_diagnosis_report

    def _identify_hidden_missing(self, market_data_verified: pd.DataFrame) -> pd.DataFrame:
        """가짜 데이터인 0.00 상수와 통계적 NaN을 통합하여 실제 무효화된 데이터 위치를 불리언 매트릭스로 매핑함.

        Args:
            market_data_verified (pd.DataFrame): 클렌징 레이어를 통과하여 유입된 원본 시계열 데이터프레임.

        Returns:
            pd.DataFrame: 
                - 행렬 크기(Shape): 입력 행렬 `market_data_verified`와 차원이 100% 동일한 고정 2D 판다스 프레임워크.
                - 인덱스 및 컬럼: 원본 데이터프레임의 타임스탬프 인덱스 및 고유 자산코드 컬럼 구조를 변형 없이 유지.
                - 내부 값(Values): 각 셀의 원시 데이터가 명시적 `NaN`이거나 금융 도메인상 유실을 의미하는 가짜 데이터인
                  정밀도 임계치 내의 부동소수점 `0.00` 지점은 불리언 `True`, 정상 적재 가격 지점은 `False`로 결합된 매트릭스.
        """
        is_explicit_nan = market_data_verified.isna()
        is_hidden_zero = np.isclose(market_data_verified, 0.00)
        missing_matrix = is_explicit_nan | is_hidden_zero
        return missing_matrix

    def _calculate_temporal_run_length(self, missing_matrix: pd.DataFrame) -> dict:
        """각 자산별로 슬라이딩 윈도우 내부에서 결측치가 연속으로 지속된 최대 거래일수를 연산함.

        Args:
            missing_matrix (pd.DataFrame): 명시적/숨은 결측치가 True로 판정된 상태의 통합 불리언 매트릭스.

        Returns:
            dict[str, int]: 
                - 데이터 구조: 고유 자산 식별자(컬럼명 문자열)를 키(Key)로 취하는 파이썬 기본 딕셔너리 객체.
                - 매핑 값(Value): 해당 자산이 슬라이딩 룩백 윈도우 전체 구간 내부에서 기록한 '최대 연속 결측 거래일수(Max Missing Run-Length)'를 나타내는 순수 정수형(int) 데이터.
                - 특이사항 명세: 결측 이력이 윈도우 안에 단 1거래일도 포착되지 않은 무결성 자산의 경우, 결측장이 `0`으로 기록되어 후행 `ForwardFillTask` 바인딩 대상에서 배제됨.
        """
        asset_max_run_length = {}

        for column_name in missing_matrix.columns:
            asset_series = missing_matrix[column_name]
            consecutive_block_indicators = (asset_series != asset_series.shift()).cumsum()
            consecutive_run_lengths = asset_series[asset_series].groupby(consecutive_block_indicators[asset_series]).size()

            if not consecutive_run_lengths.empty:
                max_missing_run_length = int(consecutive_run_lengths.max())
            else:
                max_missing_run_length = 0

            asset_max_run_length[column_name] = max_missing_run_length

        return asset_max_run_length

    def _analyze_cross_sectional_missingness(self, missing_matrix: pd.DataFrame) -> list:
        """특정 타임스탬프 단면에서 전체 자산의 동시 누락 비율을 계산하여 광역 격리 대상 일자를 추출함.

        Args:
            missing_matrix (pd.DataFrame): 명시적/숨은 결측치가 True로 판정된 상태의 통합 불리언 매트릭스.

        Returns:
            list[str]: 
                - 데이터 구조: ISO 8601 표준 날짜 문자열 포맷(예: 'YYYY-MM-DD') 요소들로 구성된 단방향 파이썬 리스트.
                - 추출 기준: 슬라이딩 데이터 단면(Row)에 적재된 전체 자산 수량 중 설정된 공통 결측 임계치(95% 이상)를 초과하여 동시 유실이 발생한 시점들의 집합.
                - 특이사항 명세: 전 금융시장 공동 휴장일이나 벤더 다운 일자가 식별되지 않을 경우, 연산 결합부 예방을 위해 빈 리스트(`[]`)를 반환함.
        """
        cross_sectional_missing_counts = missing_matrix.sum(axis=1)
        total_assets_count = missing_matrix.shape[1]
        cross_sectional_missing_ratios = cross_sectional_missing_counts / total_assets_count

        holiday_mask = cross_sectional_missing_ratios >= self._co_missing_threshold_ratio
        market_holiday_index = missing_matrix.index[holiday_mask]

        market_holiday_timestamps = [str(timestamp) for timestamp in market_holiday_index]
        return market_holiday_timestamps

    def _generate_statistical_masks(self, missing_matrix: pd.DataFrame, asset_max_run_length: dict) -> tuple:
        """위험 기준치(6일 이상 장기 결측)를 초과하는 오염 자산을 대상으로 통계적 마스크 및 가중치를 생성함.

        Args:
            missing_matrix (pd.DataFrame): 명시적/숨은 결측치가 True로 판정된 상태의 통합 불리언 매트릭스.
            asset_max_run_length (dict): 자산코드가 키이고 최대 연속 결측 거래일수가 값인 시공간 진단 딕셔너리 결과물.

        Returns:
            tuple[pd.DataFrame, pd.DataFrame]: 
                인풋 텐서 셰이프 방어를 위해 행렬 삭제 없이 고안된 고차원 판다스 데이터프레임 2-튜플(Tuple):
                - index 0 (missing_indicator_mask): 원본 행렬과 차원이 동일함. 20거래일 중 25% 초과인 6거래일 이상의 
                  장기 결측 자산의 결측 위치 좌표만 불리언 `True`로 명시 전환하고, 단기/중기 결측 및 정상 구간은 `False`로 잠근 피처 변수 결합용 지시자 마스크.
                - index 1 (target_sample_weights): 원본 행렬과 차원이 동일함. 6거래일 이상의 장기 연속 거래정지 자산의 
                  결측 발생 윈도우 구간은 부동소수점 `0.0`으로 하향 튜닝하고, 그 외 정상 데이터 및 단/중기 보간 가능 영역은 `1.0`을 부여하여 손실 오차 학습 계산에서 완벽히 배제하는 가중치 매트릭스.
        """
        missing_indicator_mask = pd.DataFrame(False, index=missing_matrix.index, columns=missing_matrix.columns)
        target_sample_weights = pd.DataFrame(1.0, index=missing_matrix.index, columns=missing_matrix.columns)

        for column_name, max_run in asset_max_run_length.items():
            if max_run > self._long_gap_threshold_days:
                specific_missing_positions = missing_matrix[column_name]
                missing_indicator_mask[column_name] = specific_missing_positions
                target_sample_weights.loc[specific_missing_positions, column_name] = 0.0

        return missing_indicator_mask, target_sample_weights