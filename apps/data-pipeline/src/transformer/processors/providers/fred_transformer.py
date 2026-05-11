"""
[모듈 제목]
FREDTransformer - 미국 세인트루이스 연방준비은행 데이터 정제 변환기

[모듈 목적 및 상세 설명]
AbstractTransformer를 상속받아, FRED API에서 수집된 Bronze 레이어의 시계열 JSON 데이터를 
Silver 레이어 적재를 위한 평면적 2D 테이블 형태(DataFrame)로 변환합니다.
transformer.yml에 정의된 정책(policy)을 주입받아, 하드코딩 없이 동적으로 컬럼 평탄화, 필터링, 타입 캐스팅을 수행합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: ReaderService로부터 전달받은 FRED API 원본 데이터 (DataFrame) 및 transformer.yml의 정책 딕셔너리.
2. Validation: 정책 내 `explode_target` (일반적으로 'observations') 컬럼이 실제 데이터에 존재하는지 무결성 사전 검사.
3. Apply Transform: 불필요한 메타데이터(realtime_start 등)를 드롭하고, `observations` 내부의 배열(List)을 행(Row)으로 전개(Explode)한 뒤 열(Column)로 평탄화(Flattening).
4. Enforce Schema: 원본 키(예: date, value)를 사내 표준 명칭(예: trade_date, value)으로 변경 후 float32/string 등으로 엄격하게 타입 캐스팅. FRED 특유의 결측치(".")를 안전하게 NaN으로 치환.
5. Output: 최종 정제되어 DW/Mart 적재 준비가 완료된 Silver DataFrame 반환.

주요 기능:
- Array Explode & Flattening: 배열 데이터를 행으로 풀어낸 뒤 `pd.json_normalize`를 활용한 고속 중첩 구조 해제.
- Missing Value Coercion: FRED API 고유의 `"."` 결측치를 안전하게 `NaN`으로 자동 캐스팅.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약. 반드시 모든 코드 내용을 작성. 가혹할정도로 코드를 재확인하면서 작성.
1. pandas의 explode() 후 json_normalize() 적용:
   - 장점: FRED API는 KIS의 단일 딕셔너리와 달리 `[{date: ..., value: ...}, ...]` 형태의 리스트를 반환합니다. 이를 `explode()`로 먼저 행 단위로 쪼갠 뒤 C 엔진 기반의 `json_normalize`로 밀어넣으면 수십 년치 일별 데이터(약 1만 건)도 밀리초(ms) 단위로 고속 처리됩니다.
   - 단점: 빈 배열이나 리스트가 아닌 잘못된 타입이 들어올 경우 explode 과정에서 인덱스가 꼬이거나 에러가 발생할 수 있습니다.
   - 근거: API 응답이 성공했다면 observations는 반드시 리스트로 반환된다는 FRED API의 Data Contract를 신뢰하고, 병목을 최소화하는 네이티브 벡터화 방식을 채택하는 것이 대용량 처리에 유리합니다.
2. 타입 변환 시 errors='coerce' 활용 (Strict Schema Enforcement):
   - 장점: FRED 데이터는 휴일 등 값이 없을 때 `value: "."` 이라는 문자열을 반환합니다. 이를 수동으로 if문으로 예외 처리하지 않고, `pd.to_numeric(errors='coerce')`를 사용하면 일괄적으로 `NaN`으로 우아하게(Graceful) 캐스팅됩니다.
   - 단점: `"."` 뿐만 아니라 아예 잘못된 쓰레기 문자열이 들어와도 에러 없이 `NaN`으로 덮어써지므로 원본의 오염을 조기에 발견하지 못할 위험이 일부 있습니다.
   - 근거: 시계열 금융/매크로 분석에서는 결측치를 `NaN`으로 두고 DW에서 보간(Interpolation)하거나 ffill(Forward Fill) 처리하는 것이 표준 파이프라인이므로, 변환기 단계에서는 조용히 `NaN`으로 밀어주는 것이 가장 역할 분담에 맞습니다.
"""

from typing import Any, Dict
import pandas as pd
import ast

from src.transformer.processors.abstract_transformer import AbstractTransformer
from src.common.exceptions import TransformerError


