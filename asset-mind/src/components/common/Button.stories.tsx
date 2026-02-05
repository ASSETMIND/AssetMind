import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './Button';
import { GoogleIcon } from '../icons/GoogleIcon';
import { KakaoIcon } from '../icons/KakaoIcon';
import { useState } from 'react';

const meta: Meta<typeof Button> = {
  title: 'UI_KIT/Button',
  component: Button,
  parameters: {
    layout: 'centered',
    backgrounds: { 
      default: 'dark',
      values: [
        { name: 'dark', value: '#2E2F33' },
        { name: 'surface', value: '#121212' },
      ],
    },
    docs: {
      description: {
        component: '다양한 variant와 상태를 지원하는 버튼 컴포넌트입니다. 접근성 기능(aria-label, 키보드 탐색, 로딩 상태)이 포함되어 있습니다.',
      },
    },
  },
  decorators: [
    (Story) => (
      <div style={{ width: '451px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '20px' }}>
        <Story />
      </div>
    ),
  ],
  argTypes: {
    variant: { table: { disable: true } },
    size: { table: { disable: true } },
    fullWidth: { table: { disable: true } },
    className: { table: { disable: true } },
    children: { table: { disable: true } },
    disabled: { table: { disable: true } },
  },
};

export default meta;
type Story = StoryObj<typeof Button & { status?: string }>;

// =============================================================================
// 1. 메인 로그인 버튼
// [수정] Loading 상태: 배경 #1C1D21 (비활성) + 아이콘 흰색 (White)
// =============================================================================
export const Main_Login_Button: Story = {
  name: 'Main Login Button',
  args: {
    ...({ status: 'default' } as any),
  },
  argTypes: {
    status: {
      control: 'radio',
      options: ['default', 'disabled', 'loading'],
      description: '상태 선택',
    },
  },
  render: (args) => {
    const status = (args as any).status;

    const baseProps = {
      variant: 'primary' as const,
      size: 'lg' as const,
      fullWidth: true,
      className: "h-[52px] text-[16px] font-medium whitespace-nowrap",
    };

    switch (status) {
      case 'default':
        return <Button {...baseProps}>로그인</Button>;
      
      case 'disabled':
        // Neutral-850(#1C1D21) 배경 + Neutral-300(#5F616B) 텍스트
        return (
          <Button {...baseProps} disabled className={`${baseProps.className} bg-[#1C1D21] text-[#5F616B] border-none opacity-100`}>
            로그인
          </Button>
        );
      
      case 'loading':
        // [수정] 배경: #1C1D21 (비활성과 동일), 스피너만 표시 (텍스트 없음)
        return (
          <Button 
            {...baseProps} 
            isLoading={true}
            loadingText=""
            className={`${baseProps.className} bg-[#1C1D21] text-white border-none cursor-wait`}
            aria-label="로그인 처리 중"
          />
        );

      default:
        return <Button {...baseProps}>로그인</Button>;
    }
  },
};

// =============================================================================
// 2. 메인 가입하기 버튼
// =============================================================================
export const Main_SignUp_Button: Story = {
  name: 'Main SignUp Button',
  args: {
    ...({ status: 'default' } as any),
  },
  argTypes: {
    status: {
      control: 'radio',
      options: ['default', 'disabled'],
      description: '상태 선택',
    },
  },
  render: (args) => {
    const status = (args as any).status;

    const baseProps = {
      variant: 'primary' as const,
      size: 'lg' as const,
      fullWidth: true,
      className: "h-[52px] text-[16px] font-medium whitespace-nowrap",
    };

    switch (status) {
      case 'default':
        return <Button {...baseProps}>가입하기</Button>;
      
      case 'disabled':
        return (
          <Button {...baseProps} disabled className={`${baseProps.className} bg-[#1C1D21] text-[#5F616B] border-none opacity-100`}>
            가입하기
          </Button>
        );

      default:
        return <Button {...baseProps}>가입하기</Button>;
    }
  },
};

// =============================================================================
// 3. 중복 확인
// =============================================================================
export const Duplicate_Check: Story = {
  name: 'Duplicate Check Button',
  render: () => (
    <Button 
      className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] font-normal rounded-[9px] w-[100px] h-[38px] whitespace-nowrap"
      aria-label="아이디 중복 확인"
    >
      중복 확인
    </Button>
  ),
};
// =============================================================================
// 4. 인증 확인
// =============================================================================
export const Verify_Auth: Story = {
  name: 'Verify Auth Button',
  args: {
    ...({ status: 'default' } as any),
  },
  argTypes: {
    status: {
      control: 'radio',
      options: ['default', 'disabled', 'loading'],
      description: '상태 선택',
    },
  },
  render: (args) => {
    const status = (args as any).status;
    const smallBase = "text-[14px] font-normal rounded-[9px] w-[100px] h-[38px] flex items-center justify-center transition-colors whitespace-nowrap";
    
    if (status === 'default') {
      return (
        <Button 
          className={`${smallBase} bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white`}
          aria-label="인증번호 확인"
        >
          인증 확인
        </Button>
      );
    }
    
    if (status === 'disabled') {
      return (
        <Button 
          className={`${smallBase} bg-[#1C1D21] text-[#5F616B] cursor-not-allowed`}
          disabled
          aria-label="인증 확인 비활성"
        >
          인증 확인
        </Button>
      );
    }
    
    if (status === 'loading') {
      return (
        <Button
          className={`${smallBase} bg-[#6D4AE6] disabled:bg-[#6D4AE6] disabled:opacity-100 text-white cursor-wait [&_svg]:mr-0`}
          isLoading={true}
          loadingText=""
          aria-label="인증 확인 중"
        >
           {null}
        </Button>
      );
    }
    return <></>;
  },
};

// =============================================================================
// 5. 인증번호 전송
// =============================================================================
export const Send_Auth_Code: Story = {
  name: 'Send Auth Code Button',
  args: {
    isResend: false,
  },
  argTypes: {
    isResend: {
      control: 'boolean',
      description: '재전송 여부 (default: 인증번호 전송 / true: 인증번호 재전송)',
    },
  },
  render: ({ isResend }) => (
    <Button 
      className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] font-normal rounded-[9px] w-[121px] h-[38px] whitespace-nowrap"
      aria-label={isResend ? "인증번호 재전송" : "인증번호 전송"}
    >
      {isResend ? '인증번호 재전송' : '인증번호 전송'}
    </Button>
  ),
};

