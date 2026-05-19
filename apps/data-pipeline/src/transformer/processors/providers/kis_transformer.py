"""
AbstractTransformer를 상속받아, KIS API에서 수집된 Bronze 레이어의 중첩 JSON(Nested JSON) 데이터를 
Silver 레이어 적재를 위한 평면적 2D 테이블 형태(DataFrame)로 변환합니다.
transformer.yml에 정의된 정책(policy)을 주입받아, 하드코딩 없이 동적으로 컬럼 평탄화, 필터링, 타입 캐스팅을 수행합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: ReaderService로부터 전달받은 KIS API 원본 데이터 (DataFrame) 및 transformer.yml의 정책 딕셔너리.
2. Validation: 정책 내 `explode_target` 컬럼이 실제 데이터에 존재하는지 무결성 사전 검사.
3. Apply Transform: 불필요한 메타데이터(msg1, rt_cd 등)를 드롭하고, `output1` 내부의 딕셔너리를 열(Column)로 전개(Flattening).
4. Enforce Schema: 원본 키(예: bstp_nmix_prpr)를 사내 표준 명칭(예: close)으로 변경 후 float32/string 등으로 엄격하게 타입 캐스팅.
5. Output: 최종 정제되어 DW/Mart 적재 준비가 완료된 Silver DataFrame 반환.

주요 기능:
- JSON Flattening: `pd.json_normalize`를 활용한 O(1) 수준의 고속 중첩 구조 해제.
- Dynamic Data Contract: 하드코딩된 컬럼 조작 없이 YAML 정책 기반의 동적 스키마 강제 적용.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약. 반드시 모든 코드 내용을 작성. 가혹할정도로 코드를 재확인하면서 작성.
1. pd.json_normalize vs apply(pd.Series) 기반 평탄화:
   - 장점: `json_normalize`는 C 수준에서 딕셔너리를 파싱하여 DataFrame으로 전개하므로, `apply(pd.Series)` 대비 수십 배 빠르고 메모리 사용량이 적습니다.
   - 단점: 중첩 단계가 3 Depth 이상으로 깊어질 경우 파라미터 튜닝이 까다로워질 수 있습니다.
   - 근거: KIS의 응답 구조는 대부분 1 Depth의 중첩 딕셔너리(`output1` 내부)로 구성되어 있으므로, 메모리/CPU 병목을 없애기 위해 가장 빠르고 네이티브한 pandas 벡터화 함수를 사용하는 것이 압도적으로 유리합니다.
2. 타겟 컬럼 외의 데이터 강제 드롭 (Strict Schema Enforcement):
   - 장점: `transformer.yml`의 `schema`에 정의되지 않은 API의 잉여 데이터(가비지 데이터)가 Silver 레이어로 침투하는 것을 원천 차단하여 Data Quality를 보장합니다.
   - 단점: API 응답에 유의미한 신규 필드가 추가되더라도, YAML 설정에 명시하지 않으면 자동으로 유실됩니다.
   - 근거: 데이터 레이크하우스 아키텍처에서는 '알 수 없는 데이터'가 들어와 파이프라인 정합성을 깨뜨리는 것보다, 명시된 'Data Contract(데이터 계약)'만을 엄격히 통과시키는 것이 운영 안정성 확보에 필수적입니다.
"""

from typing import Any, Dict
import pandas as pd

from src.transformer.processors.abstract_transformer import AbstractTransformer
from src.common.exceptions import TransformerError


