"""
외부 설정 파일(feature.yml)의 명세를 파싱하여 순차적으로 실행할 파생 피처 엔지니어링 구체 태스크(Task) 객체 체인을 일괄 생성 및 결합하는 팩토리 모듈입니다.
ConfigManager를 통해 YAML 설정에 명시된 하위 작업들의 활성화 여부(enabled) 및 수치형 파라미터 세트를 적출(Unpack)하고,
명시적 생성자 인자로 주입하여 가동 준비가 완료된 구체 태스크 인스턴스 리스트를 생성합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: FeatureService 계층으로부터 매개변수 없는 피처 태스크 체인 빌드 요청 수신.
2. Config Parsing: 싱글톤 ConfigManager를 호출하여 feature.yml 내의 `feature_engineering` 블록 명세 로드.
3. Parameter Unpacking & Assembly: 활성화(`enabled: true`)된 태스크별 명칭(`task_name`)을 식별하고, 해당 파라미터 세트를 직접 추출(Unpack)하여 구체 Task 인스턴스 생성 및 정렬된 리스트에 순차 적재.
4. Output: 상위 오케스트레이터 서비스가 파이프라이닝 순회 연산을 수행할 구체 태스크 인스턴스 리스트(`List[AbstractFeatureTask]`) 반환.

주요 기능:
- [Config-Driven Chain Generation] feature.yml 명세 구조만 파악하여 실행할 파생 피처 태스크 라인업을 일괄 결합 사출.
- [Parameter Unpacking & Binding] 각 피처 태스크별 윈도우 크기, 대상 가격 컬럼, 지표 산출 임계치들을 설정 허브로부터 적출하여 객체 생성자에 명시적 주입.
- [Decoupling & Isolation] FeatureService 계층이 세부 태스크 클래스의 직접적인 생성자 호출에 종속되지 않도록 객체 생성 책임을 완벽히 격리.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- Config-Manager 기반 팩토리 내 명시적 태스크 조립 vs 서비스 레이어 직접 인스턴스화:
  - 장점: feature.yml의 활성화 토글 변경만으로 실행 피처 라인업을 자율 조율할 수 있으며, FeatureService 코드를 한 줄도 수정하지 않고 파이프라인 확장 가능(OCP 준수).
  - 단점: 신규 피처 Task 추가 시 feature.yml 명세 정의와 더불어 Factory 내 명시적 바인딩 구문을 함께 추가해 주어야 함.
  - 근거: 하위 태스크가 전달받는 파라미터의 명시성과 무상태성(Stateless)을 보장하고, 런타임 타입 정합성 검증을 조기에 수행하기 위해 명시적 팩토리 결합 구조를 선택함.
"""

from typing import List, Dict, Any, Optional

from src.common.config import ConfigManager
from src.feature.tasks.abstract_feature import AbstractFeature
from src.feature.tasks.target_feature import TargetFeature
from src.feature.tasks.trend_momentum import TrendMomentum
from src.feature.tasks.volatility_risk import VolatilityRisk
from src.feature.tasks.macro_cross_asset import MacroCrossAsset
from src.feature.tasks.derivatives_volume import DerivativesVolume
from src.feature.tasks.calendar_seasonality import CalendarSeasonality
from src.common.exceptions import FeatureInitializationError, FeatureError


