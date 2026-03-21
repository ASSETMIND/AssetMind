import type { Meta, StoryObj } from '@storybook/react';
import { ToastItem } from './ToastItem';

const meta: Meta<typeof ToastItem> = {
  title: 'Components/Common/Toast',
  component: ToastItem,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
    controls: { disable: true },
    actions: { disable: true },
  },
  decorators: [
    (Story) => (
      <div className="bg-background-primary p-10 flex flex-col gap-4">
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof ToastItem>;

// ----------------------------------------------------------------
// [디자인 시안에 있는 4가지 케이스]
// ----------------------------------------------------------------

// 1. 비밀번호 변경 완료 (Success)
export const Case1_Password_Success: Story = {
  args: {
    variant: 'success',
    title: '비밀번호가 변경되었습니다.',
    message: '서비스 이용을 위해 다시 로그인해 주세요.',
  },
};

// 2. 인증 실패 (Error)
export const Case2_Verification_Fail: Story = {
  args: {
    variant: 'error',
    title: '인증에 실패했습니다.',
    message: '입력하신 정보가 정확한지 확인해 주세요.',
  },
};

// 3. 본인인증 실패 (Error)
export const Case3_Identity_Fail: Story = {
  args: {
    variant: 'error',
    title: '본인인증에 실패했습니다.',
    message: '잠시 후 다시 시도해주세요.',
  },
};

// 4. 로그인 실패 (Error)
export const Case4_Login_Fail: Story = {
  args: {
    variant: 'error',
    title: '로그인에 실패했습니다.',
    message: '잠시 후 다시 시도해주세요.',
  },
};