// =============================================================================
// 6. 소셜 로그인 아이콘
// =============================================================================
export const Social_Icons: Story = {
  name: 'Social Icons',
  render: () => (
    <div className="flex gap-4">
      <Button 
        variant="google" 
        size="icon" 
        className="w-[56px] h-[56px] p-0 rounded-full bg-white"
        aria-label="Google 로그인"
      >
        <GoogleIcon className="w-[40px] h-[40px]" />
      </Button>
      <Button 
        variant="kakao" 
        size="icon" 
        className="w-[56px] h-[56px] p-0 rounded-full bg-[#FEE500]"
        aria-label="카카오 로그인"
      >
        <KakaoIcon className="w-[40px] h-[40px]" />
      </Button>
    </div>
  ),
};

// =============================================================================
// 7. 인터랙티브 예제 - 로그인 시나리오
// =============================================================================
export const Interactive_Login_Flow: Story = {
  name: 'Interactive - Login Flow',
  parameters: {
    docs: {
      description: {
        story: '실제 로그인 시나리오를 시연합니다. 버튼 클릭 시 로딩 상태로 전환되고 2초 후 비활성화됩니다.',
      },
    },
  },
  render: () => {
    const [isLoading, setIsLoading] = useState(false);
    const [isDisabled, setIsDisabled] = useState(false);

    const handleLogin = async () => {
      setIsLoading(true);

      // 2초 후 완료
      setTimeout(() => {
        setIsLoading(false);
        setIsDisabled(true);

        // 3초 후 초기화
        setTimeout(() => {
          setIsDisabled(false);
        }, 3000);
      }, 2000);
    };

    return (
      <Button
        variant="primary"
        size="lg"
        fullWidth
        className="h-[52px] text-[16px] font-medium whitespace-nowrap"
        onClick={handleLogin}
        isLoading={isLoading}
        loadingText=""
        disabled={isDisabled}
        aria-label={isDisabled ? "로그인 완료" : "로그인"}
      >
        {!isLoading && '로그인'}
      </Button>
    );
  },
};

