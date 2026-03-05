# 디자인 시스템 컴포넌트 및 인터랙션 가이드

*Design System — Component & Interaction Guide*

본 문서는 개발팀의 원활한 구현을 위해 주요 UI 컴포넌트의 상태 변화와 인터랙션 규칙을 정의합니다.

---

## 1. 네비게이션 및 필터 (Navigation & Filter)

### A. 메인 탭 (Tab / Main_Tabs)

실시간 차트, 지금 뜨는 카테고리, 국내 투자자 동향 등 주요 섹션을 전환하는 최상위 탭 컴포넌트입니다.

#### 상태 (State)

| 상태 (State/Variant) | 색상값 / 스타일 | 설명 |
|---|---|---|
| Active | 텍스트: `#FFFFFF` / Bold<br>하단 Indicator: 흰색(`#FFFFFF`) 밑줄 표시 | 현재 선택된 탭 |
| Default | 텍스트: Secondary (`#9194A1`) / Regular·Medium<br>Indicator: 없음 | 비선택 탭 |

#### 인터랙션 (Interaction)

- 탭 클릭 시 해당 데이터 뷰로 전환되며 Active 상태가 변경됩니다.
- 탭 항목 수가 고정되어 있어 모든 해상도에서 가로 스크롤 없이 노출됩니다.

---

### B. 필터 그룹 및 칩 (filter-group / Chip)

전체 · 국내 · 해외 등의 Chip 여러 개로 구성된 필터 영역입니다. filter-group 컨테이너에 배경색(Neutral-800)이 적용되며, 각 Chip은 독립적인 Active/Default 상태를 가집니다.

#### Chip 상태 (State)

| 상태 (State/Variant) | 색상값 / 스타일 | 설명 |
|---|---|---|
| Default | 배경: transparent<br>텍스트: Secondary (`#9194A1`) | 기본 비선택 상태 |
| Active | 배경: Neutral-400<br>텍스트: `#FFFFFF` | 선택된 필터 |

#### filter-group 컨테이너

| 항목 | 내용 |
|---|---|
| 배경색 | Neutral-800 |
| 레이아웃 | Chip 여러 개를 가로로 나열 |

#### 인터랙션 (Interaction)

- Chip 클릭 시 해당 필터가 Active 상태로 전환되며 리스트 데이터가 필터링됩니다.
- `[Mobile / Tablet]` filter-group은 Chip 수가 화면 너비를 초과할 경우 가로 스크롤이 가능해야 합니다. 스크롤바는 숨김 처리합니다.

---

## 2. 데이터 리스트 컴포넌트 (Data Display)

### A. 리스트/테이블 행 (tbl-row)

종목명, 현재가(Ticker), 등락률(Gain/Loss), 거래대금, 거래 비율(rbar) 등의 실질적인 종목 정보를 표시하는 행 컴포넌트입니다. 내부에 Ticker, Gain/Loss, rbar 에셋이 포함되어 있습니다.

#### 상태 (State)

| 상태 (State/Variant) | 색상값 / 스타일 | 설명 |
|---|---|---|
| Default | 배경: transparent | 기본 상태 |
| Hover *(Desktop only)* | 배경: Neutral-600 (`#2C2C30`) | 데스크톱 마우스 오버 시 |
| Update-rise | 행 배경: Orange-600 하이라이트 오버레이 적용 | 상승 변동 발생 시 800ms 동안 적용 후 Default 복귀 |
| Update-fall | 행 배경: Blue-600 하이라이트 오버레이 적용 | 하락 변동 발생 시 800ms 동안 적용 후 Default 복귀 |

#### 인터랙션 (Interaction)

- 행 전체가 하나의 클릭/터치 타겟으로 작동하며, 클릭 시 해당 종목의 상세 페이지로 이동합니다.
- 실시간 데이터 갱신 시 변동 방향에 따라 Update-rise 또는 Update-fall 상태로 잠시 전환된 후 Default 상태로 복귀합니다. 피그마 프로토타입에 해당 인터랙션이 정의되어 있습니다.

---

### B. 등락률 (Gain/Loss)

tbl-row 내부에 포함되는 등락률 표시 에셋입니다.

#### 상태 (State)

| 상태 (State/Variant) | 색상값 / 스타일 | 설명 |
|---|---|---|
| Rise | 텍스트: Orange-600 | `+0.00%` 형식 — 상승 수치 |
| Even | 텍스트: `#FFFFFF` | `0.00%` 형식 — 변동 없음 |
| Fall | 텍스트: Blue-600 | `-0.00%` 형식 — 하락 수치 |

---

### C. 현재가 (Ticker)

tbl-row 내부에 포함되는 현재 주가 표시 에셋입니다.