class FeatureFactory:
    """feature.yml 설정을 파싱하여 구체 Feature Task 객체들을 명시적으로 인스턴스화하고 순차 실행 체인으로 결합하는 팩토리 클래스."""

    def __init__(self) -> None:
        """FeatureFactory 인스턴스를 초기화하고 싱글톤 ConfigManager를 바인딩합니다."""
        # [설계 의도] ConfigManager 싱글톤 인스턴스를 직접 바인딩하여 외부 설정 주입 종속성 차단
        self._config: ConfigManager = ConfigManager()

    def create_features(self) -> List[AbstractFeature]:
        """feature.yml 설정 명세를 파싱하여 순차 구동할 피처 태스크 인스턴스 체인을 일괄 결합 생성합니다.

        Returns:
            List[AbstractFeature]: 순차적으로 연산을 수행할 준비가 완료된 구체 Feature Task 객체 리스트.

        Raises:
            FeatureInitializationError: feature.yml 내 활성화된 태스크 명세가 없거나, 필수 파라미터 누락 또는 객체 초기화 실패 시 발생.
        """
        try:
            features: List[AbstractFeature] = []

            # [설계 의도] ConfigManager로부터 feature_engineering 라인업 명세 일괄 로드
            feature_engineering_configs: List[Dict[str, Any]] = (
                self._config.get("feature_engineering") or []
            )

            if not feature_engineering_configs:
                raise FeatureInitializationError(
                    message="[FeatureFactory] feature.yml 설정 내부에 feature_engineering 명세가 존재하지 않거나 비어 있습니다."
                )

            for task_config in feature_engineering_configs:
                task_name: str = task_config.get("task_name", "")
                is_enabled: bool = task_config.get("enabled", True)

                # 비활성화된 태스크는 생성 대상에서 스킵
                if not is_enabled:
                    continue

                params: Dict[str, Any] = task_config.get("params", {})

                # TargetTask (예측 타겟 변수 생성 태스크)
                if task_name == "TargetTask":
                    self._validate_required_params(
                        task_name=task_name,
                        params=params,
                        required_keys=["source_price", "target_name", "forecast_horizon_days"]
                    )
                    features.append(
                        TargetFeature(
                            task_name=task_name,
                            source_price=params["source_price"],
                            target_name=params["target_name"],
                            forecast_horizon_days=params["forecast_horizon_days"]
                        )
                    )

                # TrendMomentumTask (추세 및 모멘텀 지표 생성 태스크)
                elif task_name == "TrendMomentumTask":
                    self._validate_required_params(
                        task_name=task_name,
                        params=params,
                        required_keys=["return_lookback_days", "moving_average_ratios", "risk_adjusted_window_days"]
                    )
                    features.append(
                        TrendMomentum(
                            task_name=task_name,
                            return_lookback_days=params["return_lookback_days"],
                            moving_average_ratios=params["moving_average_ratios"],
                            risk_adjusted_window_days=params["risk_adjusted_window_days"]
                        )
                    )

                # VolatilityRiskTask (변동성 및 리스크 레짐 지표 생성 태스크)
                elif task_name == "VolatilityRiskTask":
                    self._validate_required_params(
                        task_name=task_name,
                        params=params,
                        required_keys=[
                            "volatility_lookback_days",
                            "volatility_regime_windows",
                            "higher_moments_window_days",
                            "price_range_window_days"
                        ]
                    )
                    features.append(
                        VolatilityRisk(
                            task_name=task_name,
                            volatility_lookback_days=params["volatility_lookback_days"],
                            volatility_regime_windows=params["volatility_regime_windows"],
                            higher_moments_window_days=params["higher_moments_window_days"],
                            price_range_window_days=params["price_range_window_days"]
                        )
                    )

                # MacroCrossAssetTask (매크로 및 교차 자산 지표 생성 태스크)
                elif task_name == "MacroCrossAssetTask":
                    self._validate_required_params(
                        task_name=task_name,
                        params=params,
                        required_keys=[
                            "us_treasury_spread",
                            "us_kr_rate_difference",
                            "us_kr_market_lag",
                            "coin_equity_correlation"
                        ]
                    )
                    features.append(
                        MacroCrossAsset(
                            task_name=task_name,
                            us_treasury_spread=params["us_treasury_spread"],
                            us_kr_rate_difference=params["us_kr_rate_difference"],
                            us_kr_market_lag=params["us_kr_market_lag"],
                            coin_equity_correlation=params["coin_equity_correlation"]
                        )
                    )

                # DerivativesVolumeTask (파생상품 및 거래량 수급 지표 생성 태스크)
                elif task_name == "DerivativesVolumeTask":
                    self._validate_required_params(
                        task_name=task_name,
                        params=params,
                        required_keys=[
                            "futures_basis",
                            "futures_intraday_range",
                            "volume_and_value_anomaly"
                        ]
                    )
                    features.append(
                        DerivativesVolume(
                            task_name=task_name,
                            futures_basis=params["futures_basis"],
                            futures_intraday_range=params["futures_intraday_range"],
                            volume_and_value_anomaly=params["volume_and_value_anomaly"]
                        )
                    )

                # CalendarSeasonalityTask (계절성 및 달력 주기성 지표 생성 태스크)
                elif task_name == "CalendarSeasonalityTask":
                    self._validate_required_params(
                        task_name=task_name,
                        params=params,
                        required_keys=["enable_cyclical_month_encoding", "period_end_threshold_days"]
                    )
                    features.append(
                        CalendarSeasonality(
                            task_name=task_name,
                            enable_cyclical_month_encoding=params["enable_cyclical_month_encoding"],
                            period_end_threshold_days=params["period_end_threshold_days"]
                        )
                    )

                else:
                    raise FeatureInitializationError(
                        message=f"[FeatureFactory] 지원하지 않거나 정의되지 않은 피처 태스크 명칭입니다: {task_name}",
                        task_name=task_name
                    )

            # 안전 가드레일: 활성화된 피처 태스크가 단 하나도 없을 때
            if not features:
                raise FeatureInitializationError(
                    message="[FeatureFactory] feature.yml 설정 내 활성화(enabled: true)된 피처 태스크가 존재하지 않습니다."
                )

            return features

        except FeatureError as feature_err:
            raise feature_err
        except Exception as unexpected_err:
            raise FeatureInitializationError(
                message="[FeatureFactory] 피처 태스크 체인 결합 생성 중 예기치 못한 크래시가 발생했습니다.",
                original_exception=unexpected_err
            ) from unexpected_err

    def _validate_required_params(
        self,
        task_name: str,
        params: Dict[str, Any],
        required_keys: List[str]
    ) -> None:
        """태스크 생성에 필요한 필수 파라미터 키의 존재 여부를 명시적으로 검증하는 가드 함수.

        Args:
            task_name (str): 검증 대상 태스크 명칭.
            params (Dict[str, Any]): YAML에서 주입받은 파라미터 딕셔너리.
            required_keys (List[str]): 필수 포함되어야 하는 키 목록.

        Raises:
            FeatureInitializationError: 필수 키가 단 하나라도 누락된 경우 즉시 발생.
        """
        # [설계 의도] params.get()으로 기본값을 조용히 채우는 silent failure 방지. 누락 시 즉시 파이프라인 차단.
        missing_keys: List[str] = [
            key for key in required_keys if key not in params
        ]

        if missing_keys:
            raise FeatureInitializationError(
                message=(
                    f"[{task_name}] feature.yml 명세에 필수 파라미터 키가 누락되었습니다. "
                    f"(누락된 키: {missing_keys})"
                ),
                task_name=task_name
            )