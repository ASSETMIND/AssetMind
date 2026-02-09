import type { Preview } from "@storybook/react";
import "../src/index.css";

/* 🔧 Storybook Docs 스크롤 강제 복구 */
const style = document.createElement("style");
style.innerHTML = `
  /* html/body에 걸린 고정 높이/스크롤 차단 해제 */
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
