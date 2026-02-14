# AssetMind Design System - QA Checklist

**Date**: 2026-02-12  
**Version**: 1.0.0

---

## ✅ 1. 전체 시스템 검수

### 1.1 Design Tokens

- [ ] Color Palette 모든 색상 표시
- [ ] HEX 코드 복사 기능 작동
- [ ] Typography Pretendard 폰트 적용
- [ ] Spacing 스케일 시각화

### 1.2 Components

- [ ] Button: Large/Small, Hover/Disabled
- [ ] Input: 기본/Error/Success 상태
- [ ] Modal: Open/Close, Overlay
- [ ] Toast: 애니메이션, 스타일

---

## 🌐 2. 크로스 브라우저 테스트

### Desktop
- [ ] Chrome (Latest)
- [ ] Firefox (Latest)
- [ ] Edge (Latest)
- [ ] Safari (macOS)

### Mobile
- [ ] Chrome Mobile (Android)
- [ ] Safari Mobile (iOS)

---

## ♿ 3. 접근성 검증

### WCAG 2.1 AA
- [ ] 색상 대비 4.5:1
- [ ] 키보드 네비게이션
- [ ] 포커스 표시
- [ ] ARIA 라벨

### 자동화 도구
- [ ] Storybook A11y Addon
- [ ] Lighthouse 점수 90+
- [ ] axe DevTools

---

## 🐛 4. 발견된 버그

| ID | Severity | Component | Description | Status |
|----|----------|-----------|-------------|--------|
| | | | | |

---

## 📦 5. 빌드 & 배포

- [ ] Build 성공
- [ ] 번들 크기 확인
- [ ] 성능 최적화
- [ ] 배포 환경 설정
