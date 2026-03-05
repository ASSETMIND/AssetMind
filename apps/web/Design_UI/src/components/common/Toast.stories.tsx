import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './Button';
import { ToastProvider, useToast } from '../../context/ToastContext';
import { useState } from 'react';

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

// =============================================================================
// 지속 시간 조절 데모 컴포넌트
// =============================================================================
const ToastDurationDemo = () => {
  const { showToast } = useToast();
  const [customDuration, setCustomDuration] = useState(3000);

  return (
    <div className="flex flex-col gap-6 items-center">
      <div className="text-center">
        <p className="text-[14px] text-[#E5E5E5] mb-2">
          Toast 지속 시간 설정 (기본값: 3초)
        </p>
        <div className="flex items-center gap-3 justify-center">
          <input
            type="range"
            min="1000"
            max="10000"
            step="500"
            value={customDuration}
            onChange={(e) => setCustomDuration(Number(e.target.value))}
            className="w-[200px]"
          />
          <span className="text-white text-[14px] w-[60px]">
            {(customDuration / 1000).toFixed(1)}초
          </span>
        </div>
      </div>

      <div className="flex flex-col gap-3 w-full">
        <Button 
          variant="primary" 
          size="md"
          fullWidth
          onClick={() => showToast('PASSWORD_CHANGE_SUCCESS', customDuration)}
          className="h-[48px]"
        >
          설정한 시간만큼 표시
        </Button>

        <div className="grid grid-cols-3 gap-2">
          <Button 
            size="sm"
            onClick={() => showToast('LOGIN_FAIL', 1000)}
            className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] h-[38px]"
          >
            1초
          </Button>
          <Button 
            size="sm"
            onClick={() => showToast('VERIFICATION_FAIL', 3000)}
            className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] h-[38px]"
          >
            3초
          </Button>
          <Button 
            size="sm"
            onClick={() => showToast('IDENTITY_FAIL', 5000)}
            className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] h-[38px]"
          >
            5초
          </Button>
        </div>
      </div>
    </div>
  );
};

// =============================================================================
// 여러 Toast 동시에 띄우기 데모
// =============================================================================
const MultipleToastsDemo = () => {
  const { showToast } = useToast();

  const showMultipleToasts = () => {
    showToast('PASSWORD_CHANGE_SUCCESS', 5000);
    setTimeout(() => showToast('LOGIN_FAIL', 4000), 500);
    setTimeout(() => showToast('VERIFICATION_FAIL', 3000), 1000);
  };

  return (
    <div className="flex flex-col gap-4">
      <Button 
        variant="primary" 
        size="lg"
        onClick={showMultipleToasts}
        className="h-[52px]"
      >
        여러 Toast 동시에 띄우기
      </Button>

      <p className="text-[14px] text-[#E5E5E5] text-center">
        3개의 Toast가 순차적으로 나타납니다
      </p>
    </div>
  );
};

// =============================================================================
// Meta 설정
// =============================================================================
const meta: Meta<typeof ToastTester> = {
  title:'Components/Common/Toast/Interactive',
  component: ToastTester,
  parameters: {
    layout: 'centered',
    backgrounds: { 
      default: 'dark',
      values: [
        { name: 'dark', value: '#2E2F33' },
      ],
    },
    docs: {
      description: {
        component: 'Toast 알림 시스템의 인터랙티브 데모입니다. 버튼 클릭으로 Toast를 트리거하고, 지속 시간을 조절할 수 있습니다.',
      },
    },
  },
  decorators: [
    (Story) => (
      <ToastProvider>
        <div style={{ width: '400px' }}>
          <Story />
        </div>
      </ToastProvider>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof ToastTester>;

// =============================================================================
// Stories
// =============================================================================

export const Basic_Toast_Trigger: Story = {
  name: 'Basic - Toast Trigger',
  parameters: {
    docs: {
      description: {
        story: '버튼을 클릭하여 Toast 알림을 띄울 수 있습니다. 기본 지속 시간은 3초입니다.',
      },
    },
  },
  render: () => <ToastTester />,
};

export const Custom_Duration: Story = {
  name: 'Custom Duration',
  parameters: {
    docs: {
      description: {
        story: 'Toast의 지속 시간을 1초~10초 사이로 조절할 수 있습니다. 슬라이더를 이용해 원하는 시간을 설정하세요.',
      },
    },
  },
  render: () => <ToastDurationDemo />,
};

export const Multiple_Toasts: Story = {
  name: 'Multiple Toasts',
  parameters: {
    docs: {
      description: {
        story: '여러 Toast를 동시에 띄울 수 있습니다. Toast들은 화면 상단에 쌓이며, 각각 설정된 시간 후 사라집니다.',
      },
    },
  },
  render: () => <MultipleToastsDemo />,
};

export const All_Toast_Types: Story = {
  name: 'All Toast Types',
  parameters: {
    docs: {
      description: {
        story: '모든 Toast 타입(Success, Error)을 확인할 수 있습니다.',
      },
    },
  },
  render: () => {
    const { showToast } = useToast();

    return (
      <div className="flex flex-col gap-3">
        <Button 
          variant="primary" 
          size="md"
          fullWidth
          onClick={() => showToast('PASSWORD_CHANGE_SUCCESS')}
          className="h-[48px] bg-[#0D59F2] hover:bg-[#0B4DD1]"
        >
          Success - 비밀번호 변경
        </Button>

        <Button 
          variant="primary" 
          size="md"
          fullWidth
          onClick={() => showToast('LOGIN_FAIL')}
          className="h-[48px] bg-[#EC1A13] hover:bg-[#D01710]"
        >
          Error - 로그인 실패
        </Button>

        <Button 
          variant="primary" 
          size="md"
          fullWidth
          onClick={() => showToast('VERIFICATION_FAIL')}
          className="h-[48px] bg-[#EC1A13] hover:bg-[#D01710]"
        >
          Error - 인증 실패
        </Button>

        <Button 
          variant="primary" 
          size="md"
          fullWidth
          onClick={() => showToast('IDENTITY_FAIL')}
          className="h-[48px] bg-[#EC1A13] hover:bg-[#D01710]"
        >
          Error - 본인인증 실패
        </Button>
      </div>
    );
  },
};