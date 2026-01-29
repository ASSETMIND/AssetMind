import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './Button';
import { GoogleIcon } from '../icons/GoogleIcon';
import { KakaoIcon } from '../icons/KakaoIcon';

const meta: Meta<typeof Button> = {
  title: 'UI_KIT/Button',
  component: Button,
  parameters: {
    layout: 'centered',
    controls: { disable: true },
    actions: { disable: true },
  },
};

export default meta;
type Story = StoryObj<typeof Button>;

// 1. [메인] 로그인 버튼 (배경 박스 유지)
export const Login_Button_Large: Story = {
  decorators: [
    (Story) => (
      <div className="bg-background-surface p-10 rounded-[24px]" style={{ width: '451px' }}>
        <Story />
      </div>
    ),
  ],
  args: {
    variant: 'primary',
    size: 'lg', 
    fullWidth: true,
    children: '로그인',
  },
};

// 2. [소셜] 카카오 (중앙 정렬 추가)
export const Kakao_Icon_Button: Story = {
  decorators: [
    (Story) => (
      <div className="bg-background-surface p-10 rounded-[24px] w-[150px] h-[150px] flex justify-center items-center">
        <Story />
      </div>
    ),
  ],
  args: {
    variant: 'kakao',
    size: 'icon',
    children: <KakaoIcon className="w-10 h-10" />,
  },
};

// 3. [소셜] 구글 (중앙 정렬 추가)
export const Google_Icon_Button: Story = {
  decorators: [
    (Story) => (
      <div className="bg-background-surface p-10 rounded-[24px] w-[150px] h-[150px] flex justify-center items-center">
        <Story />
      </div>
    ),
  ],
  args: {
    variant: 'google',
    size: 'icon',
    children: <GoogleIcon className="w-10 h-10" />,
  },
};