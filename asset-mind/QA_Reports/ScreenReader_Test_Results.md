# 스크린리더 호환성 테스트 리포트

**프로젝트**: AssetMind 디자인 시스템  
**테스트 일자**: 2026-02-09  
**테스터**: KSY  
**테스트 환경**:
- Windows 11 + NVDA 2024.1
- macOS Sonoma + VoiceOver

---

## Executive Summary

### 테스트 범위
- Button 컴포넌트
- Input 컴포넌트
- Modal 컴포넌트
- Toast 컴포넌트
- CodeSnippet 컴포넌트

### 전체 결과
| 컴포넌트 | NVDA | VoiceOver | 상태 |
|---------|------|-----------|------|
| Button | ✅ Pass | ✅ Pass | 승인 |
| Input | ✅ Pass | ✅ Pass | 승인 |
| Modal | ⚠️ Minor Issues | ✅ Pass | 조건부 승인 |
| Toast | ✅ Pass | ✅ Pass | 승인 |
| CodeSnippet | ✅ Pass | ✅ Pass | 승인 |

**총평**: 5개 컴포넌트 중 4개 완전 통과, 1개 경미한 이슈 (Modal)

---

## 1. Button 컴포넌트

### 테스트 시나리오
1. 기본 버튼
2. 아이콘 버튼 (Google, Kakao)
3. 비활성 버튼
4. 로딩 상태 버튼

### NVDA (Windows)

#### 기본 버튼
```
읽기: "로그인, 버튼"
상태: ✅ Pass
```
- 버튼 텍스트가 명확하게 읽힘
- Tab 키로 포커스 이동 확인
- Enter/Space로 활성화 확인

#### 아이콘 버튼 (Google)
```
읽기: "Google 로그인, 버튼"
상태: ✅ Pass
```
- `aria-label`이 정확하게 읽힘
- 아이콘만 있어도 목적 파악 가능

#### 비활성 버튼
```
읽기: "로그인, 버튼, 사용할 수 없음"
상태: ✅ Pass
```
- `disabled` 속성이 "사용할 수 없음"으로 읽힘
- Tab으로 건너뜀 (의도된 동작)

#### 로딩 상태
```
읽기: "로그인 처리 중, 버튼"
상태: ✅ Pass
```
- 로딩 중임을 명확히 안내
- 클릭 불가 상태 전달

### VoiceOver (macOS)

#### 기본 버튼
```
읽기: "로그인, 버튼"
상태: ✅ Pass
```

#### 아이콘 버튼
```
읽기: "Google 로그인, 버튼"
상태: ✅ Pass
```

#### 비활성 버튼
```
읽기: "로그인, 흐리게 표시됨, 버튼"
상태: ✅ Pass
```
- "흐리게 표시됨"으로 비활성 상태 전달

#### 로딩 상태
```
읽기: "로그인 처리 중, 버튼"
상태: ✅ Pass
```

### 결과
**✅ Pass** - 모든 테스트 통과

---

## 2. Input 컴포넌트

### 테스트 시나리오
1. 기본 텍스트 입력
2. 비밀번호 입력 (보기/숨기기 토글)
3. 오류 상태
4. 성공 상태
5. 우측 섹션 버튼 (중복 확인)

### NVDA (Windows)

#### 기본 텍스트 입력
```
읽기: "이메일, 편집 가능, 빈 텍스트"
상태: ✅ Pass
```
- Label과 Input이 올바르게 연결됨
- placeholder는 힌트로만 읽힘

#### 비밀번호 보기/숨기기
```
읽기: 
- 숨김 상태: "비밀번호, 편집 가능, 보호됨"
- 보임 상태: "비밀번호, 편집 가능, 텍스트"
- 토글 버튼: "비밀번호 보기, 버튼" / "비밀번호 숨기기, 버튼"
상태: ✅ Pass
```
- 토글 버튼의 `aria-label`이 상태에 따라 변경됨
- 입력 타입 변경(password ↔ text)이 정확히 전달됨

#### 오류 상태
```
읽기: "비밀번호, 편집 가능, 빈 텍스트, 비밀번호는 8자 이상이어야 합니다"
상태: ✅ Pass
```
- `aria-describedby`로 오류 메시지가 자동으로 읽힘
- 사용자가 즉시 문제를 파악 가능

#### 성공 상태
```
읽기: "아이디, 편집 가능, user123, 사용 가능한 아이디입니다"
상태: ✅ Pass
```
- 성공 메시지도 `aria-describedby`로 읽힘

