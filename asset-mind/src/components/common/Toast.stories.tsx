import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './Button';
import { ToastProvider, useToast } from '../../context/ToastContext';

const ToastTester = () => {
  const { showToast } = useToast();

  return (
    <div className="flex flex-col gap-4">
      <Button 
        variant="primary" 
        size="md"
        onClick={() => showToast('LOGIN_FAIL')}
      >
        로그인 실패 토스트 띄우기
      </Button>

      <Button 
        variant="secondary" 
        size="md"
        onClick={() => showToast('PASSWORD_CHANGE_SUCCESS')}
      >
        성공 토스트 띄우기
      </Button>
    </div>
  );
};

const meta: Meta<typeof ToastTester> = {
  // [수정] 'Toast' 폴더 아래 'Toast_Test'로 배치 (같은 폴더로 묶임)
  title: 'UI_KIT/Toast/Toast_Test',
  component: ToastTester,
  parameters: {
    layout: 'centered',
  },
  decorators: [
    (Story) => (
      <ToastProvider>
        <Story />
      </ToastProvider>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof ToastTester>;

export const Test_Run: Story = {};