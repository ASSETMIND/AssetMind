from typing import Literal, Optional
import numpy as np

# ==============================================================================
# Constants & Configuration
# ==============================================================================
DEFAULT_NUM_BOOTSTRAPS: int = 5000                                          # 기본 부트스트랩 반복 복원추출 횟수 (B)
DEFAULT_BLOCK_SIZE: int = 20                                                # 시계열 의존성 보존을 위한 기본 블록 길이 (b)
DEFAULT_BOOTSTRAP_METHOD: Literal["cbb", "sb"] = "cbb"                      # 기본 리샘플링 알고리즘 (Circular Block Bootstrap)
MINIMUM_SAMPLE_SIZE: int = 2                                                # 리샘플링을 위한 최소 유효 시계열 표본 크기
MINIMUM_BLOCK_SIZE: int = 1                                                 # 유효한 최소 블록 크기


# ==============================================================================
# Public API Functions
# ==============================================================================
def generate_bootstrap_indices(
    n_samples: int,
    num_bootstraps: int = DEFAULT_NUM_BOOTSTRAPS,
    block_size: int = DEFAULT_BLOCK_SIZE,
    method: Literal["cbb", "sb"] = DEFAULT_BOOTSTRAP_METHOD,
    seed: Optional[int] = None
) -> np.ndarray:
    """시계열 의존성을 보존하는 블록 부트스트랩 인덱스 행렬을 생성합니다.

    Circular Block Bootstrap(CBB) 또는 Stationary Bootstrap(SB) 방식을 사용하여
    다변량 및 페어드(Paired) 시계열을 동기화하여 슬라이싱할 수 있는 정수 인덱스를 산출합니다.

    Args:
        n_samples (int): 원본 시계열의 표본 크기 (N).
        num_bootstraps (int): 생성할 부트스트랩 복제본의 수 (B, 기본값: 5000).
        block_size (int): 기대 또는 고정 블록 길이 (b, 기본값: 20).
        method (Literal["cbb", "sb"]): 리샘플링 기법 ('cbb': 순환 블록, 'sb': 정상성 블록).
        seed (Optional[int]): 난수 재현성을 보장하기 위한 시드 값.

    Returns:
        np.ndarray: 형상이 (num_bootstraps, n_samples)인 부트스트랩 정수 인덱스 2차원 배열.

    Raises:
        ValueError: 표본 크기, 블록 크기, 반복 횟수가 유효하지 않거나 지원하지 않는 알고리즘인 경우.
    """
    _validate_bootstrap_parameters(
        n_samples=n_samples,
        num_bootstraps=num_bootstraps,
        block_size=block_size,
        method=method
    )

    random_generator: np.random.Generator = np.random.default_rng(seed)

    bootstrap_indices: np.ndarray = _route_bootstrap_indices(
        n_samples=n_samples,
        num_bootstraps=num_bootstraps,
        block_size=block_size,
        method=method,
        rng=random_generator
    )

    return bootstrap_indices


def resample_time_series(
    sample_data: np.ndarray,
    num_bootstraps: int = DEFAULT_NUM_BOOTSTRAPS,
    block_size: int = DEFAULT_BLOCK_SIZE,
    method: Literal["cbb", "sb"] = DEFAULT_BOOTSTRAP_METHOD,
    seed: Optional[int] = None
) -> np.ndarray:
    """입력된 1차원 시계열 배열에 대해 블록 부트스트랩을 수행하여 2차원 재표본 배열을 반환합니다.

    Args:
        sample_data (np.ndarray): 1차원 원본 시계열 데이터 배열 (N,).
        num_bootstraps (int): 생성할 부트스트랩 복제본의 수 (B, 기본값: 5000).
        block_size (int): 기대 또는 고정 블록 길이 (b, 기본값: 20).
        method (Literal["cbb", "sb"]): 리샘플링 기법 ('cbb': 순환 블록, 'sb': 정상성 블록).
        seed (Optional[int]): 난수 재현성을 보장하기 위한 시드 값.

    Returns:
        np.ndarray: 형상이 (num_bootstraps, n_samples)인 리샘플링된 시계열 2차원 배열.

    Raises:
        ValueError: 입력 데이터가 1차원 배열이 아니거나 표본 크기가 부족한 경우.
    """
    contiguous_data: np.ndarray = np.ascontiguousarray(sample_data, dtype=np.float64)
    if contiguous_data.ndim != 1:
        raise ValueError(f"sample_data는 반드시 1차원 배열이어야 합니다. 입력 차원: {contiguous_data.ndim}")

    bootstrap_indices: np.ndarray = generate_bootstrap_indices(
        n_samples=len(contiguous_data),
        num_bootstraps=num_bootstraps,
        block_size=block_size,
        method=method,
        seed=seed
    )

    return contiguous_data[bootstrap_indices]


