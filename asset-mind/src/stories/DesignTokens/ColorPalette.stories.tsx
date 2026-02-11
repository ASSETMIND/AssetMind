import type { Meta, StoryObj } from '@storybook/react';
import { ColorPalette } from './ColorPalette';
import { extractDesignTokens } from '../../lib/design-tokens';

const meta = {
  title: 'Design Tokens/Color Palette',
  component: ColorPalette,
  parameters: {
    layout: 'fullscreen',
    backgrounds: {
      default: 'dark',
    },
    docs: {
      description: {
        component: 'AssetMind Color Palette - Tailwind Config auto-sync design token visualization system.',
      },
    },
  },
  tags: ['autodocs'],
} satisfies Meta<typeof ColorPalette>;

export default meta;
type Story = StoryObj<typeof meta>;

const designTokens = extractDesignTokens();

export const AllColors: Story = {
  args: {
    groups: designTokens.colors,
    title: 'AssetMind Color Palette',
    showCode: true,
  },
};

export const BackgroundColors: Story = {
  args: {
    groups: designTokens.colors.filter(g => g.category === 'background'),
    title: 'Background Colors',
    showCode: true,
  },
};

export const TextColors: Story = {
  args: {
    groups: designTokens.colors.filter(g => g.category === 'text'),
    title: 'Text Colors',
    showCode: true,
  },
};

export const BorderColors: Story = {
  args: {
    groups: designTokens.colors.filter(g => g.category === 'border'),
    title: 'Border Colors',
    showCode: true,
  },
};

export const BrandColors: Story = {
  args: {
    groups: designTokens.colors.filter(g => g.category === 'brand'),
    title: 'Brand Colors',
    showCode: true,
  },
};

export const ButtonColors: Story = {
  args: {
    groups: designTokens.colors.filter(g => g.category === 'button'),
    title: 'Button Colors',
    showCode: true,
  },
};

export const StatusColors: Story = {
  args: {
    groups: designTokens.colors.filter(g => g.category === 'status'),
    title: 'Status Colors',
    showCode: true,
  },
};

export const OtherColors: Story = {
  args: {
    groups: designTokens.colors.filter(g => 
      ['toast', 'chart', 'social', 'icon'].includes(g.category)
    ),
    title: 'Other Colors',
    showCode: true,
  },
};

export const LightModeColors: Story = {
  args: {
    groups: designTokens.colors.filter(g => g.category === 'light'),
    title: 'Light Mode Colors',
    showCode: true,
  },
};

export const WithoutCode: Story = {
  args: {
    groups: designTokens.colors,
    title: 'Color Palette (Simple View)',
    showCode: false,
  },
};