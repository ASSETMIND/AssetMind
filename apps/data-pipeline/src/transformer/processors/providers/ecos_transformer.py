"""
AbstractTransformer를 상속받아, ECOS API에서 수집된 Bronze 레이어의 시계열 JSON 데이터를 
Silver 레이어 적재를 위한 평면적 2D 테이블 형태(DataFrame)로 변환합니다.
transformer.yml에 정의된 정책(policy)을 주입받아, 하드코딩 없이 동적으로 컬럼 평탄화, 
ECOS 특유의 중첩 배열 추출('row' 키), 타입 캐스팅을 수행합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: ReaderService로부터 전달받은 ECOS API 원본 데이터(DataFrame) 및 transformer.yml의 정책 딕셔너리.
2. Validation: 정책 내 `explode_target` (일반적으로 'StatisticSearch') 컬럼이 실제 데이터에 존재하는지 무결성 사전 검사.
3. Apply Transform: 
   - `StatisticSearch` 내부의 불필요한 메타데이터('list_total_count' 등)를 무시하고 실제 데이터 배열이 담긴 `'row'` 키를 추출합니다.
   - 추출된 리스트를 `explode()`를 통해 행(Row)으로 전개한 뒤, `pd.json_normalize()`로 열(Column) 평탄화(Flattening)를 수행합니다.
4. Enforce Schema: 원본 키(TIME, DATA_VALUE)를 사내 표준 명칭(trade_date, value)으로 변경하고 float32/string 등으로 엄격하게 타입 캐스팅합니다.
5. Output: 최종 정제되어 DW/Mart 적재 준비가 완료된 Silver DataFrame 반환.

주요 기능:
- Nested Array Extraction: ECOS API 특유의 `[Target] -> 'row' -> Array` 형태의 중첩 구조에서 핵심 시계열 배열만 추출.
- Array Explode & Flattening: 배열 데이터를 행으로 풀어낸 뒤 `pd.json_normalize`를 활용한 고속 중첩 구조 해제.
- Dynamic Data Contract: 하드코딩된 컬럼 조작 없이 YAML 정책 기반의 동적 스키마 강제 적용.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약. 반드시 모든 코드 내용을 작성. 가혹할정도로 코드를 재확인하면서 작성.
1. 'row' 키 내부 데이터 추출 후 explode() 수행:
   - 장점: ECOS API는 데이터 반환 시 `{'StatisticSearch': {'list_total_count': 1, 'row': [...]}}` 형태를 띱니다. 이를 `apply()`로 `'row'`만 추출하여 리스트로 덮어씌운 뒤 전개하면, 메타데이터와 핵심 데이터를 분리하는 복잡한 로직 없이 네이티브한 pandas 벡터화 체인에 태울 수 있습니다.
   - 단점: 만약 ECOS API의 응답 스키마가 변경되거나 통계 데이터가 없어 `'row'` 키가 누락된 경우, 빈 리스트로 처리되어 에러 없이 데이터가 조용히 유실될(Silent Failure) 위험이 존재합니다.
   - 근거: 한국은행 공공 API의 Data Contract는 매우 보수적이므로 응답 구조가 임의로 변경될 확률이 희박합니다. 복잡한 if-else 방어 로직으로 성능 병목을 만드는 것보다, 빠르고 직관적인 Key 접근 방식을 채택하는 것이 대규모 파이프라인 처리에 적합합니다.
2. 문자열 파싱(_parse_dict_safe) 및 DataFrame 내재화:
   - 장점: S3에서 파케이(Parquet)나 CSV로 로드될 때 JSON이 문자열(String)로 캐스팅된 경우에도 `ast.literal_eval`을 통해 안전하게 파이썬 딕셔너리로 복구할 수 있어 파이프라인의 회복탄력성(Resilience)이 매우 높습니다.
   - 단점: 모든 행에 대해 파싱을 시도하므로, 이미 완전한 딕셔너리 객체인 경우 미세한 함수 호출 오버헤드가 발생합니다.
   - 근거: Bronze 레이어의 데이터 타입은 직렬화/역직렬화 과정에서 오염될 가능성이 높습니다. 약간의 오버헤드를 감수하더라도 확실한 무결성을 보장하는 방어적 프로그래밍(Defensive Programming)이 장애 복구 비용보다 훨씬 저렴합니다.
"""

import ast
from typing import Any, Dict
import pandas as pd

from src.transformer.processors.abstract_transformer import AbstractTransformer
from src.common.exceptions import TransformerError


