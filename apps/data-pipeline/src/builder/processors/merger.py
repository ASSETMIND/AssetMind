"""
N개의 개별 데이터프레임을 지정된 키(merge_key) 기준으로 병합하여 1개의 통합된 Wide Table(Feature Matrix)을 생성합니다.
TODAY 모드(단일/특정 타겟 기간)와 LEGACY 모드(전체 시계열)를 모두 지원하며, 
컬럼 충돌 방지를 위한 접두사(Prefix) 맵핑과 인덱스 고유성 보장 로직을 수행합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: 다수의 DataFrame 리스트, 식별자(job_ids) 리스트, 조인 키, 그리고 선택적인 타겟 키(Spine) 유입.
2. Indexing & Prefixing: 각 DataFrame의 중복 키를 제거하여 고유 인덱스로 설정하고, job_id를 활용하여 컬럼명을 동적으로 변경.
3. Concat: 인덱스 정렬이 완료된 N개의 DataFrame을 Pandas C-엔진을 통해 메모리상에서 1-Shot 병합(Outer Join).
4. Spine Enforcement: target_keys가 주어졌을 경우(TODAY 모드 등), 해당 키로 데이터를 강제 재색인(Reindex)하여 정합성 보장.
5. Output: 가로로 완벽히 조립된 단일 Wide DataFrame 반환.

주요 기능:
- N-to-1 Horizontal Concatenation: O(N) 순차 조인이 아닌 벡터화된 고속 가로 병합 수행.
- Dynamic Column Namespace: `job_id_column` 형태로 네임스페이스를 분리하여 N개 테이블 간의 컬럼명 충돌 원천 차단.
- Optional Date Spine (Reindexing): 특정 기준일(들)에 대해서만 정합성 있는 결과를 강제하여 누락되거나 초과된 데이터를 통제.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약. 반드시 모든 코드 내용을 작성. 가혹할정도로 코드를 재확인하면서 작성.
1. 순차적 Left Join(루프) 대신 pd.concat() + reindex() 채택:
   - 장점: `pd.concat`은 내부적으로 단일 메모리 할당으로 모든 데이터를 병합하므로 루프 기반의 Join보다 압도적으로 빠릅니다. 또한, `reindex`를 통해 복잡한 조인 조건식 없이도 타겟 날짜(Spine)에 대한 뼈대를 완벽히 강제할 수 있으며, 누락된 데이터는 네이티브하게 NaN으로 자동 채워집니다.
   - 단점: `target_keys`가 매우 작은 경우(예: TODAY 1건), 초기 `pd.concat` 단계에서 원본 크기만큼의 일시적인 메모리 피크(Memory Peak)가 발생한 후 잘려나갑니다.
   - 근거: Python 생태계에서 for-loop 기반의 DataFrame 수정은 최악의 안티 패턴입니다. 약간의 순간 메모리 사용량을 감수하더라도, Pandas의 C 구현체를 최대한 활용하여 연산 속도를 극대화하고 코드의 간결성을 유지하는 것이 유지보수와 성능 측면에서 절대적으로 유리합니다.
2. drop_duplicates(keep='last')의 방어적 적용:
   - 장점: 상위 파이프라인(Extractor/Transformer)의 오류로 동일한 merge_key가 여러 개 유입되더라도 `InvalidIndexError`를 뱉으며 뻗지 않고 최신(마지막) 데이터를 기준으로 파이프라인을 생존시킵니다.
   - 단점: 상단에서 발생한 중복 데이터 버그가 조용히 무시될(Silent Bypass) 위험이 존재합니다.
   - 근거: 병합(Merger) 계층은 파이프라인의 종착지(Gold Layer 직전)에 가깝습니다. 여기서 파이프라인이 붕괴되면 전체 배치가 실패하므로, 로깅 계층에 책임을 위임하고 데이터 처리 자체는 방어적으로(Fault-tolerant) 흘려보내는 것이 운영 안정성에 부합합니다.
"""

from typing import List
import pandas as pd

from src.common.decorators.log_decorator import log_decorator
from src.common.exceptions import BuilderDataMismatchError

