import type { Meta, StoryObj } from '@storybook/react';
import { SpacingViewer } from './SpacingViewer';

const meta = {
  title: 'Foundation/Design Tokens/Spacing',
  component: SpacingViewer,
  parameters: {
    layout: 'fullscreen',
    backgrounds: {
      default: 'dark',
    },
    docs: {
      description: {
        component: 'Spacing System - Margin, padding, and gap tokens based on Tailwind spacing scale.',
      },
    },
  },
  tags: ['autodocs'],
} satisfies Meta<typeof SpacingViewer>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    title: 'AssetMind Spacing System',
  },
};

export const SpacingScale: Story = {
  args: {
    title: 'Spacing Scale Reference',
  },
};