/**
 * Design Token Types
 */

export interface ColorToken {
  name: string;
  value: string;
  category: string;
  subcategory?: string;
  description?: string;
}

export interface ColorGroup {
  category: string;
  description?: string;
  colors: ColorToken[];
}

export interface TypographyToken {
  name: string;
  fontSize: string;
  lineHeight: string;
  letterSpacing: string;
  fontWeight: string;
}

export interface SpacingToken {
  name: string;
  value: string;
}

export interface DesignTokens {
  colors: ColorGroup[];
  typography: TypographyToken[];
  spacing: SpacingToken[];
}