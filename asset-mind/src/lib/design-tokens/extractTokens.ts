/**
 * Design Token Extractor
 */

import type { ColorToken, ColorGroup, TypographyToken, DesignTokens } from './types';

const tailwindColors = {
  background: {
    primary: '#131316',
    disabled: '#161617',
    surface: '#1C1D21',
    elevated: '#21242C',
    hover: '#2C2C30',
    overlay: 'rgba(19,19,22,0.7)',
    surfaceError: 'rgba(236, 26, 19, 0.1)',
    surfaceWarning: 'rgba(245, 158, 11, 0.1)',
  },
  text: {
    primary: '#FFFFFF',
    secondary: '#9194A1',
    disabled: '#4B4B50',
    placeholder: '#808080',
    brand: '#0D59F2',
    link: '#0D59F2',
    error: '#EC1A13',
    success: '#256AF4',
    value: '#FFFFFF',
  },
  border: {
    divider: '#2F3037',
    inputNormal: '#383A42',
    inputHover: '#9194A1',
    inputFocus: '#FFFFFF',
    inputError: '#EC1A13',
    inputWarning: '#F59E0B',
    inputSuccess: '#256AF4',
  },
  icon: {
    secondary: '#9194A1',
  },
  brand: {
    primary: '#0D59F2',
    primaryHover: '#256AF4',
    disabled: '#18181B',
    onPrimary: '#FFFFFF',
  },
  button: {
    large: {
      primary: '#131316',
      primaryHover: '#2C2C30',
      disabled: '#18181B',
      label: '#FFFFFF',
      labelDisabled: '#4B4B50',
    },
    small: {
      primary: '#6D4AE6',
      primaryHover: '#5F3FD1',
      disabled: '#18181B',
      label: '#FFFFFF',
      labelDisabled: '#4B4B50',
    },
  },
  status: {
    error: '#EC1A13',
    errorHover: '#C01510',
    warning: '#F59E0B',
    warningHover: '#D97706',
    success: '#256AF4',
    rise: '#EA580C',
    fall: '#256AF4',
    premium: '#EAB308',
    spinner: '#FFFFFF',
  },
  toast: {
    bg: '#21242C',
    textTitle: '#FFFFFF',
    textBody: '#C8C5C5',
    iconSuccess: '#0D59F2',
    iconError: '#EC1A13',
    gradientSuccess: '#0D59F2',
    gradientError: '#EC1A13',
  },
  chart: {
    setA: '#C9A24D',
    setB: '#4FA3B8',
    setC: '#8A6BBE',
  },
  social: {
    google: {
      bg: '#FFFFFF',
      red: '#EB4335',
      blue: '#4285F4',
      yellow: '#FBBC05',
      green: '#34A853',
    },
    kakao: {
      bg: '#FEE500',
      icon: '#000000',
    },
  },
  light: {
    background: {
      primary: '#FFFFFF',
      surface: '#F4F5F7',
      elevated: '#E9EBEF',
      surfaceError: 'rgba(236, 26, 19, 0.1)',
      surfaceWarning: 'rgba(245, 158, 11, 0.1)',
    },
    text: {
      primary: '#131316',
      secondary: '#4B4B50',
      disabled: '#9194A1',
    },
    border: {
      divider: '#D1D3D8',
      inputNormal: '#C4C6CC',
      inputHover: '#9194A1',
      inputFocus: '#0D59F2',
      inputError: '#EC1A13',
      inputWarning: '#F59E0B',
      inputSuccess: '#256AF4',
    },
    brand: {
      primary: '#0D59F2',
      primaryHover: '#256AF4',
    },
    status: {
      error: '#EC1A13',
      warning: '#F59E0B',
      success: '#256AF4',
      rise: '#EA580C',
      fall: '#256AF4',
      premium: '#EAB308',
    },
  },
};

