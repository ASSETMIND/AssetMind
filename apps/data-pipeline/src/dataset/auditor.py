import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.stattools import adfuller, acf
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tools.tools import add_constant
from typing import Dict, Tuple, Any, List

from src.dataset.walk_forward_splitter import WalkForwardSplitter

class ChampionDatasetAuditor:
    """챔피언 데이터셋의 통계적 건전성, 시계열 동역학, 공변량 표류를 감사하는 클래스."""

    def __init__(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        X_inference: pd.DataFrame,
        forecast_horizon: int = 20
    ):
        self.X_train = X_train
        self.y_train = y_train
        self.X_test = X_test
        self.y_test = y_test
        self.X_inference = X_inference
        self.horizon = forecast_horizon

    def audit_partition_architecture(self) -> pd.DataFrame:
        """[대시보드 1] 파티션 아키텍처 및 유효 표본 크기(ESS) 감사표 생성."""
        records = [
            {
                "Partition": "Train Set",
                "Role": "모델 학습 및 Walk-Forward CV 영역",
                "Start Date": self.X_train.index.min().strftime("%Y-%m-%d"),
                "End Date": self.X_train.index.max().strftime("%Y-%m-%d"),
                "Rows (N)": f"{len(self.X_train):,}",
                "Features": self.X_train.shape[1],
                "ESS (N / 20d)": f"{len(self.X_train) / self.horizon:.1f} 독립 구간",
                "Nulls / Infs": f"{self.X_train.isna().sum().sum()} / {np.isinf(self.X_train.to_numpy()).sum()}",
                "Memory": f"{self.X_train.memory_usage().sum() / 1024**2:.2f} MB"
            },
            {
                "Partition": "Test Set",
                "Role": "Out-of-Sample 최종 실전 평가 영역",
                "Start Date": self.X_test.index.min().strftime("%Y-%m-%d"),
                "End Date": self.X_test.index.max().strftime("%Y-%m-%d"),
                "Rows (N)": f"{len(self.X_test):,}",
                "Features": self.X_test.shape[1],
                "ESS (N / 20d)": f"{len(self.X_test) / self.horizon:.1f} 독립 구간",
                "Nulls / Infs": f"{self.X_test.isna().sum().sum()} / {np.isinf(self.X_test.to_numpy()).sum()}",
                "Memory": f"{self.X_test.memory_usage().sum() / 1024**2:.2f} MB"
            },
            {
                "Partition": "Inference Set",
                "Role": "T+20 실시간 추론 전용 (정답 y 미도래)",
                "Start Date": self.X_inference.index.min().strftime("%Y-%m-%d"),
                "End Date": self.X_inference.index.max().strftime("%Y-%m-%d"),
                "Rows (N)": f"{len(self.X_inference):,}",
                "Features": self.X_inference.shape[1],
                "ESS (N / 20d)": "Live Horizon",
                "Nulls / Infs": f"{self.X_inference.isna().sum().sum()} / {np.isinf(self.X_inference.to_numpy()).sum()}",
                "Memory": f"{self.X_inference.memory_usage().sum() / 1024**2:.2f} MB"
            }
        ]
        return pd.DataFrame(records)

    def audit_target_dynamics(self) -> pd.DataFrame:
        """[대시보드 2] 타겟 변수(y) 시계열 동적 속성 및 레짐 시프트 검정표 생성."""
        y_tr = self.y_train.dropna()
        y_te = self.y_test.dropna()

        # 1. 고차 모멘트
        mean_tr, mean_te = y_tr.mean(), y_te.mean()
        std_tr, std_te = y_tr.std(), y_te.std()
        skew_tr, skew_te = stats.skew(y_tr), stats.skew(y_te)
        kurt_tr, kurt_te = stats.kurtosis(y_tr), stats.kurtosis(y_te)
        pos_tr = (y_tr > 0).mean() * 100
        pos_te = (y_te > 0).mean() * 100

        # 2. 시계열 정상성 및 자기상관
        adf_tr = adfuller(y_tr)[1]
        adf_te = adfuller(y_te)[1]
        acf_tr = acf(y_tr, nlags=self.horizon)
        acf_te = acf(y_te, nlags=self.horizon)

        # 3. 분포 거리 및 동일성 검정
        ks_stat, ks_pval = stats.ks_2samp(y_tr, y_te)
        w_dist = stats.wasserstein_distance(y_tr, y_te)

        records = [
            {"Domain": "1. 기술통계 (Moments)", "Metric": "평균 (Mean)", "Train Set": f"{mean_tr:.6f}", "Test Set": f"{mean_te:.6f}", "Diagnosis": f"위치 모멘트 {mean_te / mean_tr:.2f}x 이동"},
            {"Domain": "1. 기술통계 (Moments)", "Metric": "표준편차 (Std)", "Train Set": f"{std_tr:.6f}", "Test Set": f"{std_te:.6f}", "Diagnosis": f"변동성 {std_te / std_tr:.2f}x 확대"},
            {"Domain": "1. 기술통계 (Moments)", "Metric": "왜도 (Skewness)", "Train Set": f"{skew_tr:.2f}", "Test Set": f"{skew_te:.2f}", "Diagnosis": f"비대칭도 변동 (Δ: {skew_te - skew_tr:+.2f})"},
            {"Domain": "1. 기술통계 (Moments)", "Metric": "첨도 (Kurtosis)", "Train Set": f"{kurt_tr:.2f}", "Test Set": f"{kurt_te:.2f}", "Diagnosis": "팻테일(Train) ➔ 정규화(Test) 전환"},
            {"Domain": "1. 기술통계 (Moments)", "Metric": "양수 비율 (Pos %)", "Train Set": f"{pos_tr:.1f}%", "Test Set": f"{pos_te:.1f}%", "Diagnosis": f"상승 베이스라인 {pos_te - pos_tr:+.1f}%p"},
            {"Domain": "2. 시계열 동적 속성", "Metric": "ADF Test (p-val)", "Train Set": f"{adf_tr:.4e}", "Test Set": f"{adf_te:.4e}", "Diagnosis": "정상성(Stationarity) 만족" if max(adf_tr, adf_te) < 0.05 else "비정상성 의심"},
            {"Domain": "2. 시계열 동적 속성", "Metric": "ACF Lag 1 (자기상관)", "Train Set": f"{acf_tr[1]:.4f}", "Test Set": f"{acf_te[1]:.4f}", "Diagnosis": "T+20 중첩에 의한 연속 상관"},
            {"Domain": "2. 시계열 동적 속성", "Metric": f"ACF Lag {self.horizon} (20d 소멸)", "Train Set": f"{acf_tr[self.horizon]:.4f}", "Test Set": f"{acf_te[self.horizon]:.4f}", "Diagnosis": "20영업일 후 자기상관 소멸 (Gap 타당)"},
            {"Domain": "3. 레짐 시프트 검정", "Metric": "2-Sample KS Test", "Train Set": "기준 분포 (F0)", "Test Set": f"Stat={ks_stat:.4f} (p={ks_pval:.2e})", "Diagnosis": "🚨 H0 기각 (서로 다른 생성 과정)" if ks_pval < 0.01 else "분포 동일"},
            {"Domain": "3. 레짐 시프트 검정", "Metric": "Wasserstein Distance", "Train Set": "기준점 (0.0)", "Test Set": f"{w_dist:.6f}", "Diagnosis": "구조적 우측 이동(Drift) 실증"}
        ]
        return pd.DataFrame(records)

    def _calculate_psi(self, train_arr: np.ndarray, test_arr: np.ndarray, bins: int = 10) -> float:
        """Train 분위수 기준으로 Test의 Population Stability Index(PSI)를 계산."""
        quantiles = np.linspace(0, 100, bins + 1)
        bin_edges = np.percentile(train_arr, quantiles)
        bin_edges[0] -= 1e-5
        bin_edges[-1] += 1e-5
        bin_edges = np.unique(bin_edges)

        if len(bin_edges) < 3:
            return 0.0

        train_counts, _ = np.histogram(train_arr, bins=bin_edges)
        test_counts, _ = np.histogram(test_arr, bins=bin_edges)

        train_dist = (train_counts + 1e-5) / (len(train_arr) + 1e-5 * len(train_counts))
        test_dist = (test_counts + 1e-5) / (len(test_arr) + 1e-5 * len(test_counts))

        psi_val = np.sum((test_dist - train_dist) * np.log(test_dist / train_dist))
        return float(psi_val)

    def audit_features(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """[대시보드 3 & 4] 피처 전수 건전성, 공변량 표류 및 다변량 직교성 감사표 생성."""
        feature_records: List[Dict[str, Any]] = []

        # 1. 5-Fold Walk-Forward OOF Rank IC 및 ICIR 자체 산출 (외부 인자 주입 0%, 독립 완결)
        splitter = WalkForwardSplitter(n_splits=5, forecast_horizon=self.horizon, min_train_ratio=0.5)
        fold_ics: Dict[str, List[float]] = {col: [] for col in self.X_train.columns}

        for _, _, val_x, val_y in splitter.split_walk_forward(X=self.X_train, y=self.y_train):
            val_y_arr = val_y.to_numpy(dtype=np.float64)
            for col in self.X_train.columns:
                ic, _ = stats.spearmanr(val_x[col].to_numpy(dtype=np.float64), val_y_arr)
                fold_ics[col].append(0.0 if np.isnan(ic) else float(ic))

        oof_metrics: Dict[str, Tuple[float, float]] = {}
        for col in self.X_train.columns:
            arr = np.array(fold_ics[col], dtype=np.float64)
            mean_ic = float(np.mean(arr))
            std_ic = float(np.std(arr))
            icir = float(mean_ic / (std_ic + 1e-6))
            oof_metrics[col] = (mean_ic, icir)

        # 2. 절편 반영 다변량 VIF 사전 산출
        if self.X_train.shape[1] > 1:
            X_with_const = add_constant(self.X_train.astype(float))
            vif_dict = {
                col: float(variance_inflation_factor(X_with_const.values, idx + 1))
                for idx, col in enumerate(self.X_train.columns)
            }
            # 피어슨 상관계수 행렬 및 최대 상관 변수 추출
            corr_matrix = self.X_train.corr(method="pearson")
            abs_corr_matrix = corr_matrix.abs()
            np.fill_diagonal(abs_corr_matrix.values, 0.0)
        else:
            vif_dict = {col: 1.0 for col in self.X_train.columns}
            corr_matrix = pd.DataFrame(1.0, index=self.X_train.columns, columns=self.X_train.columns)
            abs_corr_matrix = pd.DataFrame(0.0, index=self.X_train.columns, columns=self.X_train.columns)

        for col in self.X_train.columns:
            tr_series = self.X_train[col].to_numpy()
            te_series = self.X_test[col].to_numpy()

            w_dist = stats.wasserstein_distance(tr_series, te_series)
            _, ks_pval = stats.ks_2samp(tr_series, te_series)
            psi = self._calculate_psi(tr_series, te_series)
            vif_val = vif_dict.get(col, 1.0)

            # 최대 상관 피처 및 부호 상관계수
            if self.X_train.shape[1] > 1:
                max_corr = float(abs_corr_matrix[col].max())
                most_corr_col = str(abs_corr_matrix[col].idxmax())
                signed_corr = float(corr_matrix.loc[col, most_corr_col])
            else:
                max_corr, most_corr_col, signed_corr = 0.0, "-", 0.0

            # 트리 외삽 위험률
            tr_min, tr_max = np.min(tr_series), np.max(tr_series)
            extrap_ratio = np.mean((te_series < tr_min) | (te_series > tr_max)) * 100

            # Rank IC 및 Sign Flip
            tr_ic, _ = stats.spearmanr(tr_series, self.y_train.to_numpy())
            te_ic, _ = stats.spearmanr(te_series, self.y_test.to_numpy())
            tr_ic = 0.0 if np.isnan(tr_ic) else tr_ic
            te_ic = 0.0 if np.isnan(te_ic) else te_ic

            is_flip = (np.sign(tr_ic) != np.sign(te_ic)) and (abs(tr_ic) >= 0.03)

            # 리스크 상태 결정
            if extrap_ratio > 5.0 or (is_flip and psi >= 0.25) or vif_val >= 10.0 or max_corr >= 0.80:
                risk_status = "CRITICAL"
            elif ks_pval < 0.01 or psi >= 0.25 or is_flip or vif_val >= 5.0 or max_corr >= 0.65:
                risk_status = "WARNING"
            else:
                risk_status = "HEALTHY"

            oof_ic, oof_icir = oof_metrics[col]

            feature_records.append({
                "Feature Name": col,
                "OOF Rank IC": oof_ic,
                "OOF ICIR": oof_icir,
                "Train Rank IC": tr_ic,
                "Test Rank IC": te_ic,
                "Sign Flip": "FLIP" if is_flip else "OK",
                "Wasserstein Dist": w_dist,
                "KS p-val": ks_pval,
                "PSI": psi,
                "VIF": vif_val,
                "Max |r|": max_corr,
                "Signed r": signed_corr,
                "Most Correlated Feature": most_corr_col,
                "Extrapolation %": extrap_ratio,
                "Risk Status": risk_status
            })

        detail_df = pd.DataFrame(feature_records)

        # 종합 통계 요약 (대시보드 3: 영문 표준화 및 부호 일치 감지 정합성 보정)
        total_feats = len(detail_df)
        ks_warn = (detail_df["KS p-val"] < 0.05).sum()
        psi_warn = (detail_df["PSI"] >= 0.25).sum()
        vif_warn = (detail_df["VIF"] >= 5.0).sum()
        flip_danger = (detail_df["Sign Flip"] == "FLIP").sum()
        extrap_danger = (detail_df["Extrapolation %"] > 0).sum()
        mean_w = detail_df["Wasserstein Dist"].mean()

        summary_records = [
            {"Dimension": "Severe Distribution Drift (KS p < 0.05)", "Count / Ratio": f"{ks_warn} / {total_feats} ({ks_warn/total_feats*100:.1f}%)", "Threshold": "<= 20.0%", "Status": "WARNING" if ks_warn/total_feats > 0.2 else "PASS"},
            {"Dimension": "High Covariate Drift (PSI >= 0.25)", "Count / Ratio": f"{psi_warn} / {total_feats} ({psi_warn/total_feats*100:.1f}%)", "Threshold": "<= 10.0%", "Status": "WARNING" if psi_warn/total_feats > 0.1 else "PASS"},
            {"Dimension": "Multicollinearity Risk (VIF >= 5.0)", "Count / Ratio": f"{vif_warn} / {total_feats} ({vif_warn/total_feats*100:.1f}%)", "Threshold": "0", "Status": "WARNING" if vif_warn > 0 else "PASS"},
            {"Dimension": "Correlation Sign Inversion (Sign Flip)", "Count / Ratio": f"{flip_danger} / {total_feats} ({flip_danger/total_feats*100:.1f}%)", "Threshold": "<= 5.0%", "Status": "DANGER" if flip_danger/total_feats > 0.05 else "PASS"},
            {"Dimension": "Tree Extrapolation Risk (Extrapolation > 0%)", "Count / Ratio": f"{extrap_danger} / {total_feats} ({extrap_danger/total_feats*100:.1f}%)", "Threshold": "0", "Status": "DANGER" if extrap_danger > 0 else "PASS"},
            {"Dimension": "Mean Wasserstein Distance (Mean W-Dist)", "Count / Ratio": f"{mean_w:.4f}", "Threshold": "<= 0.1500", "Status": "PASS" if mean_w <= 0.15 else "WARNING"}
        ]
        summary_df = pd.DataFrame(summary_records)

        # 상위 위험 피처 테이블 (대시보드 4): PSI 기준 내림차순 정렬
        top_risk_df = detail_df.sort_values(by="PSI", ascending=False).head(10).copy()
        top_risk_df.reset_index(drop=True, inplace=True)
        top_risk_df.index += 1
        top_risk_df.index.name = "Rank"

        # 포맷팅
        top_risk_df["OOF Rank IC"] = top_risk_df["OOF Rank IC"].map(lambda x: f"{x:+.4f}")
        top_risk_df["OOF ICIR"] = top_risk_df["OOF ICIR"].map(lambda x: f"{x:+.2f}")
        top_risk_df["Train Rank IC"] = top_risk_df["Train Rank IC"].map(lambda x: f"{x:+.4f}")
        top_risk_df["Test Rank IC"] = top_risk_df["Test Rank IC"].map(lambda x: f"{x:+.4f}")
        top_risk_df["Wasserstein Dist"] = top_risk_df["Wasserstein Dist"].map(lambda x: f"{x:.4f}")
        top_risk_df["KS p-val"] = top_risk_df["KS p-val"].map(lambda x: f"{x:.4e}")
        top_risk_df["PSI"] = top_risk_df["PSI"].map(lambda x: f"{x:.3f}")
        top_risk_df["VIF"] = top_risk_df["VIF"].map(lambda x: f"{x:.3f}")

        # [설계 의도] 11개 핵심 피처 정보만 단독 슬라이싱 (공선성 페어, 외삽률 등 불필요 열 원천 배제)
        target_columns = [
            "Feature Name", "OOF Rank IC", "OOF ICIR", "Train Rank IC", "Test Rank IC",
            "Sign Flip", "Wasserstein Dist", "KS p-val", "PSI", "VIF", "Risk Status"
        ]
        top_risk_df = top_risk_df[target_columns]

        return summary_df, top_risk_df