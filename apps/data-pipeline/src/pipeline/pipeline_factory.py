"""
[모듈 제목]
Data Pipeline Dynamic Factory Module

[모듈 목적 및 상세 설명]
설정 파일(pipeline.yml)에 선언된 메달리온 아키텍처 레이어 명세('layer')를 런타임에 판별하여,
그에 부합하는 구체 파이프라인 서비스 객체를 동적으로 동적 초기화 및 반환하는 팩토리 클래스입니다.
이를 통해 실행 엔트리포인트(main.py)는 구체 클래스에 대한 임포트 의존성 없이 완벽한 다형성을 누리게 됩니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: main.py로부터 실행 대상 작업 식별자(`task_name`) 접수.
2. Detection: `pipeline.yml`을 읽어 해당 태스크의 메달리온 레이어(bronze, silver 등) 속성 식별.
3. Creation: 레이어 명세에 맵핑된 구체 클래스를 지연 임포트(Lazy Import)하여 인스턴스화.
4. Output: `AbstractPipeline` 규격을 충족하는 가동 준비 완료된 서비스 인스턴스 반환.

주요 기능:
- [Dynamic Registry Mappings] YAML 설정을 기반으로 한 객체 생성 계층 분리 (Factory Pattern).
- [Lazy Dependency Loading] 실행되지 않는 레이어의 서비스 클래스 및 무거운 하위 패키지 로딩 전면 차단.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 팩토리 패턴 기반 동적 매핑 vs 메인 진입점 내 직접 하드코딩 분기:
  - 장점: 향후 Silver, Gold 파이프라인 서비스 파일이 신규 추가되어도 `main.py`를 단 한 줄도 수정하지 않고 오직 팩토리 내부 등록 스키마만 확장하면 되므로 OCP를 완벽히 준수함.
  - 단점: 간접적인 인스턴스화 과정으로 인해 정적 코드 분석 도구의 추적 경로가 단절될 수 있음.
  - 근거: 데이터 레이어의 지속적 확장성이 예상되는 비즈니스 구조상, 다형성을 통한 인프라 조율 계층의 안정성이 개발 편의성보다 압도적으로 가치 있으므로 이 구조를 강제함.
"""

from typing import Dict, Type
from src.common.config import ConfigManager
from src.common.exceptions import ConfigurationError
from src.pipeline.abstract_pipeline import AbstractPipeline


class PipelineFactory:
    """YAML 메타데이터를 기반으로 적절한 데이터 파이프라인 인스턴스를 조립하는 디자인 팩토리 클래스."""

    @staticmethod
    def create(task_name: str) -> AbstractPipeline:
        """설정 파일에 명시된 레이어 속성에 따라 알맞은 파이프라인 인스턴스를 생성하여 반환합니다.

        Args:
            task_name (str): 실행 프로세스의 고유 태스크 이름.

        Returns:
            AbstractPipeline: 추상 클래스 규격을 충족하는 구체 파이프라인 인스턴스.

        Raises:
            ConfigurationError: 지정된 task_name이 설정에 없거나 지원하지 않는 레이어 유형일 경우.
        """
        config = ConfigManager.load("pipeline")
        try:
            task_policy = config.get_pipeline(task_name)
        except Exception as e:
            raise ConfigurationError(f"[{task_name}] 설정을 공장 계층에서 로드할 수 없습니다: {e}") from e

        # [설계 의도] YAML의 'layer' 설정을 시스템 식별 키로 삼아 도메인 라우팅을 수행함
        layer_value = getattr(task_policy, "layer", "bronze")
        layer = str(layer_value).strip().lower()

        # [설계 의도] 기동 시 불필요한 레이어 라이브러리가 메모리에 동시 탑재되는 것을 방지하기 위해 
        # 분기 블록 내부에서 동적 임포트(Lazy/Dynamic Import)를 가동함.
        if layer == "bronze":
            from src.pipeline.bronze_pipeline import BronzePipeline
            return BronzePipeline(task_name=task_name)

        elif layer == "silver":
            from src.pipeline.silver_pipeline import SilverPipeline
            return SilverPipeline(task_name=task_name)

        else:
            raise ConfigurationError(
                message=f"팩토리에서 지원하지 않는 파이프라인 레이어 도메인입니다: '{layer}'",
                key_name="pipeline.layer"
            )