import type { Meta, StoryObj } from '@storybook/react';
import { SignUpModal } from './SignUpModal';

// 이 파일을 SignUpModal.tsx와 같은 폴더에 넣어주세요!

const meta: Meta<typeof SignUpModal> = {
  title: 'UI_KIT/SignUpModal',
  component: SignUpModal,
  parameters: {
    layout: 'fullscreen',
    backgrounds: { default: 'dark' },
  },
  argTypes: {
    isOpen: {
      description: '모달 표시 여부',
      control: 'boolean',
    },
  },
};

export default meta;
type Story = StoryObj<typeof SignUpModal>;

export const Default: Story = {
  name: 'Sing Up Modal',
  args: {
    isOpen: true,
    onClose: () => console.log('모달 닫기'),
    onSwitchToLogin: () => console.log('로그인 화면으로 전환'),
  },
};

export const Closed: Story = {
  name: 'Closed',
  args: {
    isOpen: false,
    onClose: () => console.log('모달 닫기'),
    onSwitchToLogin: () => console.log('로그인 화면으로 전환'),
  },
};
