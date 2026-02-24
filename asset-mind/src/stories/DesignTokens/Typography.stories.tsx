import type { Meta, StoryObj } from '@storybook/react';
import { TypographyViewer } from './TypographyViewer';
import { extractDesignTokens } from '../../lib/design-tokens';

const meta = {
  title: 'Foundation/Design Tokens/Typography',
  component: TypographyViewer,
  parameters: {
    layout: 'fullscreen',
    backgrounds: {
      default: 'dark',
    },
    docs: {
      description: {
        component: 'Typography System - Font styles and text formatting tokens from Tailwind Config.',
      },
    },
  },
  tags: ['autodocs'],
} satisfies Meta<typeof TypographyViewer>;

export default meta;
type Story = StoryObj<typeof meta>;

const designTokens = extractDesignTokens();

export const AllStyles: Story = {
  args: {
    tokens: designTokens.typography,
    title: 'AssetMind Typography System',
    sampleText: 'The quick brown fox jumps over the lazy dog',
  },
};

export const BodyStyles: Story = {
  args: {
    tokens: designTokens.typography.filter(t => t.name.startsWith('b')),
    title: 'Body Text Styles',
    sampleText: 'This is body text. It is used for paragraphs and general content throughout the application.',
  },
};

export const LabelStyles: Story = {
  args: {
    tokens: designTokens.typography.filter(t => t.name.startsWith('l')),
    title: 'Label & UI Text Styles',
    sampleText: 'This is label text. It is used for buttons, form labels, and UI elements.',
  },
};

export const CustomSample: Story = {
  args: {
    tokens: designTokens.typography,
    title: 'Custom Sample Text',
    sampleText: 'AssetMind - 디지털 자산 관리 플랫폼 | Digital Asset Management Platform',
  },
};

export const KoreanText: Story = {
  args: {
    tokens: designTokens.typography,
    title: 'Korean Text Preview',
    sampleText: '안녕하세요. AssetMind 디자인 시스템입니다. 다양한 폰트 스타일을 확인해보세요.',
  },
};

export const HeadlineStyles: Story = {
  args: {
    tokens: designTokens.typography.filter(t => t.name.startsWith('h')),
    title: 'Headline Styles',
    sampleText: 'AssetMind - 디지털 자산 관리의 새로운 기준',
  },
};

export const TitleStyles: Story = {
  args: {
    tokens: designTokens.typography.filter(t => t.name.startsWith('t')),
    title: 'Title Styles',
    sampleText: 'Dashboard Overview',
  },
};

export const ResponsiveHeadlines: Story = {
  args: {
    tokens: designTokens.typography.filter(t => t.name.includes('h1')),
    title: 'Responsive Headlines (Desktop/Tablet/Mobile)',
    sampleText: 'AssetMind',
  },
};