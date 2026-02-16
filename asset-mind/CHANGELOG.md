# Changelog

All notable changes to the AssetMind Design System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Planned
- **Components**: Dropdown, Checkbox, Radio, Select 등 폼 요소 추가
- **Feature**: 다크 모드/라이트 모드 시스템 자동 전환 기능
- **Responsive**: 모바일 환경 대응을 위한 반응형 컴포넌트 개선
- **Test**: 단위 테스트(Unit Test) 커버리지 80% 이상 확대
- **Performance**: 번들 사이즈 최적화 및 트리쉐이킹 개선

## [1.0.0] - 2026-02-15
### Added

#### Components
- `LoginModal`: 사용자 인증을 위한 로그인 모달
- `SignUpModal`: 신규 회원가입 프로세스 모달
- `Button`: Large/Small 변형(Variant) 및 다양한 상태 지원
- `Input`: 유효성 검사(에러/성공) 상태를 시각적으로 지원하는 입력 필드
- `Modal`: 재사용 가능한 범용 모달 다이얼로그
- `Toast`: 전역 알림 시스템 (ToastContext 및 Provider 포함)
- `CodeSnippet`: 구문 강조(Syntax Highlighting) 및 복사 기능 지원
- **Icons**: `CloseIcon`, `EyeIcon`, `GoogleIcon`, `KakaoIcon` 추가

#### Design Tokens
- **Color System**: Light/Dark 모드를 지원하는 100개 이상의 색상 토큰 정의
- **Typography System**: Headline(H), Title(T), Body(B), Label(L) 등 12종 스타일 정의
- **Spacing System**: 8px 그리드 시스템 기반 (4px ~ 160px)

#### Documentation (Storybook)
- Storybook 기반의 인터랙티브 컴포넌트 문서화 환경 구축
- Design Tokens(Color, Typography, Spacing) 시각화 페이지 추가
- 개발자 가이드(Getting Started) 및 설치 매뉴얼 작성
- 접근성(A11y) 가이드라인 및 컴포넌트별 체크리스트 제공

#### Accessibility (A11y)
- **Compliance**: WCAG 2.1 AA 기준 준수
- **Navigation**: 전 컴포넌트 키보드 포커스 및 네비게이션 지원
- **ARIA**: 스크린 리더 지원을 위한 적절한 ARIA 속성 적용
- **Tooling**: Storybook A11y Addon 통합으로 실시간 접근성 검사 환경 마련

#### Development & Infrastructure
- **Language**: TypeScript 5.9.3 기반의 정적 타입 시스템 적용
- **Styling**: Tailwind CSS 3.4.17 및 커스텀 설정(Config) 적용
- **Build**: Vite 6.0.11 기반의 고속 빌드 환경 구성
- **Quality**: ESLint, Prettier 설정을 통한 코드 컨벤션 통일
- **Test**: Vitest 테스트 환경 구축
- **Core**: React 18.3.1 및 Storybook 10.2.5 버전 적용