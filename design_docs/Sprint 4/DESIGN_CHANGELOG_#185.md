## [2026-02-22] - feature/#185-chart-design-KSY

### Added & Changed (추가 및 변경 사항)
* **태블릿 해상도 대응 반응형 디자인 적용**
- 신규 마스터 컴포넌트 생성 및 UI 디자인 적용
- 양방향(매수/매도 등) 거래 비율을 시각적으로 나타내는 게이지 막대(`Gauge_Bar`) UI 구현
- 게이지 바 하단에 비율 수치를 표시하는 라벨(`Labels`) 영역 추가
- 화면 해상도 및 데이터 길이에 맞게 유동적으로 크기가 변하도록 오토 레이아웃(Auto Layout) 최적화
  - 라벨 영역에 `Gap: Auto` 속성을 적용하여 비율 수치가 게이지 양끝에 자동 정렬되도록 레이아웃 규칙 설정

### 관련 산출물 및 참고 자료
* **디자인 시안:** [https://www.figma.com/design/20IMijeghQ9NI6WxtS1wC8/AssetMind_-stock_chart?node-id=0-1&t=TbgFcvFGaxxj6Q1K-1]