#### 상태 (State)

| 상태 (State/Variant) | 색상값 / 스타일 | 설명 |
|---|---|---|
| Default | 텍스트: `#FFFFFF` | 가격 변동이 없는 안정 상태 |
| Update | 텍스트: `#FFFFFF`<br>Slide Up 애니메이션 적용 | 가격 갱신 발생 시 숫자가 교체되는 애니메이션 처리 후 Default 복귀 |

#### 인터랙션 (Interaction)

가격 업데이트 발생 시 숫자가 아래에서 위로 밀어 올리는 형태의 애니메이션으로 교체됩니다. 피그마 프로토타입을 참조하여 구현해 주세요.

| 항목 | 내용 |
|---|---|
| 애니메이션 방향 | Slide Up — 아래에서 위로 밀어 올리는 형태 |
| Duration | 400ms |

---

### D. 거래 비율 게이지 바 (rbar)

tbl-row 내부에 포함되는 매수/매도 비율 시각화 에셋입니다. 게이지 바(Gauge_Bar)와 비율 수치 라벨(Labels) 두 영역으로 구성됩니다.

#### 구성 요소

| 항목 | 내용 |
|---|---|
| Gauge_Bar | 매도(Sell) 바: Blue-600 (좌측) / 매수(Buy) 바: Orange-600 (우측)<br>좌우 너비 비율로 매도/매수 비율을 시각화하는 게이지 바 영역 |
| Labels | 게이지 바 하단에 매도/매수 비율 수치를 텍스트로 표시하는 라벨 영역.<br>매도 수치: Blue-600 (좌측) / 매수 수치: Orange-600 (우측)<br>Auto Layout `Gap: Auto` 속성을 적용하여 매도 수치는 좌측, 매수 수치는 우측 끝에 자동 정렬됩니다. |

#### 렌더링 규칙

- 매도(Sell) / 매수(Buy) 비율 데이터에 따라 좌우 게이지 바의 Width(%)가 동적으로 렌더링됩니다. 두 값의 합은 항상 100%입니다.
- 극단적인 비율(예: 99:1)로 인해 한쪽 바가 지나치게 얇아지는 현상을 방지하기 위해 양쪽 바의 최소 너비는 4px로 고정합니다.
- API 응답 값이 정확히 0% 또는 100%일 경우, 일반 게이지 바가 아닌 아래의 전용 베리언트를 렌더링합니다.

#### 극단 비율 상태 (State)

| 상태 (State/Variant) | 색상값 / 스타일 | 설명 |
|---|---|---|
| 100-Buy | 매수(Buy) 100% / 매도(Sell) 0%<br>매수 바(Orange-600, 우측) 최대 너비, 매도 바(Blue-600, 좌측) 최소(4px) 적용 | API 응답에서 매도 비율이 정확히 0%일 때 전용 베리언트 렌더링 |
| 100-Sell | 매도(Sell) 100% / 매수(Buy) 0%<br>매도 바(Blue-600, 좌측) 최대 너비, 매수 바(Orange-600, 우측) 최소(4px) 적용 | API 응답에서 매수 비율이 정확히 0%일 때 전용 베리언트 렌더링 |

---

## 3. 상태별 UI 및 피드백 (State & Feedback)

### A. 로딩 상태 스켈레톤 (tbl-row-skeleton)

#### 베리언트 (Variants)

| 상태 (State/Variant) | 색상값 / 스타일 | 설명 |
|---|---|---|
| State = Default | Neutral-700 (`#21242C`) | 기본 어두운 배경 상태 |
| State = Loading | Neutral-600 (`#2C2C30`) | 하이라이트 밝은 배경 상태 |

#### 애니메이션 규칙 (Pulse)

사용자의 렉(Lag) 오인을 방지하기 위해 단색이 아닌 두 상태가 부드럽게 전환되는 Pulse 애니메이션이 적용되어야 합니다.

| 항목 | 내용 |
|---|---|
| 애니메이션 방식 | Default ↔ Loading 두 베리언트를 무한 반복 |
| Duration | 800ms |
| Timing Function | ease-in-out |
| Delay | 없음 (0ms) |
| Iteration | infinite |

#### 개발 구현 가이드

피그마에 세팅된 수치(duration: 800ms, Ease In and Out, Smart Animate)를 참고하여 CSS animation을 구현해 주세요.

```css
@keyframes skeleton-pulse {
  0%, 100% { background-color: #21242C; }
  50%       { background-color: #2C2C30; }
}
.skeleton {
  animation: skeleton-pulse 800ms ease-in-out infinite;
}
```

---

### B. 빈 데이터 상태 (Empty State)

#### 표시 조건

