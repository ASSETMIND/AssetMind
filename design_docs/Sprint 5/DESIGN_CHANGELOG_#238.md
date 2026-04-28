## [2026-03-06] - feature/#238-chart-orderbook-KSY

### Added & Changed (추가 및 변경 사항)

**1. 캔들스틱 차트 영역 레이아웃 및 기간 선택 Tab 디자인**
- 차트 영역은 TradingView 위젯으로 구현되는 것으로 확인되어, 피그마에서는 전체 레이아웃 맥락 파악을 위한 간략한 캔들 차트 배치로 대체했습니다.
- 기간 선택 Tab(1분, 일, 주, 월, 년) 컴포넌트를 디자인했습니다.

**2. 호가창 레이아웃 디자인**
- 매도/매수 호가 테이블 3열 구조(잔량 · 호가 · 종목정보)를 구성했습니다.
- 등락률 기준 상태별 컬러 토큰(rise/fall)을 적용했습니다.

**3. 차트 인터랙션 스펙 문서화**
- TradingView 위젯 도입에 따라 크로스헤어 및 툴팁 인터랙션은 피그마 시안 대신 스펙 코멘트로 정의했습니다.

**4. 체결 내역 실시간 Ticker Animation 가이드 작성**
- 새 체결 데이터 상단 삽입, Slide Down (200ms, Ease-out), Fade In (150ms) 등 애니메이션 규칙을 스펙으로 정의했습니다.

### 관련 산출물 및 참고 자료
- **디자인 시안:** https://www.figma.com/design/20IMijeghQ9NI6WxtS1wC8/AssetMind_-stock_chart?node-id=166-1060&t=FdAI4WKY87MGWjIp-1