class ECOSTransformer(AbstractTransformer):
    """한국은행(ECOS) API 데이터를 처리하는 구체화된 변환기 클래스.
    
    Attributes:
        policy (Dict[str, Any]): transformer.yml에서 추출된 ecos_base_schema 변환 규칙.
    """

    def __init__(self, config: Any, policy: Dict[str, Any]):
        """ECOSTransformer 초기화 및 의존성/정책 주입.
        
        Args:
            config (ConfigManager): 글로벌 로거 및 시스템 설정을 위한 앱 객체.
            policy (Dict[str, Any]): 동적으로 할당된 스키마 정책 (예: ecos_base_schema).
        """
        super().__init__(config)
        self.policy = policy

    def _validate(self, data: pd.DataFrame, **kwargs: Any) -> None:
        """변환 전 정책과 데이터 간의 필수 무결성을 검증합니다.
        
        Args:
            data (pd.DataFrame): 검증할 원본 데이터프레임.
            **kwargs: 추가 파라미터.
            
        Raises:
            TransformerError: 평탄화 대상 컬럼이 존재하지 않을 경우.
        """
        explode_target = self.policy.get("explode_target")
        
        if explode_target and explode_target not in data.columns:
            raise TransformerError(
                message=f"[ECOSTransformer] 무결성 오류: 평탄화 대상 컬럼 '{explode_target}'이(가) 데이터에 존재하지 않습니다.",
                should_retry=False
            )

    def _parse_dict_safe(self, val: Any) -> Any:
        """문자열로 파싱된 딕셔너리/리스트를 안전하게 실제 파이썬 객체로 변환합니다.
        
        Args:
            val (Any): 변환할 대상 값.
            
        Returns:
            Any: 딕셔너리 또는 리스트로 복구된 객체, 실패 시 원본 값.
        """
        if isinstance(val, (dict, list)):
            return val
        if isinstance(val, str):
            try:
                return ast.literal_eval(val)
            except Exception:
                return val
        return val

    def _extract_row_array(self, val: Any) -> list:
        """ECOS 응답 객체에서 실제 데이터 배열인 'row' 키의 값을 추출합니다.
        
        Args:
            val (Any): 파싱된 ECOS 최상위 응답 객체 (일반적으로 Dict).
            
        Returns:
            list: 'row' 키에 해당하는 배열. 없을 경우 빈 리스트 반환.
        """
        parsed_val = self._parse_dict_safe(val)
        if isinstance(parsed_val, dict):
            return parsed_val.get("row", [])
        return []

    def _apply_transform(self, data: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """ECOS 특유의 중첩 구조에서 'row'를 추출하고, 데이터를 평탄화합니다.
        
        Args:
            data (pd.DataFrame): 변환할 대상 원본 데이터프레임.
            **kwargs: 추가 파라미터.
            
        Returns:
            pd.DataFrame: 2D 테이블 형태로 평탄화된 데이터프레임.
        """
        df = data.copy()
        
        # 1. 불필요한 메타데이터 컬럼 사전 제거 (가벼운 메모리 상태 확보)
        drop_cols = self.policy.get("drop_columns", [])
        existing_drop_cols = [col for col in drop_cols if col in df.columns]
        if existing_drop_cols:
            df = df.drop(columns=existing_drop_cols)
            
        # 2. 타겟 컬럼 전개 (Extraction -> Explode -> Flattening)
        explode_target = self.policy.get("explode_target")
        if explode_target and explode_target in df.columns:
            
            # 2.1 ECOS 구조에 맞춰 'StatisticSearch' 내부의 'row' 배열만 추출
            df[explode_target] = df[explode_target].apply(self._extract_row_array)
            
            # 2.2 리스트(배열)를 각각의 행(Row)으로 분리 (1행 -> N행)
            df = df.explode(explode_target).reset_index(drop=True)
            
            # 2.3 행으로 분리된 딕셔너리들의 Key(TIME, DATA_VALUE 등)를 열(Column)로 전개
            if not df[explode_target].isna().all():
                # [설계 의도] C엔진 기반의 json_normalize를 활용하여 수천 건의 dict를 순식간에 컬럼으로 전개함
                exploded_df = pd.json_normalize(df[explode_target].tolist())
                
                # 원본 타겟 컬럼 삭제 및 전개된 컬럼 병합
                df = df.drop(columns=[explode_target])
                df = pd.concat([df, exploded_df], axis=1)
            else:
                # 데이터가 아예 없는 경우 타겟 컬럼만 제거하고 빈 상태 유지
                df = df.drop(columns=[explode_target])
                
        return df

    def _enforce_schema(self, data: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """YAML Data Contract에 맞춰 컬럼명을 치환하고 데이터 타입을 강력하게 캐스팅합니다.
        
        Args:
            data (pd.DataFrame): 평탄화가 완료된 데이터프레임.
            **kwargs: 추가 파라미터.
            
        Returns:
            pd.DataFrame: Silver 레이어 표준 스키마가 적용된 최종 데이터프레임.
        """
        df = data.copy()
        schema_rules = self.policy.get("schema", {})
        
        rename_map = {}
        type_map = {}
        
        # 1. 설정 매핑 추출 (yml 기반 동적 매핑)
        for orig_col, rules in schema_rules.items():
            if orig_col in df.columns:
                target_name = rules.get("name", orig_col)
                target_type = rules.get("type")
                
                rename_map[orig_col] = target_name
                if target_type:
                    type_map[target_name] = target_type

        # 2. 컬럼명 표준화 변경 (예: TIME -> trade_date)
        df = df.rename(columns=rename_map)
        
        # 3. Data Contract 강제 (정의되지 않은 Garbage Column 원천 드롭)
        target_columns = list(type_map.keys())
        df = df[[col for col in target_columns if col in df.columns]]
        
        # 4. 데이터 타입 캐스팅 (Vectorized)
        for col, dtype in type_map.items():
            if col in df.columns:
                try:
                    # 결측치 방어를 위해 pd.to_numeric(errors='coerce') 사용 (수치형 한정)
                    if dtype in ["float32", "float64", "int32", "int64"]:
                        df[col] = pd.to_numeric(df[col], errors='coerce').astype(dtype)
                    else:
                        df[col] = df[col].astype(dtype)
                except Exception as e:
                    self.logger.warning(f"[ECOSTransformer] 타입 변환 실패 ({col} -> {dtype}): {e}")
                    
        return df