- API 응답은 성공했으나 반환된 데이터가 0건일 때 노출합니다.
- 스켈레톤 로딩이 완료된 이후 데이터가 없을 경우 Empty UI로 전환합니다.

#### UI 구성

| 항목 | 내용 |
|---|---|
| 아이콘 | 빈 박스 아이콘 — 색상: Secondary (`#9194A1`) |
| 안내 문구 | "조회된 종목이 없습니다." |
| 레이아웃 | 화면 중앙 배치. 데스크톱부터 모바일까지 시각적 밸런스가 유지되도록 해상도별 크기 최적화 |

---

### C. 에러 상태 및 재시도 버튼 (Error State / '다시 시도')

데이터 통신 실패 시 노출되는 에러 UI입니다. 사용자가 오류 상태에 갇히지 않고 직접 재시도를 트리거할 수 있도록 '다시 시도' 버튼을 제공합니다.

#### UI 구성

| 항목 | 내용 |
|---|---|
| 아이콘 | 경고 아이콘 — 색상: Secondary (`#9194A1`) |
| 안내 문구 | "데이터를 불러오는 데 실패했습니다." |
| 버튼 | '다시 시도' 버튼 — 배경: Primary (`#6D4AE6`), 텍스트: `#FFFFFF` |
| 적용 해상도 | 데스크톱 / 태블릿 / 모바일 전 해상도 공통 적용 |

#### 버튼 상태 (State)

| 상태 (State/Variant) | 색상값 / 스타일 | 설명 |
|---|---|---|
| Default | 배경: Primary (`#6D4AE6`)<br>텍스트: `#FFFFFF` | 에러 발생 시 노출되는 재시도 버튼 기본 상태 |
| Hover / Pressed | 피그마 컴포넌트 스타일 참조 | 마우스 오버 및 클릭 시 |

#### 인터랙션 (Interaction) — 재시도 플로우

| 항목 | 내용 |
|---|---|
| 트리거 | 사용자가 '다시 시도' 버튼 클릭 |
| 즉각 피드백 | 클릭 직후 화면을 즉시 스켈레톤(Loading) 상태로 전환하여 시스템 동작 중임을 시각적으로 표시 |
| 동작 | 현재 화면의 데이터 통신을 재요청 (API Re-fetch) |
| 성공 시 | 스켈레톤 → 정상 데이터 리스트로 전환 |
| 실패 시 | 스켈레톤 → 에러 상태 UI로 재전환 |

---

## 4. 반응형 브레이크포인트 (Responsive Breakpoints)

본 UI는 Desktop / Tablet / Mobile 세 가지 뷰포인트를 지원합니다. 피그마 프레임 기준 해상도 및 분기 기준은 아래를 참고해 주세요.

| 해상도 | 내용 |
|---|---|
| Desktop | 피그마 프레임: 1440 x 1024 \| 분기 기준: 1024px 이상 |
| Tablet | 피그마 프레임: 768 x 1024 \| 분기 기준: 768px 이상 ~ 1023px 이하 |
| Mobile | 피그마 프레임: 393 x 852 \| 분기 기준: 767px 이하 |

- Tablet 및 Mobile UI의 레이아웃과 컴포넌트 변화는 피그마의 각 해상도 프레임을 기준으로 구현해 주세요.
- `[Mobile / Tablet]` filter-group은 가로 스크롤을 지원하며, 스크롤바는 숨김 처리합니다. (`overflow-x: auto; scrollbar-width: none;` 참고)
- `[Mobile / Tablet]` 터치 인터페이스를 고려하여 Tab 및 필터(Chip) 버튼의 터치 타겟 높이는 최소 45px 이상을 확보해야 합니다.
- 메인 탭(Main_Tabs)은 모든 해상도에서 가로 스크롤 없이 노출됩니다.

### 광고 영역 여백 (Ad_Placeholder)

향후 수익화 배너 도입 시 레이아웃 시프트를 방지하기 위해 각 해상도 최상단에 배너 규격의 여백(Ad_Placeholder)이 선반영되어 있습니다. 해당 여백은 임의로 제거하지 않아야 합니다.

- 향후 상단 내비게이션 바, 홈 버튼 등 상단 콘텐츠가 추가될 경우 여백 크기가 재조정될 수 있습니다. 관련 변경 사항은 UI 담당자를 통해 공지됩니다.

---

*※ 본 가이드에서 정의되지 않은 세부 스타일(색상값, 여백, 폰트 크기 등)은 Notion의 Color Pallete와 피그마 디자인 파일을 1차 기준으로 삼아 구현해 주세요.*

*문의 사항은 UI 담당자에게 카카오톡 또는 피그마 코멘트로 남겨주세요.*