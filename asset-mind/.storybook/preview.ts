import type { Preview } from "@storybook/react";
import "../src/index.css"; 

const preview: Preview = {
  parameters: {
    backgrounds: {
      // [중요] 'default'를 surface로 설정하여 버튼(#131316)과 구분되게 함
      default: 'surface', 
      values: [
        { name: 'surface', value: '#1C1D21' }, // 모달 배경색 (이 위에서 버튼이 보임)
        { name: 'dark', value: '#131316' },    // 메인 배경색
        { name: 'light', value: '#ffffff' },
      ],
    },
    layout: 'centered',
    // 불필요한 자동 컨트롤 제거
    controls: { hideNoControlsWarning: true }, 
  },
};

export default preview;