const tailwindFontSize = {
  b1: ['16px', { lineHeight: '150%', letterSpacing: '0em', fontWeight: '400' }],
  b2: ['14px', { lineHeight: '150%', letterSpacing: '0em', fontWeight: '400' }],
  l1: ['18px', { lineHeight: '100%', letterSpacing: '0.05em', fontWeight: '500' }],
  l2: ['16px', { lineHeight: '130%', letterSpacing: '0em', fontWeight: '400' }],
  l3: ['14px', { lineHeight: '100%', letterSpacing: '0.05em', fontWeight: '500' }],
  l4: ['14px', { lineHeight: '140%', letterSpacing: '0em', fontWeight: '400' }],
};

function extractColors(): ColorGroup[] {
  const colors = tailwindColors;
  const groups: ColorGroup[] = [];

  const categoryDescriptions: Record<string, string> = {
    background: 'Background colors - Main background, modals, cards',
    text: 'Text colors - Body text, labels, placeholders',
    border: 'Border colors - Dividers, input borders',
    icon: 'Icon colors',
    brand: 'Brand colors - Primary actions and emphasis',
    button: 'Button colors - Large/Small button styles',
    status: 'Status colors - Success, error, warning states',
    toast: 'Toast notification colors',
    chart: 'Chart auxiliary colors',
    social: 'Social login colors',
    light: 'Light mode colors',
  };

  Object.entries(colors).forEach(([category, colorSet]) => {
    const colorTokens: ColorToken[] = [];

    if (typeof colorSet === 'object' && colorSet !== null) {
      Object.entries(colorSet).forEach(([name, value]) => {
        if (typeof value === 'object' && value !== null) {
          Object.entries(value).forEach(([subName, subValue]) => {
            if (typeof subValue === 'string') {
              colorTokens.push({
                name: `${name}.${subName}`,
                value: subValue,
                category,
                subcategory: name,
              });
            } else if (typeof subValue === 'object' && subValue !== null) {
              Object.entries(subValue).forEach(([deepName, deepValue]) => {
                if (typeof deepValue === 'string') {
                  colorTokens.push({
                    name: `${name}.${subName}.${deepName}`,
                    value: deepValue,
                    category,
                    subcategory: `${name}.${subName}`,
                  });
                }
              });
            }
          });
        } else if (typeof value === 'string') {
          colorTokens.push({
            name,
            value,
            category,
          });
        }
      });
    }

    if (colorTokens.length > 0) {
      groups.push({
        category,
        description: categoryDescriptions[category],
        colors: colorTokens,
      });
    }
  });

  return groups;
}

function extractTypography(): TypographyToken[] {
  const fontSize = tailwindFontSize;
  const tokens: TypographyToken[] = [];

  Object.entries(fontSize).forEach(([name, config]) => {
    if (Array.isArray(config) && config.length >= 2) {
      const [size, styles] = config;
      if (typeof styles === 'object' && styles !== null) {
        tokens.push({
          name,
          fontSize: size as string, 
          lineHeight: styles.lineHeight || 'normal',
          letterSpacing: styles.letterSpacing || '0em',
          fontWeight: styles.fontWeight || '400',
        });
      }
    }
  });

  return tokens;
}

export function extractDesignTokens(): DesignTokens {
  return {
    colors: extractColors(),
    typography: extractTypography(),
    spacing: [],
  };
}

export function getColorsByCategory(category: string): ColorToken[] {
  const allColors = extractColors();
  const group = allColors.find((g) => g.category === category);
  return group?.colors || [];
}

export function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  if (hex.startsWith('rgba')) {
    const match = hex.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (match) {
      return {
        r: parseInt(match[1]),
        g: parseInt(match[2]),
        b: parseInt(match[3]),
      };
    }
  }

  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result
    ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16),
      }
    : null;
}

export function getColorBrightness(hex: string): number {
  const rgb = hexToRgb(hex);
  if (!rgb) return 0;
  return (rgb.r * 299 + rgb.g * 587 + rgb.b * 114) / 1000;
}

export function needsLightText(hex: string): boolean {
  return getColorBrightness(hex) < 128;
}