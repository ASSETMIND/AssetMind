import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './Button';
import { GoogleIcon } from '../icons/GoogleIcon';
import { KakaoIcon } from '../icons/KakaoIcon';
import { Loader2 } from 'lucide-react';

const meta: Meta<typeof Button> = {
  title: 'UI_KIT/Button',
  component: Button,
  parameters: {
    layout: 'centered',
    backgrounds: { default: 'surface' },
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
        // [수정] 배경: #1C1D21 (비활성과 동일), 텍스트/아이콘: White (흰색 복구)
        return (
          <Button {...baseProps} className={`${baseProps.className} bg-[#1C1D21] text-white border-none cursor-wait`}>
            <Loader2 className="w-5 h-5 animate-spin" />
          </Button>
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
      options: ['default', 'completed', 'loading'],
      description: '상태 선택',
    },
  },
  render: (args) => {
    const status = (args as any).status;
    const smallBase = "text-[14px] font-normal rounded-[9px] w-[100px] h-[38px] flex items-center justify-center transition-colors whitespace-nowrap";
    
    if (status === 'default') {
      return <Button className={`${smallBase} bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white`}>인증 확인</Button>;
    }
    
    if (status === 'completed') {
      return (
        <Button className={`${smallBase} bg-[#1C1D21] text-[#5F616B] cursor-not-allowed`}>
          인증 완료
        </Button>
      );
    }
    
    if (status === 'loading') {
       return <Button className={`${smallBase} bg-[#6D4AE6] text-white`}><Loader2 className="w-5 h-5 animate-spin" /></Button>;
    }
    return <></>;;
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
      description: '재전송 여부',
    },
  },
  render: ({ isResend }) => (
    <Button 
      className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] font-normal rounded-[9px] w-[121px] h-[38px] whitespace-nowrap"
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
      <Button variant="google" size="icon" className="w-[56px] h-[56px] p-0 rounded-full bg-white">
        <GoogleIcon className="w-[40px] h-[40px]" />
      </Button>
      <Button variant="kakao" size="icon" className="w-[56px] h-[56px] p-0 rounded-full bg-[#FEE500]">
        <KakaoIcon className="w-[40px] h-[40px]" />
      </Button>
    </div>
  ),
};