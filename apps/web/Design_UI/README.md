# AssetMind Design System

AssetMind의 React 기반 디자인 시스템입니다. Tailwind CSS와 TypeScript를 기반으로 구축되었으며, Storybook을 통해 체계적으로 문서화되었습니다. 본 시스템은 제품 전반의 사용자 경험(UX) 일관성을 유지하고 개발 효율성을 극대화하는 것을 목적으로 합니다.

---

## 개요 (Overview)

이 디자인 시스템은 AssetMind 서비스의 확장성과 유지보수성을 고려하여 설계되었습니다.  
재사용 가능한 UI 컴포넌트와 표준화된 디자인 토큰(Design Tokens)을 제공하여, 개발자와 디자이너 간의 협업 비용을 줄이고 통일된 브랜드 아이덴티티를 구현합니다.

---

## 핵심 기능 (Key Features)

- **Design Tokens**: 색상, 타이포그래피, 간격(Spacing) 등 디자인 원칙의 시스템화  
- **Component Library**: 프로덕션 레벨의 검증된 11종 React 컴포넌트 제공  
- **Type Safety**: TypeScript 기반의 엄격한 타입 정의로 런타임 오류 방지  
- **Documentation**: Storybook을 활용한 인터랙티브 컴포넌트 명세 및 가이드라인 제공  
- **Styling**: Tailwind CSS를 활용한 유틸리티 퍼스트(Utility-First) 스타일링 적용  
- **Accessibility**: WCAG 2.1 AA 기준을 준수하여 웹 접근성 보장  

---

## 기술 스택 (Tech Stack)

| Category | Stack |
|---------|--------|
| **Core** | React 18.3.1, TypeScript 5.9.3 |
| **Styling** | Tailwind CSS 3.4.17 |
| **Build Tool** | Vite 6.0.11 |
| **Documentation** | Storybook 10.2.5 |
| **Test** | Vitest 4.0.17 |

---

## 컴포넌트 구성 (Components)

### Auth (인증)
- `LoginModal`
- `SignUpModal`

### Common (공통)
- `Button`
- `Input`
- `Modal`
- `Toast`
- `CodeSnippet`

### Icons (아이콘)
- `CloseIcon`
- `EyeIcon`
- `GoogleIcon`
- `KakaoIcon`

---

## 설치 및 환경 설정 (Installation & Setup)

### 패키지 설치
```bash
npm install
```

### 개발 환경 실행
```bash
npm run dev
npm run storybook
```

### 빌드 (Build)
```bash
npm run build
npm run build-storybook
```

---

## 문서화 (Storybook)

```bash
npm run storybook
```
브라우저에서 http://localhost:6006 접속

---

## 디자인 토큰 (Design Tokens)

### Colors
- Base: Background, Text, Border, Icon
- Brand: Primary, Hover, Disabled
- Status: Error, Warning, Success
- Social: Google, Kakao
- Theme: Light Mode

### Typography
- Headline: H1, H1-T, H1-M
- Title: T1, T1-T, T1-M
- Body: B1, B2
- Label: L1, L2, L3, L4

### Spacing
- 8px 그리드 시스템
- 4px ~ 160px 규격화

---

## 사용 가이드 (Usage Guide)

### Button
```tsx
import { Button } from './components/common/Button';

function App() {
  return (
    <Button variant="large" onClick={() => console.log('Action')}>
      로그인
    </Button>
  );
}
```

### Input
```tsx
import { Input } from './components/common/Input';

function LoginForm() {
  return (
    <Input type="email" placeholder="이메일을 입력하세요" label="이메일" />
  );
}
```

### Toast
```tsx
import { useToast } from './context/ToastContext';

function SubmitButton() {
  const { showToast } = useToast();

  return (
    <button onClick={() =>
      showToast({
        type: 'success',
        title: '완료',
        message: '성공적으로 저장되었습니다.',
      })
    }>
      제출하기
    </button>
  );
}
```

---

## 프로젝트 구조 (Directory Structure)

```text
asset-mind/
├── .storybook/
├── src/
│   ├── components/
│   │   ├── auth/
│   │   ├── common/
│   │   ├── icons/
│   │   └── DesignTokens/
│   ├── context/
│   ├── lib/
│   ├── stories/
│   └── docs/
├── public/
└── QA_Reports/
```

---

## 품질 관리 (Quality Assurance)

```bash
npx tsc --noEmit
npm run lint
npm run qa:a11y
```

---

## 브라우저 호환성 (Browser Support)

- Google Chrome (Latest)
- Mozilla Firefox (Latest)
- Apple Safari (Latest)
- Microsoft Edge (Latest)

---

## 라이선스 (License)

MIT License. LICENSE 파일 참조.

---

## 문의 및 기여 (Contact & Contribution)

- GitHub Issues
- Slack #design-system

---

Copyright © AssetMind Team. All Rights Reserved.