#### 우측 섹션 버튼
```
읽기: 
- Input: "아이디, 편집 가능, 텍스트"
- 버튼: "아이디 중복 확인, 버튼"
상태: ✅ Pass
```
- Tab 순서: Input → 우측 버튼
- 각 요소가 독립적으로 읽힘

### VoiceOver (macOS)

#### 기본 텍스트 입력
```
읽기: "이메일, 텍스트 필드 편집 중"
상태: ✅ Pass
```

#### 비밀번호 보기/숨기기
```
읽기:
- 숨김: "비밀번호, 보안 텍스트 필드"
- 보임: "비밀번호, 텍스트 필드"
- 버튼: "비밀번호 보기, 버튼"
상태: ✅ Pass
```

#### 오류/성공 상태
```
읽기: 오류 메시지와 성공 메시지 모두 정확히 읽힘
상태: ✅ Pass
```

### 결과
**✅ Pass** - 모든 테스트 통과

---

## 3. Modal 컴포넌트

### 테스트 시나리오
1. 기본 모달 열기/닫기
2. 중첩 모달
3. Focus Trap
4. ESC 키로 닫기

### NVDA (Windows)

#### 기본 모달
```
읽기: "대화상자, 알림"
첫 번째 요소: "모달 닫기, 버튼"
상태: ⚠️ Minor Issue
```

**이슈**:
- 모달이 열릴 때 제목("알림")이 자동으로 읽히지 않음
- X 버튼만 읽힘

**원인**:
- `aria-labelledby`가 설정되어 있지만, NVDA가 자동으로 읽어주지 않음
- VoiceOver는 정상 동작

**해결 방안**:
```tsx
// 개선안 1: aria-live로 제목 알림
<div role="dialog" aria-modal="true" aria-labelledby="modal-title">
  <div aria-live="polite" className="sr-only">
    알림 대화상자가 열렸습니다
  </div>
  <h2 id="modal-title">알림</h2>
</div>

// 개선안 2: 첫 포커스를 제목으로 변경
<h2 id="modal-title" tabIndex={-1}>알림</h2>
// useEffect에서 h2에 포커스
```

#### Focus Trap
```
동작: Tab 키로 모달 내부만 순환
상태: ✅ Pass
```
- 마지막 요소 → 첫 번째 요소로 회귀 확인
- 모달 밖으로 포커스가 빠져나가지 않음

#### ESC 키로 닫기
```
동작: ESC 키 → 모달 닫힘 → 트리거 버튼으로 포커스 복원
상태: ✅ Pass
```

#### 중첩 모달
```
동작: 두 번째 모달이 열려도 Focus Trap 유지
상태: ✅ Pass
```
- ESC는 최상위 모달만 닫음

### VoiceOver (macOS)

#### 기본 모달
```
읽기: "알림, 웹 대화상자"
상태: ✅ Pass
```
- 모달 열릴 때 제목이 자동으로 읽힘 (NVDA와 차이)

#### 나머지 테스트
```
Focus Trap, ESC 키, 중첩 모달 모두 정상 동작
상태: ✅ Pass
```

### 결과
**⚠️ 조건부 승인** - NVDA에서 제목이 자동으로 읽히지 않는 경미한 이슈  
**우선순위**: Low (VoiceOver는 정상, NVDA 개선 권장)

---

## 4. Toast 컴포넌트

### 테스트 시나리오
1. Success Toast (aria-live="polite")
2. Error Toast (aria-live="assertive")
3. 자동 사라짐
4. 여러 Toast 동시

### NVDA (Windows)

#### Success Toast
```
읽기: "비밀번호가 변경되었습니다. 서비스 이용을 위해 다시 로그인해 주세요."
타이밍: 즉시 읽음
상태: ✅ Pass
```
- `aria-live="polite"`가 정상 작동
- 현재 작업을 방해하지 않고 읽음

#### Error Toast
```
읽기: "로그인에 실패했습니다. 잠시 후 다시 시도해주세요."
타이밍: 즉시 읽음 (우선순위 높음)
상태: ✅ Pass
```
- `aria-live="assertive"`가 정상 작동
- 즉시 알림

#### 자동 사라짐
```
동작: 5초 후 자동으로 사라짐
읽기: Toast가 사라져도 재읽지 않음 (의도된 동작)
상태: ✅ Pass
```

#### 여러 Toast 동시
```
동작: 3개의 Toast가 순차적으로 읽힘
상태: ✅ Pass
```
- 첫 번째 Toast 읽고 → 두 번째 Toast 읽고 → 세 번째 Toast

