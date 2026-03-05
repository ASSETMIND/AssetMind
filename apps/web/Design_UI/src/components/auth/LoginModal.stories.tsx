import type { Meta, StoryObj } from '@storybook/react';
import { LoginModal } from './LoginModal';

const meta: Meta<typeof LoginModal> = {
  title: 'Components/Auth/LoginModal',
  component: LoginModal,
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
type Story = StoryObj<typeof LoginModal>;

export const Default: Story = {
  name: 'Login Modal',
  args: {
    isOpen: true,
    onClose: () => console.log('모달 닫기'),
    onLogin: (id: string, pw: string) => console.log('로그인:', { id, pw }),
  },
};

export const Closed: Story = {
  name: 'Closed',
  args: {
    isOpen: false,
    onClose: () => console.log('모달 닫기'),
    onLogin: (id: string, pw: string) => console.log('로그인:', { id, pw }),
  },
};