class FREDTransformer(AbstractTransformer):
    """세인트루이스 연은(FRED) API 데이터를 처리하는 구체화된 변환기 클래스."""

    def __init__(self, config: Any, policy: Dict[str, Any]):
        """FREDTransformer 초기화 및 의존성/정책 주입."""
        super().__init__(config)
        self.policy = policy

    def _validate(self, data: pd.DataFrame, **kwargs: Any) -> None:
        """변환 전 정책과 데이터 간의 필수 무결성을 검증합니다."""
        explode_target = self.policy.get("explode_target")
        
        if explode_target and explode_target not in data.columns:
            raise TransformerError(
                message=f"[FREDTransformer] 무결성 오류: 평탄화 대상 컬럼 '{explode_target}'이(가) 데이터에 존재하지 않습니다.",
                should_retry=False
            )

    def _parse_dict_safe(self, val: Any) -> Any:
        """문자열로 파싱된 리스트/딕셔너리를 안전하게 실제 파이썬 객체로 변환합니다."""
        if isinstance(val, (dict, list)):
            return val
        if isinstance(val, str):
            try:
                return ast.literal_eval(val)
            except Exception:
                return val
        return val

    def _apply_transform(self, data: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """불필요한 컬럼을 제거하고 observations 배열을 행과 열로 평탄화합니다."""
        df = data.copy()
        
        # 1. 불필요한 메타데이터 컬럼 사전 제거 (가벼운 메모리 상태 확보)
        drop_cols = self.policy.get("drop_columns", [])
        existing_drop_cols = [col for col in drop_cols if col in df.columns]
        if existing_drop_cols:
            df = df.drop(columns=existing_drop_cols)
            
        # 2. 타겟 배열 컬럼 전개 (Explode -> Flattening)
        explode_target = self.policy.get("explode_target")
        if explode_target and explode_target in df.columns:
            # 문자열로 파싱되어 있을 수 있으므로 실제 리스트 객체로 변환
            df[explode_target] = df[explode_target].apply(self._parse_dict_safe)
            
            # 리스트(배열)를 각각의 행(Row)으로 분리
            df = df.explode(explode_target).reset_index(drop=True)
            
            # 행으로 분리된 딕셔너리들의 Key를 컬럼으로 전개
            if not df[explode_target].isna().all():
                exploded_df = pd.json_normalize(df[explode_target].tolist())
                
                # 원본 타겟 컬럼 삭제 및 전개된 컬럼 병합
                df = df.drop(columns=[explode_target])
                df = pd.concat([df, exploded_df], axis=1)
            else:
                df = df.drop(columns=[explode_target])
                
        return df

    def _enforce_schema(self, data: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """YAML Data Contract에 맞춰 컬럼명을 치환하고, FRED 고유의 결측치('.')를 처리하며 타입을 캐스팅합니다."""
        df = data.copy()
        schema_rules = self.policy.get("schema", {})
        
        rename_map = {}
        type_map = {}
        
        # 1. 설정 매핑 추출
        for orig_col, rules in schema_rules.items():
            if orig_col in df.columns:
                target_name = rules.get("name", orig_col)
                target_type = rules.get("type")
                
                rename_map[orig_col] = target_name
                if target_type:
                    type_map[target_name] = target_type

        # 2. 컬럼명 표준화 변경
        df = df.rename(columns=rename_map)
        
        # 3. Data Contract 강제 (정의되지 않은 Garbage Column 원천 드롭)
        target_columns = list(type_map.keys())
        df = df[[col for col in target_columns if col in df.columns]]
        
        # 4. 데이터 타입 캐스팅 (Vectorized)
        for col, dtype in type_map.items():
            if col in df.columns:
                try:
                    # FRED의 "." 같은 결측치 처리를 위해 coerce 옵션 필수 적용
                    if dtype in ["float32", "float64", "int32", "int64"]:
                        df[col] = pd.to_numeric(df[col], errors='coerce').astype(dtype)
                    else:
                        df[col] = df[col].astype(dtype)
                except Exception as e:
                    self.logger.warning(f"[FREDTransformer] 타입 변환 실패 ({col} -> {dtype}): {e}")
                    
        return df