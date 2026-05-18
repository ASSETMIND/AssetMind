"""
AbstractTransformer를 상속받아, UPBIT API(가상자산 일별/분별 캔들 데이터)에서 수집된 Bronze 레이어의 JSON 배열 데이터를 
Silver 레이어 적재를 위한 평면적 2D 테이블 형태(DataFrame)로 변환합니다.
Upbit API 응답은 기본적으로 1 Depth의 List[Dict] 형태를 가지므로 복잡한 전개(Explode) 과정 없이,
transformer.yml에 정의된 정책(policy)을 기반으로 컬럼명 표준화 및 데이터 타입 강제(Type Casting)에 집중합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: ReaderService로부터 전달받은 UPBIT API 원본 데이터(List[Dict] 기반 DataFrame) 및 transformer.yml의 정책 딕셔너리.
2. Validation: 데이터프레임이 비어있는지 1차 무결성 검증을 수행합니다.
3. Apply Transform: 불필요한 메타데이터(설정된 drop_columns)를 드롭합니다. 데이터가 이미 평탄화되어 있으므로 추가적인 Flattening 연산은 생략합니다.
4. Enforce Schema: 원본 키(예: trade_price, candle_acc_trade_volume)를 사내 표준 명칭(예: close, volume)으로 변경 후 float32/string 등으로 엄격하게 타입 캐스팅합니다.
5. Output: 최종 정제되어 DW/Mart(Silver 레이어) 적재 준비가 완료된 DataFrame을 반환합니다.

주요 기능:
- Zero-Overhead Transformation: 기본적으로 평탄화된 배열로 들어오는 특성을 활용하여 최소한의 연산으로 DataFrame 매핑.
- Dynamic Data Contract: 하드코딩된 컬럼 조작 없이 YAML 정책 기반의 동적 스키마 강제 적용.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약. 반드시 모든 코드 내용을 작성. 가혹할정도로 코드를 재확인하면서 작성.
1. 평탄화(Flattening) 로직 제거 (Zero-Overhead):
   - 장점: Upbit API는 응답 자체가 `[{"market": "KRW-BTC", "trade_price": 50000}, ...]` 형태의 1차원 배열이므로, 상위 추상 클래스(AbstractTransformer)에서 `pd.DataFrame(data)` 호출만으로 이미 완벽한 2D 테이블이 구성됩니다. 따라서 KIS/ECOS와 달리 추가적인 `explode`나 `json_normalize` 연산을 생략하여 CPU 연산 시간과 메모리 사용량을 최소화합니다.
   - 단점: 만약 Upbit 거래소 측에서 API 응답 구조를 `{ "status": "ok", "data": [...] }`와 같이 중첩 구조로 일방적으로 변경할 경우, 평탄화 타겟 지정이 안 되어 있어 전체 파이프라인 변환이 실패하게 됩니다.
   - 근거: 거래소 공용 Open API의 Data Contract 상 기본 최상위 응답 구조(Root Structure)가 변경될 확률은 극히 낮습니다. 구조가 완전히 개편된다면 Silver 계층의 정제 로직 추가가 아니라 Bronze 추출(Extractor) 모듈에서 대응하는 것이 마이크로서비스 및 파이프라인 아키텍처 상 올바른 책임 분배입니다. 오버엔지니어링을 피하기 위해 현 1D 구조에 최적화된 패스스루(Pass-through) 방식을 채택했습니다.
2. 데이터 타입 강제 캐스팅(coerce) 및 예외 로그:
   - 장점: 코인 시장의 특성상 거래소 점검, 일시적 API 오류, 혹은 거래량(Volume) 데이터 누락 등으로 인해 'null'이나 빈 문자열이 유입될 수 있습니다. `pd.to_numeric(errors='coerce')`를 사용하면 네이티브 예외(Exception)를 던져 파이프라인 전체를 다운시키는 대신, 해당 비정상 값들을 일괄적으로 `NaN`으로 치환하여 파이프라인의 강건성(Robustness)을 유지합니다.
   - 단점: 정상적이지 않은 문자열(예: "System Error")이 숫자형 컬럼에 섞여 들어와도 에러를 발생시키지 않고 조용히 결측치로 덮어쓰기 때문에(Silent Failure), 데이터 오염을 즉각적으로 인지하기 지연될 수 있습니다.
   - 근거: 대규모 스트리밍/일별 데이터 파이프라인에서는 특정 Row의 일시적 포맷 에러 때문에 전체 Job이 중단되는 것이 비즈니스 임팩트에 더 큰 손실을 야기합니다. 변환(Transformer) 단계에서는 데이터를 누락 없이 흘려보내되 결측치로 안전하게 치환(Safe Coercion)하고, 최종적인 결측치 처리(Imputation) 전략은 모델링 도메인을 담당하는 Gold 레이어(Feature Store 전처리)로 위임하는 것이 Data Engineering의 Best Practice입니다.
"""

from typing import Any, Dict
import pandas as pd

# 프로젝트 내부 모듈 의존성
from src.transformer.processors.abstract_transformer import AbstractTransformer
from src.common.exceptions import TransformerError


