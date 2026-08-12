"""
[모듈 목적 및 상세 설명]
모든 세부 피처 엔지니어링 태스크(Task) 클래스들이 상속받아야 하는 최상위 추상 베이스 클래스(Abstract Base Class)를 정의합니다.
개방-폐쇄 원칙(OCP)과 단일 책임 원칙(SRP)을 달성하여, 새로운 피처 그룹이 추가되더라도 
기존 파이프라인 엔진 코드를 수정하지 않고 동적으로 확장이 가능하도록 규격화합니다.

[전체 데이터 흐름 설명 (Input -> Output)]
1. Input: FeatureService로부터 순차적으로 전달받은 금융 시계열 데이터프레임(`df: pd.DataFrame`).
2. Column Validation: `_validate_required_columns()`를 통해 개별 태스크 연산에 필요한 원본/이전 피처 컬럼의 존재 여부 사전 검증.
3. Feature Computation: 하위 구체 태스크 클래스의 `calculate()` 메서드를 통해 원자적 피처 변환 및 파생 피처 연산 수행.
4. Output: 신규 파생 피처 컬럼들이 추가 결합된 데이터프레임(`pd.DataFrame`) 반환.

주요 기능:
- [Abstract Task Interface] `calculate(df)` 추상 메서드를 통한 하위 피처 태스크들의 연산 인터페이스 규격화.
- [Defensive Schema Validation] 필수 입력 컬럼 누락 방지를 위한 공통 방어적 가드 함수(`_validate_required_columns`) 제공.

Trade-off: 주요 구현에 대한 엔지니어링 관점의 근거(장점, 단점, 근거) 요약.
- 추상 베이스 클래스(ABC) 기반 계약 강제 vs 일반 함수 기반 피처 생성:
  - 장점: 하위 피처 태스크들의 입출력 계약 및 메서드 서명을 통일하여 Service 계층에서의 다형성 순회 구동 및 공통 예외 처리가 용이함.
  - 단점: 단일 파생 변수를 추가하는 경우에도 클래스 정의와 추상 메서드 오버라이딩이 필요하여 초기 보일러플레이트 코드가 증가함.
  - 근거: 대규모 금융 시계열 파이프라인에서는 피처 추가/삭제 유연성(OCP)과 스키마 무결성 검증이 초기 코드 작성 비용보다 월등히 중요하므로 이 구조를 강제함.
"""

from abc import ABC, abstractmethod
from typing import List
import pandas as pd

from src.common.exceptions import RequiredColumnNotFoundError


class AbstractFeature(ABC):
    """모든 피처 엔지니어링 태스크의 추상 인터페이스 및 공통 유틸리티를 제공하는 베이스 클래스.

    Attributes:
        task_name (str): 실행 대상 피처 태스크의 식별 명칭.
    """

    def __init__(self, task_name: str) -> None:
        """AbstractFeature 인스턴스를 초기화합니다.

        Args:
            task_name (str): 피처 태스크 식별 명칭.
        """
        # [설계 의도] 각 태스크는 태스크 식별 명칭을 보유하며, 세부 수치 파라미터는 하위 클래스가 명시적 인자로 주입받아 무상태성을 유지함
        self.task_name: str = task_name

    @abstractmethod
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """입력 데이터프레임에 피처 변환 및 파생 피처 사출을 수행하는 추상 메서드.

        하위 세부 태스크 클래스에서 반드시 재정의(Override)하여 구체적인 피처 연산 로직을 구현해야 합니다.

        Args:
            df (pd.DataFrame): 정제가 완료된 원본/이전 단계 금융 시계열 데이터프레임.

        Returns:
            pd.DataFrame: 파생 피처 컬럼들이 추가된 데이터프레임.

        Raises:
            RequiredColumnNotFoundError: 필수 입력 컬럼이 데이터프레임에 존재하지 않을 때 발생.
            FeatureCalculationExecutionError: 롤링/통계 연산 중 수리적 발산이나 런타임 오류 발생 시 발생.
        """
        pass

    def _validate_required_columns(
        self,
        df: pd.DataFrame,
        required_columns: List[str]
    ) -> None:
        """피처 계산에 필요한 필수 컬럼들의 존재 여부를 검증하는 방어적 가드 함수.

        Args:
            df (pd.DataFrame): 검증 대상 데이터프레임.
            required_columns (List[str]): 필수 누락 불가 컬럼명 목록.

        Raises:
            RequiredColumnNotFoundError: 하나 이상의 필수 컬럼이 데이터프레임에서 누락된 경우.
        """
        # [설계 의도] 롤링 연산 수행 전 스키마 무결성을 사전 검증하여 불분명한 pandas KeyException 방지
        missing_columns: List[str] = [
            col for col in required_columns if col not in df.columns
        ]

        if missing_columns:
            raise RequiredColumnNotFoundError(
                message=f"[{self.task_name}] 피처 산출에 필요한 필수 입력 컬럼이 누락되었습니다.",
                missing_columns=missing_columns,
                task_name=self.task_name
            )