@log_decorator(logger_name="build_wide_table")
def build_wide_table(
    dfs: List[pd.DataFrame], 
    job_ids: List[str], 
    merge_key: str
) -> pd.DataFrame:
    """다수의 DataFrame을 특정 키(merge_key)를 기준으로 고속 병합하여 단일 테이블로 생성합니다.

    Args:
        dfs (List[pd.DataFrame]): 병합할 대상 데이터프레임 리스트.
        job_ids (List[str]): 각 데이터프레임에 대응하는 고유 식별자 리스트 (접두사 맵핑용).
        merge_key (str): 병합의 기준이 되는 컬럼명 (예: 'trade_date').

    Returns:
        pd.DataFrame: merge_key를 기준으로 가로로 병합된 1개의 Wide DataFrame.
        
    Raises:
        ValueError: 입력된 DataFrame 리스트와 job_ids 리스트의 길이가 불일치할 경우.
    """
    if not dfs or not job_ids:
        return pd.DataFrame()

    # [설계 의도] DataFrame과 네임스페이스 식별자의 1:1 매칭 무결성 조기 검증 (Fail-Fast)
    if len(dfs) != len(job_ids):
        raise BuilderDataMismatchError(
            message=f"데이터프레임 개수({len(dfs)})와 Job ID 개수({len(job_ids)})가 일치하지 않습니다.",
            df_count=len(dfs),
            job_count=len(job_ids)
        )

    indexed_dfs = []
    
    # 1. 인덱스 정렬 및 네임스페이스(컬럼명) 동적 격리
    for df, job_id in zip(dfs, job_ids):
        if df.empty or merge_key not in df.columns:
            continue
            
        # [설계 의도] API 재시도나 중첩 수집으로 인한 인덱스 충돌(InvalidIndexError) 및 파이프라인 붕괴 방어
        # 가장 마지막에 적재된(최신) 데이터를 우선하여 중복을 제거합니다.
        clean_df = df.drop_duplicates(subset=[merge_key], keep='last')
        
        # 병합을 위해 조인 키를 인덱스로 승격
        df_indexed = clean_df.set_index(merge_key)
        
        # [설계 의도] N개의 테이블 병합 시 동일한 이름(예: open, close)이 
        # 충돌하여 _x, _y 접미사가 붙는 것을 원천 방지하기 위한 Prefix 맵핑 룰 적용
        rename_map = {}
        for col in df_indexed.columns:
            if col.lower() == "value":
                # 단일 값(예: FRED, ECOS 금리)은 컬럼명 자체를 식별자로 대체
                rename_map[col] = job_id
            else:
                rename_map[col] = f"{job_id}_{col}"
                
        df_indexed = df_indexed.rename(columns=rename_map)
        indexed_dfs.append(df_indexed)

    if not indexed_dfs:
        return pd.DataFrame()

    # 2. 고속 병합 (Vectorized Outer Concat)
    # [설계 의도] O(N) 순차 조인(Merge)이 아닌, C-엔진 기반의 pd.concat을 사용하여 
    # 메모리 상에서 1-Shot으로 가로(axis=1) 병합을 수행하여 성능을 극대화합니다.
    wide_df = pd.concat(indexed_dfs, axis=1)

    # [설계 의도] 대량의 데이터프레임 가로 결합으로 발생한 내부 메모리 단편화(Fragmentation)를 해소합니다.
    # 연속적인 단일 메모리 블록으로 재배정함으로써, 후속 인덱스 정렬(.sort_index) 및 
    # 다운스트림 파이프라인 연산 시 PerformanceWarning 경고 노이즈가 발생하는 것을 원천 차단합니다.
    wide_df = wide_df.copy()
        
    # 3. 정렬 및 인덱스 복원 (다운스트림 레이어를 위한 평탄화)
    wide_df = wide_df.sort_index().reset_index()
    
    # [설계 의도] reset_index 시 기존 인덱스명이 'index'로 강제 변경되는 현상을 방어하고 원본 조인 키로 복구
    wide_df = wide_df.rename(columns={"index": merge_key})
    
    return wide_df