class UPBITTransformer(AbstractTransformer):
    """업비트(UPBIT) 가상자산 시세/캔들 데이터를 처리하는 구체화된 변환기 클래스.
    
    Attributes:
        policy (Dict[str, Any]): transformer.yml에서 추출된 upbit_base_schema 변환 규칙.
    """

    def __init__(self, config: Any, policy: Dict[str, Any]) -> None:
        """UPBITTransformer 초기화 및 의존성/정책 주입.
        
        Args:
            config (Any): 글로벌 설정 관리 객체 (로깅 및 공통 메타데이터 포괄).
            policy (Dict[str, Any]): transformer.yml의 'policy' 하위 라우팅 규칙 (스키마 매핑 정보 포함).
        """
        super().__init__(config)
        self.policy = policy

    def _validate(self, data: pd.DataFrame, **kwargs: Any) -> None:
        """변환 전 원본 데이터프레임의 필수 무결성을 방어적으로 검증합니다.
        
        Upbit 데이터는 최상위 객체가 배열이므로 별도의 explode_target을 확인하지 않습니다.
        대신 입력 데이터프레임의 생존 여부(비어있는지)를 Entry Point에서 철저히 검증합니다.

        Args:
            data (pd.DataFrame): 검증할 원본 데이터프레임.
            **kwargs: 추가 파라미터.
            
        Raises:
            TransformerError: 데이터프레임이 완전히 비어있어 변환이 불가능한 경우.
        """
        if data is None or data.empty:
            raise TransformerError(
                message="[UPBITTransformer] 무결성 검증 실패: 입력 데이터프레임이 비어 있습니다. 파이프라인 추출 계층(Extractor)을 확인하세요.",
                should_retry=False
            )

    def _apply_transform(self, data: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """단일 컬럼 내부에 래핑된 업비트 딕셔너리 데이터를 가로로 평탄화(Flattening)합니다.
        
        Args:
            data (pd.DataFrame): 변환할 대상 원본 데이터프레임.
            **kwargs: 추가 파라미터.
            
        Returns:
            pd.DataFrame: 드롭 필터링이 완료된 데이터프레임.
        """
        df = data.copy()
        
        # 1. 불필요한 메타데이터 드롭
        drop_cols = self.policy.get("drop_columns", [])
        existing_drop_cols = [col for col in drop_cols if col in df.columns]
        if existing_drop_cols:
            df = df.drop(columns=existing_drop_cols)
            
        # 2. 타겟 컬럼 전개 (가로 평탄화)
        explode_target = self.policy.get("explode_target")
        
        if explode_target is not None:
            # [설계 의도] Pandas가 "0"을 문자열(str)로 읽을지 정수(int)로 읽을지 
            # 런타임 환경에 따라 다르므로 안전한 바인딩(Safe Binding)을 수행합니다.
            target_col = None
            if explode_target in df.columns:
                target_col = explode_target
            elif str(explode_target) in df.columns:
                target_col = str(explode_target)
            elif str(explode_target).isdigit() and int(explode_target) in df.columns:
                target_col = int(explode_target)
                
            if target_col is not None and not df[target_col].empty:
                # 컬럼 내부의 딕셔너리 리스트를 가로(Column) 축으로 평탄화
                exploded_df = pd.json_normalize(df[target_col].tolist())
                
                # 껍데기 컬럼(0)을 버리고 전개된 데이터를 병합
                df = df.drop(columns=[target_col]).reset_index(drop=True)
                df = pd.concat([df, exploded_df], axis=1)

        return df

    def _enforce_schema(self, data: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """YAML Data Contract에 맞춰 컬럼명을 치환하고 데이터 타입을 강력하게 캐스팅합니다.
        
        Args:
            data (pd.DataFrame): 1차 변환(드롭 등)이 완료된 데이터프레임.
            **kwargs: 추가 파라미터.
            
        Returns:
            pd.DataFrame: Silver 레이어 표준 스키마(Data Contract)가 엄격하게 적용된 데이터프레임.
        """
        df = data.copy()
        schema_rules = self.policy.get("schema", {})
        
        rename_map = {}
        type_map = {}
        
        # 1. 설정 매핑 추출 (yml 기반 동적 스키마 룰 구축)
        for orig_col, rules in schema_rules.items():
            if orig_col in df.columns:
                target_name = rules.get("name", orig_col)
                target_type = rules.get("type")
                
                rename_map[orig_col] = target_name
                if target_type:
                    type_map[target_name] = target_type

        # 2. 컬럼명 표준화 변경 (예: candle_date_time_kst -> trade_date, trade_price -> close)
        df = df.rename(columns=rename_map)
        
        # 3. Data Contract 강제 (정의되지 않은 Garbage Column 원천 드롭하여 Silver 무결성 보장)
        target_columns = list(type_map.keys())
        df = df[[col for col in target_columns if col in df.columns]]
        
        # 4. 데이터 타입 캐스팅 (Vectorized Execution)
        for col, dtype in type_map.items():
            if col in df.columns:
                try:
                    if dtype in ["date", "datetime", "datetime64[ns]"]:
                        df[col] = self._cast_datetime_vectorized(df[col])
                        df[col] = df[col].dt.normalize()
                    elif dtype in ["float32", "float64", "int32", "int64"]:
                        df[col] = pd.to_numeric(df[col], errors='coerce').astype(dtype)
                    else:
                        df[col] = df[col].astype(dtype)
                except Exception as e:
                    self.logger.warning(f"[UPBITTransformer] 타입 변환 중 경고 발생 ({col} -> {dtype}): {e}")
                    
        return df