// =============================================================================
// 8. 인터랙티브 예제 - 키보드 탐색 데모
// =============================================================================
export const Interactive_Keyboard_Navigation: Story = {
  name: 'Interactive - Keyboard Navigation',
  parameters: {
    docs: {
      description: {
        story: 'Tab 키로 버튼들을 탐색하고, Enter/Space 키로 버튼을 클릭할 수 있습니다. Focus 상태를 확인하세요.',
      },
    },
  },
  render: () => {
    const [lastClicked, setLastClicked] = useState<string>('');

    const handleClick = (buttonName: string) => {
      setLastClicked(buttonName);
    };

    return (
      <div className="flex flex-col items-center gap-4 w-full">
        <p className="text-[14px] text-text-secondary text-center mb-2">
          Tab 키로 이동, Enter/Space로 클릭
        </p>

        <Button
          variant="primary"
          size="lg"
          fullWidth
          className="h-[52px]"
          onClick={() => handleClick('Primary 버튼')}
        >
          Primary 버튼
        </Button>

        <div className="flex gap-2 justify-center">
          <Button
            className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] rounded-[9px] w-[100px] h-[38px]"
            onClick={() => handleClick('액션 1')}
          >
            액션 1
          </Button>
          <Button
            className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] rounded-[9px] w-[100px] h-[38px]"
            onClick={() => handleClick('액션 2')}
          >
            액션 2
          </Button>
        </div>

        <Button
          variant="primary"
          size="lg"
          fullWidth
          className="h-[52px]"
          disabled
          aria-label="비활성 버튼"
        >
          비활성 버튼 (Tab으로 건너뜀)
        </Button>

        {lastClicked && (
          <p className="text-[14px] text-white text-center mt-2">
            마지막 클릭: {lastClicked}
          </p>
        )}
      </div>
    );
  },
};

// =============================================================================
// 9. Controls Playground (모든 Props 테스트)
// =============================================================================
export const Playground: Story = {
  name: 'Playground',
  parameters: {
    docs: {
      description: {
        story: 'Controls 패널에서 메인 로그인 버튼의 모든 props를 자유롭게 조작해보세요.',
      },
    },
  },
  argTypes: {
    variant: {
      control: 'select',
      options: ['primary', 'secondary', 'kakao', 'google'],
      description: '버튼 스타일 변형',
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg', 'icon'],
      description: '버튼 크기',
    },
    fullWidth: {
      control: 'boolean',
      description: '전체 너비 사용 여부',
    },
    disabled: {
      control: 'boolean',
      description: '비활성화 상태',
    },
    isLoading: {
      control: 'boolean',
      description: '로딩 상태',
    },
    children: {
      control: 'text',
      description: '버튼 텍스트',
    },
  },
  args: {
    children: '로그인',
    variant: 'primary',
    size: 'lg',
    fullWidth: true,
    disabled: false,
    isLoading: false,
  },
  render: (args) => (
    <Button
      variant={args.variant}
      size={args.size}
      fullWidth={args.fullWidth}
      disabled={args.disabled}
      isLoading={args.isLoading}
      loadingText=""
      className="h-[52px] text-[16px] font-medium whitespace-nowrap"
    >
      {!args.isLoading && args.children}
    </Button>
  ),
};
