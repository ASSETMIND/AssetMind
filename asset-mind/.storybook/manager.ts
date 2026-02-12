import { addons } from '@storybook/addons';
import { themes } from '@storybook/theming';

addons.setConfig({
  theme: {
    ...themes.dark,
    
    // Brand
    brandTitle: 'AssetMind Design System',
    brandUrl: 'https://assetmind.com',
    brandTarget: '_self',
    
    // Colors
    colorPrimary: '#0D59F2',
    colorSecondary: '#256AF4',
    
    // UI
    appBg: '#131316',
    appContentBg: '#1C1D21',
    appBorderColor: '#2F3037',
    appBorderRadius: 8,
    
    // Text colors
    textColor: '#FFFFFF',
    textInverseColor: '#131316',
    
    // Toolbar
    barTextColor: '#9194A1',
    barSelectedColor: '#0D59F2',
    barBg: '#1C1D21',
    
    // Form colors
    inputBg: '#1C1D21',
    inputBorder: '#383A42',
    inputTextColor: '#FFFFFF',
    inputBorderRadius: 8,
    
    // Font
    fontBase: '"Pretendard Variable", "Pretendard", -apple-system, BlinkMacSystemFont, system-ui, sans-serif',
    fontCode: 'monospace',
  },
  sidebar: {
    showRoots: true,
    collapsedRoots: [],
  },
  toolbar: {
    title: { hidden: false },
    zoom: { hidden: false },
    eject: { hidden: false },
    copy: { hidden: false },
    fullscreen: { hidden: false },
  },
});