# ==============================================================================
# Internal Helper Functions
# ==============================================================================
def _validate_bootstrap_parameters(
    n_samples: int,
    num_bootstraps: int,
    block_size: int,
    method: str
) -> None:
    """부트스트랩 입력 파라미터의 수리적 유효성을 사전 검증합니다."""
    if n_samples < MINIMUM_SAMPLE_SIZE:
        raise ValueError(f"n_samples는 최소 {MINIMUM_SAMPLE_SIZE} 이상이어야 합니다. 입력값: {n_samples}")
    if num_bootstraps < 1:
        raise ValueError(f"num_bootstraps는 최소 1 이상이어야 합니다. 입력값: {num_bootstraps}")
    if block_size < MINIMUM_BLOCK_SIZE or block_size > n_samples:
        raise ValueError(
            f"block_size는 {MINIMUM_BLOCK_SIZE} 이상 {n_samples} 이하이어야 합니다. 입력값: {block_size}"
        )
    if method not in ("cbb", "sb"):
        raise ValueError(f"지원하지 않는 부트스트랩 방식입니다: '{method}'. ('cbb', 'sb' 중 선택)")


def _route_bootstrap_indices(
    n_samples: int,
    num_bootstraps: int,
    block_size: int,
    method: str,
    rng: np.random.Generator
) -> np.ndarray:
    """지정된 알고리즘(CBB 또는 SB)에 따라 적절한 인덱스 생성 내장함수로 라우팅합니다."""
    if method == "cbb":
        return _generate_cbb_indices(
            n_samples=n_samples,
            num_bootstraps=num_bootstraps,
            block_size=block_size,
            rng=rng
        )
    return _generate_sb_indices(
        n_samples=n_samples,
        num_bootstraps=num_bootstraps,
        block_size=block_size,
        rng=rng
    )


def _generate_cbb_indices(
    n_samples: int,
    num_bootstraps: int,
    block_size: int,
    rng: np.random.Generator
) -> np.ndarray:
    """원형 래핑(Wrap-around) 고정 블록 리샘플링(CBB)을 벡터화 연산으로 집행합니다."""
    blocks_needed: int = int(np.ceil(n_samples / block_size))
    random_starts: np.ndarray = rng.integers(0, n_samples, size=(num_bootstraps, blocks_needed))

    block_offsets: np.ndarray = np.arange(block_size, dtype=np.int64)
    expanded_blocks: np.ndarray = (random_starts[:, :, np.newaxis] + block_offsets[np.newaxis, np.newaxis, :]) % n_samples

    flattened_indices: np.ndarray = expanded_blocks.reshape(num_bootstraps, -1)
    return np.ascontiguousarray(flattened_indices[:, :n_samples], dtype=np.int64)


def _generate_sb_indices(
    n_samples: int,
    num_bootstraps: int,
    block_size: int,
    rng: np.random.Generator
) -> np.ndarray:
    """기하분포 무작위 블록 길이를 적용한 정상성 부트스트랩(SB) 인덱스를 생성합니다."""
    jump_probability: float = 1.0 / float(block_size)

    indices_matrix: np.ndarray = np.empty((num_bootstraps, n_samples), dtype=np.int64)
    indices_matrix[:, 0] = rng.integers(0, n_samples, size=num_bootstraps)

    random_integers: np.ndarray = rng.integers(0, n_samples, size=(num_bootstraps, n_samples - 1))
    jump_flags: np.ndarray = rng.random(size=(num_bootstraps, n_samples - 1)) < jump_probability

    for step_index in range(1, n_samples):
        indices_matrix[:, step_index] = np.where(
            jump_flags[:, step_index - 1],
            random_integers[:, step_index - 1],
            (indices_matrix[:, step_index - 1] + 1) % n_samples
        )

    return indices_matrix