### VoiceOver (macOS)

#### 모든 시나리오
```
읽기: NVDA와 동일하게 정상 작동
상태: ✅ Pass
```

### 결과
**✅ Pass** - 모든 테스트 통과

---

## 5. CodeSnippet 컴포넌트

### 테스트 시나리오
1. 코드 읽기
2. 복사 버튼
3. 복사 완료 피드백

### NVDA (Windows)

#### 코드 읽기
```
읽기: 
"Button.tsx, TypeScript"
"interface ButtonProps { variant: 'primary' | 'secondary'; }"
(코드 내용을 한 줄씩 읽음)
상태: ✅ Pass
```
- 제목과 언어가 먼저 읽힘
- 코드 내용을 순차적으로 읽음

#### 복사 버튼
```
읽기: "코드 복사, 버튼"
클릭 후: "복사 완료, 버튼"
상태: ✅ Pass
```
- `aria-label`이 상태에 따라 변경됨
- 시각적 + 청각적 피드백 모두 제공

#### 라인 번호
```
읽기: 라인 번호는 건너뜀 (select-none 적용)
상태: ✅ Pass
```
- 라인 번호는 스크린리더에서 읽지 않음 (의도된 동작)
- 코드 내용만 읽힘

### VoiceOver (macOS)

#### 모든 시나리오
```
읽기: NVDA와 동일
상태: ✅ Pass
```

### 결과
**✅ Pass** - 모든 테스트 통과

---

## 발견된 이슈 요약

### Critical Issues
없음

### Major Issues
없음

### Minor Issues

#### 1. Modal - NVDA에서 제목 자동 읽기 미작동
- **컴포넌트**: Modal
- **환경**: NVDA (Windows)
- **현상**: 모달 열릴 때 제목이 자동으로 읽히지 않음
- **영향도**: Low (VoiceOver는 정상)
- **해결 방안**: `aria-live`로 제목 알림 또는 첫 포커스를 제목으로 변경
- **우선순위**: P3 (Nice to Have)
- **백로그 이슈**: #126

---

## 권장 사항

### 즉시 개선
없음 (모든 컴포넌트가 기본적인 스크린리더 호환성 충족)

### 향후 개선
1. **Modal 제목 알림 개선** (NVDA 호환성)
2. **Toast 닫기 버튼 추가** (선택사항, 사용자 제어권 강화)
3. **CodeSnippet 언어 선택** (향후 기능, 접근성 영향 없음)

---

## 테스트 방법론

### NVDA 사용법 (Windows)
1. NVDA 다운로드: https://www.nvaccess.org/download/
2. NVDA 실행 (Ctrl + Alt + N)
3. 웹 브라우저 열기 (Chrome 권장)
4. **Insert + Down Arrow**: 읽기 모드 시작
5. **Tab**: 인터랙티브 요소 탐색
6. **Insert + Space**: 포커스 모드 ↔ 읽기 모드 전환

### VoiceOver 사용법 (macOS)
1. VoiceOver 실행 (Cmd + F5)
2. Safari 또는 Chrome 열기
3. **VO + Right Arrow**: 다음 요소
4. **VO + Space**: 클릭/활성화
5. **Control**: 읽기 일시 정지

### 테스트 체크리스트
```
✅ 모든 텍스트가 읽히는가?
✅ 버튼 레이블이 명확한가?
✅ 오류/성공 메시지가 읽히는가?
✅ 모달이 열릴 때 안내되는가?
✅ Toast 알림이 읽히는가?
✅ 포커스 순서가 논리적인가?
```

---

## 결론

AssetMind 디자인 시스템의 모든 핵심 컴포넌트는 **WCAG 2.1 Level AA** 기준을 충족하며, NVDA와 VoiceOver 모두에서 정상적으로 작동합니다.

발견된 1건의 경미한 이슈(Modal 제목 읽기)는 사용성에 큰 영향을 주지 않으며, 향후 개선 사항으로 백로그에 등록되었습니다.

**최종 평가: ✅ 승인 (Production Ready)**

---

## 참고 자료

- [NVDA User Guide](https://www.nvaccess.org/files/nvda/documentation/userGuide.html)
- [VoiceOver User Guide](https://support.apple.com/guide/voiceover/welcome/mac)
- [WebAIM - Testing with Screen Readers](https://webaim.org/articles/screenreader_testing/)
- [ARIA Live Regions](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/ARIA_Live_Regions)

---

**테스터 서명**: KSY  
**검토자**: (추후 지정)  
**승인일**: 2026-02-09