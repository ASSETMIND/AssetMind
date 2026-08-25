"""
[모듈 목적 및 상세 설명]
골드 파이프라인(Gold Pipeline) 전처리 계층 내 결측치 처리의 최상위 실행 제어를 전담하는 오케스트레이터 태스크입니다.
MissingValueDiagnosisTask가 산출한 자산별 연속 결측장 진단 리포트를 선언적으로 해독하여 단기, 중기, 장기 결측 자산군을 
동적으로 라우팅합니다. 특히 단기 결측 자산군에 대해서는 통계적 성향(정적, 추세, 회귀)을 다중 버킷 실험 구조(Multi-Bucket)로 
확장 생성하며, 장기 결측에 대해서는 하위 ML 모델의 손실 함수 계산을 차단할 통계적 격리 마스크 행렬 쌍을 동시 빌드합니다.
세부 태스크 레이어 계층 규칙에 의거하여 외부 설정 딕셔너리(config) 통째 주입을 철저히 배제하고, 상위 서비스 계층에서 완전히 
해체된 원자적 매개변수(Discrete Parameters)만을 주입받아 구동함으로써 설정 스키마와의 엔지니어링적 결합도를 원천 제거합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Initialization: 상위 PreprocessorService로부터 분해 주입된 임계치 및 하위 알고리즘별 하이퍼파라미터 인자 수신 및 레지스트리 빌드.
2. Input: Ingestion 레이어에서 적재된 20거래일 원본 pd.DataFrame 및 MissingValueDiagnosisTask의 진단 리포트 딕셔너리.
3. Processing:
   - 진단 리포트를 파싱하여 단기(<=short_term_threshold), 중기(<=medium_term_threshold), 장기 자산 컬럼 목록을 동적 분류.
   - 단기 자산 영역에 대해 3대 실험 버킷별로 독립 카피본을 생성하여 병렬 전략 연산 위임.
   - 중기 자산에 대해 칼만 필터 평활화를 공통 적용하고, 장기 결측구간은 상수 대치 및 가중치/인디케이터 행렬 계산.
4. Output: 3대 실험 버킷 데이터프레임과 피처용 Mask, 타겟용 Sample Weight 행렬이 패키징된 반환 계약 스키마(Dict) 반환.

주요 기능:
- [Decoupled Parameter Injection] 통 config 객체 의존성을 파괴하고 풀어진 개별 파라미터 제어를 통해 태스크 레이어 독립 가용성 확보.
- [Dynamic Strategy Routing] 자산별 품질 상태에 따라 최적의 보간 알고리즘 객체를 런타임에 동적 매핑 및 집행.
- [Multi-Bucket Experimentation Framework] 다운스트림 모델의 수렴도 비교를 위한 3대 통계 국면 데이터프레임 동시 분기 제어.
- [Downstream Tensor Defense] 장기 거래정지 자산에 대한 상수 대치 및 Loss Neutralization용 샘플 가중치 행렬 생성.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from src.common.exceptions import ImputationExecutionError
from src.preprocessor.tasks.missing_value.locf_imputer import LocfImputer
from src.preprocessor.tasks.missing_value.log_return_imputer import LogReturnImputer
from src.preprocessor.tasks.missing_value.moving_average_imputer import MovingAverageImputer
from src.preprocessor.tasks.missing_value.kalman_imputer import KalmanImputer
# ==============================================================================
# Main Class/Functions
# ==============================================================================


class MissingValueImputation:
    """진단 리포트를 기반으로 하위 임퓨터 전략을 바인딩하고 다중 실험 버킷 행렬을 오케스트레이션하는 마스터 태스크 클래스."""

    def __init__(
        self,
        short_term_threshold: float = 0.10,
        medium_term_threshold: float = 0.25,
        log_return_params: Optional[Dict[str, Any]] = None,
        moving_average_params: Optional[Dict[str, Any]] = None,
        kalman_params: Optional[Dict[str, Any]] = None
    ) -> None:
        """상위 서비스 레이어로부터 완전히 해체 분분된 개별 제어 파라미터 세트를 안전하게 주입받아 인스턴스를 초기화합니다.

        Args:
            short_term_threshold (float): 단기 결측을 판정하는 윈도우 대비 연속 결측 비율 임계치. 기본값 0.10.
            medium_term_threshold (float): 중기 결측을 판정하는 윈도우 대비 연속 결측 비율 임계치. 기본값 0.25.
            log_return_params (Dict[str, Any], optional): LogReturnImputer 구동을 위한 하이퍼파라미터 사전.
            moving_average_params (Dict[str, Any], optional): MovingAverageImputer 구동을 위한 하이퍼파라미터 사전.
            kalman_params (Dict[str, Any], optional): KalmanImputer 구동을 위한 하이퍼파라미터 사전.
        """
        self._short_term_threshold = short_term_threshold
        self._medium_term_threshold = medium_term_threshold
        
        # [설계 의도] None 주입으로 인한 하위 사전 인덱싱 NullPointerException 크래시를 방지하기 위해 빈 딕셔너리로 방어 바인딩함.
        self._log_return_params = log_return_params or {}
        self._moving_average_params = moving_average_params or {}
        self._kalman_params = kalman_params or {}
        
        self._strategy_registry: Dict[str, Any] = {}
        self._initialize_strategy_registry()

    def _initialize_strategy_registry(self) -> None:
        """[설계 의도] OCP(개방-폐쇄 원칙)를 사수하기 위해 구체 클래스 의존성을 배제하고,
        런타임에 전략 다형성 맵을 빌드하여 향후 알고리즘 추가 시 본체 수정을 원천 차단함.
        생성자 시점에 수신한 세부 컴포넌트별 튜닝 매개변수를 구체 인스턴스 쌍에 정확히 밀어넣어 격리함.
        """
        self._strategy_registry["locf"] = (LocfImputer(), {})
        self._strategy_registry["log_return"] = (LogReturnImputer(), self._log_return_params)
        self._strategy_registry["moving_average"] = (MovingAverageImputer(), self._moving_average_params)
        self._strategy_registry["kalman"] = (KalmanImputer(), self._kalman_params)

    def execute(self, df: pd.DataFrame, diagnosis_report: Dict[str, Any]) -> Dict[str, Any]:
        """20거래일 원본 프레임과 진단서를 결합 해독하여 최종 정제된 다중 버킷 및 통계 마스크 패키지를 반환합니다.

        Args:
            df (pd.DataFrame): Ingestion 레이어에서 파이프라인을 통해 공급된 20 x 190+ 원본 금융 시계열 행렬.
            diagnosis_report (Dict[str, Any]): MissingValueDiagnosisTask가 발행한 자산별 연속 결측장 리포트 사전 데이터.

        Returns:
            Dict[str, Any]: 아래의 인터페이스 반환 규격 계약을 완벽하게 준수하는 결과 아티팩트 구조체.
                - "bucket_locf" (pd.DataFrame): 단기 대치에 LOCF를 적용하여 공백을 완전 박멸한 정제 프레임.
                - "bucket_log_return" (pd.DataFrame): 단기 대치에 로그 수익률 외삽을 적용하여 공백을 완전 박멸한 정제 프레임.
                - "bucket_moving_average" (pd.DataFrame): 단기 대치에 이평선 회귀를 적용하여 공백을 완전 박멸한 정제 프레임.
                - "missing_indicator_mask" (pd.DataFrame): 피처 레이어용 장기 결측 위치 격리 불리언 행렬 (1: 결측, 0: 정상).
                - "target_sample_weights" (pd.DataFrame): 타겟 레이어용 역전파 손실 계산 차단 가중치 행렬 (0.0: 장기결측, 1.0: 정상).

        Raises:
            ImputationExecutionError: 입력 행렬의 타입 비정합성, 진단 리포트 유실, 혹은 하위 
                전략 런타임 연산 실패 시 구조화된 문맥 데이터를 봉인하여 상위 서비스로 즉각 전파.
        """
        # [설계 의도] 운영 환경에서 강제 생략될 여지가 있는 assert 구문 대신, 명시적 상시 검증 조건을 걸어
        # 인풋 파라미터 정합성이 파괴된 상태로 수리 루프에 진입하여 시스템이 오염되는 현상을 조기 차단(Fail-Fast)함.
        if not isinstance(df, pd.DataFrame):
            raise ImputationExecutionError(
                message="오케스트레이터 태스크 주입 데이터가 유효한 pd.DataFrame 구조가 아닙니다.",
                imputer_type=self.__class__.__name__,
                target_assets=[]
            )
        
        if not diagnosis_report or "asset_max_run_length" not in diagnosis_report:
            raise ImputationExecutionError(
                message="결측치 처리를 위한 상위 진단 리포트 아티팩트가 누락되었거나 파싱할 수 없습니다.",
                imputer_type=self.__class__.__name__,
                target_assets=[]
            )

        try:
            # [Cold Start Fallback 분기] 20일 미만 유입 시 수렴 불가한 칼만/격리 로직 우회 후 단순 보간 집행
            is_cold_start = diagnosis_report.get("is_cold_start", False)
            if is_cold_start:
                final_protection_chain = lambda target_df: target_df.ffill(axis=0).bfill(axis=0).fillna(0.0)
                cleaned_df = final_protection_chain(df.copy())
                
                missing_indicator_mask = pd.DataFrame(0, index=df.index, columns=df.columns)
                target_sample_weights = pd.DataFrame(1.0, index=df.index, columns=df.columns)
                
                imputation_summary_report = {
                    "short_term_locf_asset_count": len(df.columns),
                    "medium_term_kalman_asset_count": 0,
                    "long_term_neutralized_asset_count": 0
                }
                
                return {
                    "bucket_locf": cleaned_df.copy(),
                    "bucket_log_return": cleaned_df.copy(),
                    "bucket_moving_average": cleaned_df.copy(),
                    "missing_indicator_mask": missing_indicator_mask,
                    "target_sample_weights": target_sample_weights,
                    "imputation_summary_report": imputation_summary_report
                }

            # 20거래일 정상 윈도우 시 기존 정밀 라우팅 집행
            window_length = len(df)
            short_term_days = int(window_length * self._short_term_threshold)
            medium_term_days = int(window_length * self._medium_term_threshold)

            # 라우팅 분류용 동적 자산 버킷 리스트 선언
            short_term_assets: List[str] = []
            medium_term_assets: List[str] = []
            long_term_assets: List[str] = []

            # [설계 의도] 진단서 패러다임을 집행하여 자산별 최대 연속 결측장(max_run)을 기준으로 컬럼축 단위 동적 분기를 수행함.
            run_length_report: Dict[str, int] = diagnosis_report["asset_max_run_length"]
            for asset_code, max_run in run_length_report.items():
                if max_run == 0:
                    continue
                elif max_run <= short_term_days:
                    short_term_assets.append(asset_code)
                elif max_run <= medium_term_days:
                    medium_term_assets.append(asset_code)
                else:
                    long_term_assets.append(asset_code)

            # [설계 의도] 다운스트림 모델의 학습 손실 계산 방어를 위한 마스크 및 샘플 가중치 프레임 초기화.
            # 초기 상태는 전 차원 정상(Indicator=0, Weight=1.0)으로 채워 물리적 셰이프를 선제 구축함.
            missing_indicator_mask = pd.DataFrame(0, index=df.index, columns=df.columns)
            target_sample_weights = pd.DataFrame(1.0, index=df.index, columns=df.columns)

            # [설계 의도] 장기 거래정지 및 고위험 결측 자산군 격리 처리 블록 집행.
            # 값이 비어있는 위치를 정확히 타겟팅하여 피처용 1 태깅, 타겟용 0.0 태깅을 완료하고, 값은 상수 0.00으로 고정해 차원을 방어함.
            if long_term_assets:
                for asset in long_term_assets:
                    nan_positions = df[asset].isna()
                    missing_indicator_mask.loc[nan_positions, asset] = 1
                    target_sample_weights.loc[nan_positions, asset] = 0.0

            # 3대 실험군 독립 버킷 데이터프레임 깊은 복사 분기 생성
            bucket_locf = df.copy()
            bucket_log_return = df.copy()
            bucket_moving_average = df.copy()

            # [설계 의도] 전사적 시장 휴장일(Systemic Blackout) 국면이 개별 자산의 보간 로직(특히 장기 결측의 0.00 대치)에 의해 
            # 왜곡되는 것을 방어하기 위해, 휴장일 타임스탬프 행에 대해 직전 영업일 가격을 선제적으로 일괄 ffill 처리함.
            market_holidays = [pd.Timestamp(t) for t in diagnosis_report.get("market_holiday_timestamps", [])]
            for bucket in [bucket_locf, bucket_log_return, bucket_moving_average]:
                for holiday in market_holidays:
                    if holiday in bucket.index:
                        idx_pos = bucket.index.get_loc(holiday)
                        if idx_pos > 0:
                            bucket.loc[holiday] = bucket.loc[holiday].fillna(bucket.iloc[idx_pos - 1])

            # [설계 의도] 장기 결측 영역은 보간의 유의성이 전무하므로 안전한 수리적 상수 0.00으로 3대 버킷 전체를 일괄 동결 대치함.
            if long_term_assets:
                bucket_locf[long_term_assets] = bucket_locf[long_term_assets].fillna(0.0)
                bucket_log_return[long_term_assets] = bucket_log_return[long_term_assets].fillna(0.0)
                bucket_moving_average[long_term_assets] = bucket_moving_average[long_term_assets].fillna(0.0)

            # [설계 의도] 중기 결측치 공통 구제 로직 집행.
            # 다중 버킷 실험의 변수 통제를 격리하기 위해 중기 자산은 칼만 필터 전략 객체 하나로 통일하여 3대 버킷 모두에 일치 유입시킴.
            if medium_term_assets:
                kalman_imputer, kalman_kwargs = self._strategy_registry["kalman"]
                bucket_locf = kalman_imputer.transform(bucket_locf, medium_term_assets, **kalman_kwargs)
                bucket_log_return = kalman_imputer.transform(bucket_log_return, medium_term_assets, **kalman_kwargs)
                bucket_moving_average = kalman_imputer.transform(bucket_moving_average, medium_term_assets, **kalman_kwargs)

            # [설계 의도] 단기 결측치 실험 분기 로직 집행.
            # 각 버킷 본연의 도메인 수학적 특성(직전값 정적 유지, 로그 수익률 추세 확장, 이평선 평균 회귀) 전략을 각개 바인딩하여 변환 위임함.
            if short_term_assets:
                locf_imputer, _ = self._strategy_registry["locf"]
                log_return_imputer, log_return_kwargs = self._strategy_registry["log_return"]
                moving_average_imputer, moving_average_kwargs = self._strategy_registry["moving_average"]

                bucket_locf = locf_imputer.transform(bucket_locf, short_term_assets)
                bucket_log_return = log_return_imputer.transform(bucket_log_return, short_term_assets, **log_return_kwargs)
                bucket_moving_average = moving_average_imputer.transform(bucket_moving_average, short_term_assets, **moving_average_kwargs)

            # [설계 의도] 인프라 최종 방어 레이어 가동.
            # 수리적 예외 상황으로 인해 행렬 내부 어딘가에 NaN 잔차가 단 1셀이라도 잔존하는 현상을 영구 박멸하기 위해,
            # 안전벽 목적의 최종 정적 ffill().ffill(axis=0).bfill(axis=0).fillna(0.0) 체인을 통과시켜 100% 무결한 조밀 행렬(Dense Matrix) 차원을 사수함.
            final_protection_chain = lambda target_df: target_df.ffill(axis=0).bfill(axis=0).fillna(0.0)
            
            # [설계 의도] 상위 PreprocessorService의 요약 보고(log_preprocessing_summary) 계약 조건을 충족하기 위해
            # 각 라우팅 분기별 처리 완료 자산 수 메타데이터 구조체를 동적 빌드하여 레지스트리 유실을 복원함.
            imputation_summary_report = {
                "short_term_locf_asset_count": len(short_term_assets),
                "medium_term_kalman_asset_count": len(medium_term_assets),
                "long_term_neutralized_asset_count": len(long_term_assets)
            }
            
            return {
                "bucket_locf": final_protection_chain(bucket_locf),
                "bucket_log_return": final_protection_chain(bucket_log_return),
                "bucket_moving_average": final_protection_chain(bucket_moving_average),
                "missing_indicator_mask": missing_indicator_mask,
                "target_sample_weights": target_sample_weights,
                "imputation_summary_report": imputation_summary_report
            }
        
        except Exception as original_error:
            # 하위 수리 모듈 패닉 또는 인덱싱 에러 포착 및 구조화 예외 전파 체인 봉인
            raise ImputationExecutionError(
                message="결측치 처리 최상위 오케스트레이션(Execution Imputation Job) 연산 중 치명적 런타임 오류가 발생했습니다.",
                imputer_type=self.__class__.__name__,
                target_assets=list(diagnosis_report.get("asset_max_run_length", {}).keys()),
                original_exception=original_error
            )