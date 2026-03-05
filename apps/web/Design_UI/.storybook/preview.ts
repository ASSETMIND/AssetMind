import type { Preview } from "@storybook/react";
import "../src/index.css";

// ----------------------------------------------------------------------
// 1. 스타일 주입
// ----------------------------------------------------------------------
const style = document.createElement("style");
style.innerHTML = `
  html, body, #storybook-root {
    height: auto !important;
    overflow-y: auto !important;
  }
  .sbdocs-wrapper, .sbdocs-content {
    height: auto !important;
    max-height: none !important;
    overflow-y: auto !important;
  }
  /* 폰트 적용 */
  html, body, #storybook-root, #storybook-root *,
  .sbdocs-wrapper, .sbdocs-wrapper *,
  .sbdocs-content, .sbdocs-content *,
  div, span, p, h1, h2, h3, h4, h5, h6,
  button, input, textarea {
    font-family: "Pretendard Variable", "Pretendard", -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
  }
  /* 테마 커스터마이징 */
  .sb-show-main { background-color: #131316 !important; }
  .sidebar-container { background-color: #1C1D21 !important; border-right: 1px solid #2F3037 !important; }
  .sb-bar { background-color: #1C1D21 !important; border-bottom: 1px solid #2F3037 !important; }
  [data-selected="true"] { background-color: rgba(13, 89, 242, 0.1) !important; color: #0D59F2 !important; }
  a { color: #0D59F2 !important; }
  button:focus-visible, a:focus-visible { outline: 2px solid #0D59F2 !important; outline-offset: 2px !important; }
`;
document.head.appendChild(style);

// ----------------------------------------------------------------------
// 2. Preview 설정
// ----------------------------------------------------------------------
const preview: Preview = {
  parameters: {
    options: {
      storySort: {
        order: [
          // 1순위: Getting Started 
          "Getting Started", "GETTING-STARTED", "Getting-Started", "getting-started",
          
          // 2순위: Foundation
          "Foundation", "FOUNDATION", "foundation", "Design Tokens",
          
          // 3순위: Components
          "Components", "COMPONENTS", "components",
          
          // 4순위: Docs
          "Docs", "DOCS", "docs",
          
          // 나머지
          "*"
        ],
      },
    },
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
    docs: {
      theme: {
        base: 'dark',
        brandTitle: 'AssetMind Design System',
        brandUrl: 'https://assetmind.com',
        brandTarget: '_self',
        colorPrimary: '#0D59F2',
        colorSecondary: '#256AF4',
        appBg: '#131316',
        appContentBg: '#1C1D21',
        appBorderColor: '#2F3037',
        appBorderRadius: 8,
        textColor: '#FFFFFF',
        textInverseColor: '#131316',
        barTextColor: '#9194A1',
        barSelectedColor: '#0D59F2',
        barBg: '#1C1D21',
        inputBg: '#1C1D21',
        inputBorder: '#383A42',
        inputTextColor: '#FFFFFF',
        inputBorderRadius: 8,
        fontBase: '"Pretendard Variable", "Pretendard", -apple-system, BlinkMacSystemFont, system-ui, sans-serif',
        fontCode: 'monospace',
      },
    },
  },
};

export default preview;