import type { Preview } from "@storybook/react";
import "../src/index.css";

/* Storybook Docs 스크롤 강제 복구 + Pretendard 폰트 강제 적용 */
const style = document.createElement("style");
style.innerHTML = `
  /* html/body 고정 높이/스크롤 차단 제거 */
  html, body {
    height: auto !important;
    overflow-y: auto !important;
  }
  
  /* Storybook 루트 */
  #storybook-root {
    height: auto !important;
    overflow-y: auto !important;
  }
  
  /* Docs 컨테이너 */
  .sbdocs-wrapper,
  .sbdocs-content {
    height: auto !important;
    max-height: none !important;
    overflow-y: auto !important;
  }
  
  /* Pretendard 폰트 강제 적용 - 모든 요소에 */
  html,
  body,
  #storybook-root,
  #storybook-root *,
  .sbdocs-wrapper,
  .sbdocs-wrapper *,
  .sbdocs-content,
  .sbdocs-content *,
  .docs-story,
  .docs-story *,
  div,
  span,
  p,
  h1, h2, h3, h4, h5, h6,
  button,
  input,
  textarea {
    font-family: "Pretendard Variable", "Pretendard", -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
  }
`;
document.head.appendChild(style);

const preview: Preview = {
  parameters: {
    backgrounds: {
      default: "surface",
      values: [
        { name: "surface", value: "#1C1D21" },
        { name: "dark", value: "#131316" },
        { name: "light", value: "#ffffff" },
      ],
    },
    layout: "centered",
    controls: { hideNoControlsWarning: true },
  },
};

export default preview;