class KISTransformer(AbstractTransformer):
    """한국투자증권(KIS) API 데이터를 처리하는 구체화된 변환기 클래스.
    
    Attributes:
        policy (Dict[str, Any]): transformer.yml에서 추출된 해당 스키마 그룹의 변환 규칙.
    """

    def __init__(self, config: Any, policy: Dict[str, Any]):
        """KISTransformer 초기화 및 의존성/정책 주입.
        
        Args:
            config (ConfigManager): 글로벌 로거 및 시스템 설정을 위한 앱 객체.
            policy (Dict[str, Any]): 동적으로 할당된 스키마 정책 (예: kis_domestic_schema).
        """
        super().__init__(config)
        self.policy = policy

    def _validate(self, data: pd.DataFrame, **kwargs: Any) -> None:
        """변환 전 정책과 데이터 간의 필수 무결성을 검증합니다."""
        explode_target = self.policy.get("explode_target")
        
        if not explode_target:
            return

        # 단일 문자열(str) 입력 시 리스트로 강제 정규화하여 처리 로직을 통일함
        targets = [explode_target] if isinstance(explode_target, str) else explode_target
        
        for target in targets:
            if target not in data.columns:
                raise TransformerError(
                    message=f"[KISTransformer] 무결성 오류: 평탄화 대상 컬럼 '{target}'이(가) 데이터에 존재하지 않습니다.",
                    should_retry=False
                )

    def _apply_transform(self, data: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """불필요한 컬럼을 제거하고 중첩 딕셔너리(output1 등)를 고속으로 평탄화합니다."""
        df = data.copy()
        
        # 1. 불필요한 메타데이터 컬럼 사전 제거 (가벼운 메모리 상태 확보)
        drop_cols = self.policy.get("drop_columns", [])
        existing_drop_cols = [col for col in drop_cols if col in df.columns]
        if existing_drop_cols:
            df = df.drop(columns=existing_drop_cols)
            
        # 2. 타겟 컬럼 전개 (Flattening)
        explode_target = self.policy.get("explode_target")

        if not explode_target:
            return df
        
        # 단일 문자열(str) 입력 시 리스트로 정규화
        targets = [explode_target] if isinstance(explode_target, str) else explode_target

        # 2. 타겟 컬럼 순차 전개 (Flattening & Broadcasting)
        for target in targets:
            if target in df.columns:
                # [설계 의도] List 타입 대응 (output2)
                # 데이터가 존재하고 첫 번째 요소가 리스트인 경우, pandas 네이티브 explode로 세로(Row) 확장 수행
                if not df[target].empty and isinstance(df[target].dropna().iloc[0], list):
                    df = df.explode(target)

                # 빈 배열([]) 수집 건 등이 결측치가 되었을 경우 안전하게 제거
                df = df.dropna(subset=[target])
                
                # explode 연산 후 붕괴된 Index를 반드시 초기화. 
                # (초기화하지 않으면 뒤의 json_normalize 결과와 index mismatch가 발생하여 NaN이 채워짐)
                df = df.reset_index(drop=True)
                
                # [설계 의도] Dict 타입 가로 평탄화 (output1 및 explode된 output2)
                exploded_df = pd.json_normalize(df[target].tolist())
                
                # 원본 타겟 컬럼 삭제 및 전개된 컬럼을 열(Column) 기준으로 병합
                df = df.drop(columns=[target])

                # 중복 컬럼 방어 - 만약 평탄화된 컬럼이 원본 데이터프레임의 기존 컬럼과 이름이 겹칠 경우, 기존 컬럼을 우선적으로 제거하여 충돌 방지
                overlap_cols = [col for col in exploded_df.columns if col in df.columns]
                if overlap_cols:
                    df = df.drop(columns=overlap_cols)

                df = pd.concat([df, exploded_df], axis=1)
                
        return df

    def _enforce_schema(self, data: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """YAML Data Contract에 맞춰 컬럼명을 치환하고 데이터 타입을 강력하게 캐스팅합니다."""
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
                    if dtype in ["date", "datetime", "datetime64[ns]"]:
                        df[col] = self._cast_datetime_vectorized(df[col])
                    elif dtype in ["float32", "float64", "int32", "int64"]:
                        df[col] = pd.to_numeric(df[col], errors='coerce').astype(dtype)
                    else:
                        df[col] = df[col].astype(dtype)
                except Exception as e:
                    self.logger.warning(f"[KISTransformer] 타입 변환 실패 ({col} -> {dtype}): {e}")
                    
        return df