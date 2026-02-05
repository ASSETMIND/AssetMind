import type { Meta, StoryObj } from '@storybook/react';
import { Input } from './Input';
import { EyeIcon } from '../icons/EyeIcon';
import { useState } from 'react';

const meta: Meta<typeof Input> = {
  title: 'UI_KIT/Input',
  component: Input,
  parameters: {
    layout: 'centered',
    backgrounds: { default: 'surface' },
    docs: {
      description: {
        component: '다양한 상태(default, error, success)를 지원하는 입력 필드 컴포넌트입니다. Label-Input 연결, 에러 메시지 스크린 리더 알림 등 접근성 기능이 포함되어 있습니다.',
      },
    },
  },
  decorators: [
    (Story) => (
      <div style={{ width: '451px' }}>
        <Story />
      </div>
    ),
  ],
  argTypes: {
    state: {
      description: '인풋 상태 (default / error / success)',
      control: 'radio',
      options: ['default', 'error', 'success'],
    },
    error: {
      description: '에러 메시지 (state가 error일 때 표시됨)',
      control: 'text',
    },
    value: { control: 'text' },
    placeholder: { control: 'text' },
    disabled: { control: 'boolean' },
  },
};

export default meta;
type Story = StoryObj<typeof Input>;

// Password Toggle 컴포넌트 (재사용 가능)
const PasswordInputWithToggle = (args: any) => {
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);

  return (
    <Input
      {...args}
      type={isPasswordVisible ? 'text' : 'password'}
      icon={
        <button
          type="button"
          onClick={() => setIsPasswordVisible(!isPasswordVisible)}
          className="cursor-pointer"
          aria-label={isPasswordVisible ? "비밀번호 숨기기" : "비밀번호 보기"}
        >
          <EyeIcon isOpen={isPasswordVisible} className="w-5 h-5" />
        </button>
      }
    />
  );
};

// =============================================================================
// 1. 로그인 (Login) UI
// =============================================================================

export const Login_ID: Story = {
  name: 'Login - ID',
  args: {
    label: '아이디',
    placeholder: '아이디를 입력해 주세요.',
    state: 'default',
    value: '',
  },
};

export const Login_Password: Story = {
  name: 'Login - Password',
  render: (args) => <PasswordInputWithToggle {...args} />,
  args: {
    label: '비밀번호',
    placeholder: '비밀번호를 입력해 주세요.',
  },
};

// =============================================================================
// 2. 회원가입 (Sign Up) UI
// =============================================================================

export const Signup_ID: Story = {
  name: 'Signup - ID',
  args: {
    label: '아이디',
    placeholder: '영문 소문자, 숫자 포함 4~20자',
    rightSection: (
      <button 
        className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] font-normal rounded-[9px] w-[100px] h-[38px] flex items-center justify-center transition-colors"
        aria-label="아이디 중복 확인"
      >
        중복 확인
      </button>
    ),
    rightSectionWidth: 'pr-[115px]',
  },
};

export const Signup_Password: Story = {
  name: 'Signup - Password',
  render: (args) => <PasswordInputWithToggle {...args} />,
  args: {
    label: '비밀번호',
    placeholder: '영문, 숫자, 특수문자 포함 8자 이상',
  },
};

export const Signup_Phone: Story = {
  name: 'Signup - Phone Number',
  args: {
    label: '휴대폰 번호',
    placeholder: '010-0000-0000',
    rightSection: (
      <button 
        className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] font-normal rounded-[9px] w-[121px] h-[38px] flex items-center justify-center transition-colors"
        aria-label="인증번호 전송"
      >
        인증번호 전송
      </button>
    ),
    rightSectionWidth: 'pr-[136px]',
  },
};

export const Signup_AuthCode: Story = {
  name: 'Signup - Auth Code',
  args: {
    placeholder: '인증번호 입력',
    rightSection: (
      <button 
        className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] font-normal rounded-[9px] w-[100px] h-[38px] flex items-center justify-center transition-colors"
        aria-label="인증번호 확인"
      >
        인증 확인
      </button>
    ),
    rightSectionWidth: 'pr-[115px]',
  },
};

// =============================================================================
// 3. 인터랙티브 예제 - 아이디 중복 확인
// =============================================================================
export const Interactive_ID_Duplicate_Check: Story = {
  name: 'Interactive - ID Duplicate Check',
  parameters: {
    docs: {
      description: {
        story: '아이디 중복 확인 시나리오를 시연합니다. 4자 미만이면 에러, 4자 이상이면 성공 메시지가 표시됩니다.',
      },
    },
  },
  render: () => {
    const [id, setId] = useState('');
    const [state, setState] = useState<'default' | 'error' | 'success'>('default');
    const [message, setMessage] = useState('');
    const [isChecking, setIsChecking] = useState(false);

    const handleCheck = () => {
      setIsChecking(true);

      // 1초 후 결과 표시
      setTimeout(() => {
        if (id.length < 4) {
          setState('error');
          setMessage('중복된 아이디입니다.');
        } else {
          setState('success');
          setMessage('사용 가능한 아이디입니다.');
        }
        setIsChecking(false);
      }, 1000);
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      setId(e.target.value);
      setState('default');
      setMessage('');
    };

    return (
      <Input
        label="아이디"
        placeholder="영문 소문자, 숫자 포함 4~20자"
        value={id}
        onChange={handleChange}
        state={state}
        error={state === 'error' ? message : undefined}
        message={state === 'success' ? message : undefined}
        rightSection={
          <button
            onClick={handleCheck}
            disabled={!id || isChecking}
            className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] font-normal rounded-[9px] w-[100px] h-[38px] flex items-center justify-center transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="아이디 중복 확인"
          >
            {isChecking ? '확인 중...' : '중복 확인'}
          </button>
        }
        rightSectionWidth="pr-[115px]"
      />
    );
  },
};

// =============================================================================
// 4. 인터랙티브 예제 - 비밀번호 유효성 검증
// =============================================================================
export const Interactive_Password_Validation: Story = {
  name: 'Interactive - Password Validation',
  parameters: {
    docs: {
      description: {
        story: '비밀번호 유효성 검증을 실시간으로 확인합니다. 8자 미만이면 에러, 8자 이상이면 성공 상태로 표시됩니다.',
      },
    },
  },
  render: () => {
    const [password, setPassword] = useState('');
    const [isPasswordVisible, setIsPasswordVisible] = useState(false);
    const [state, setState] = useState<'default' | 'error' | 'success'>('default');
    const [message, setMessage] = useState('');

    const validatePassword = (value: string) => {
      if (!value) {
        setState('default');
        setMessage('');
        return;
      }

      if (value.length < 8) {
        setState('error');
        setMessage('비밀번호는 8자 이상이어야 합니다.');
      } else {
        const hasLetter = /[a-zA-Z]/.test(value);
        const hasNumber = /[0-9]/.test(value);
        const hasSpecial = /[!@#$%^&*]/.test(value);

        if (hasLetter && hasNumber && hasSpecial) {
          setState('success');
          setMessage('사용 가능한 비밀번호입니다.');
        } else {
          setState('error');
          setMessage('영문, 숫자, 특수문자를 모두 포함해야 합니다.');
        }
      }
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = e.target.value;
      setPassword(value);
      validatePassword(value);
    };

    return (
      <Input
        label="비밀번호"
        type={isPasswordVisible ? 'text' : 'password'}
        placeholder="영문, 숫자, 특수문자 포함 8자 이상"
        value={password}
        onChange={handleChange}
        state={state}
        error={state === 'error' ? message : undefined}
        message={state === 'success' ? message : undefined}
        icon={
          <button
            type="button"
            onClick={() => setIsPasswordVisible(!isPasswordVisible)}
            className="cursor-pointer"
            aria-label={isPasswordVisible ? "비밀번호 숨기기" : "비밀번호 보기"}
          >
            <EyeIcon isOpen={isPasswordVisible} className="w-5 h-5" />
          </button>
        }
      />
    );
  },
};

// =============================================================================
// 5. 인터랙티브 예제 - 휴대폰 인증 플로우
// =============================================================================
export const Interactive_Phone_Verification: Story = {
  name: 'Interactive - Phone Verification',
  parameters: {
    docs: {
      description: {
        story: '휴대폰 인증 전체 플로우를 시연합니다. 번호 입력 → 인증번호 전송 → 인증번호 입력 → 인증 완료',
      },
    },
  },
  render: () => {
    const [phone, setPhone] = useState('');
    const [authCode, setAuthCode] = useState('');
    const [isCodeSent, setIsCodeSent] = useState(false);
    const [isSending, setIsSending] = useState(false);
    const [isVerifying, setIsVerifying] = useState(false);
    const [isVerified, setIsVerified] = useState(false);
    const [authState, setAuthState] = useState<'default' | 'error' | 'success'>('default');
    const [authMessage, setAuthMessage] = useState('');

    const handleSendCode = () => {
      setIsSending(true);

      setTimeout(() => {
        setIsCodeSent(true);
        setIsSending(false);
      }, 1500);
    };

    const handleVerify = () => {
      setIsVerifying(true);

      setTimeout(() => {
        if (authCode.length >= 4) {
          setAuthState('success');
          setAuthMessage('인증이 완료되었습니다.');
          setIsVerified(true);
        } else {
          setAuthState('error');
          setAuthMessage('인증번호를 확인해주세요.');
        }
        setIsVerifying(false);
      }, 1500);
    };

    return (
      <div className="flex flex-col gap-4">
        {/* 휴대폰 번호 */}
        <Input
          label="휴대폰 번호"
          placeholder="010-0000-0000"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          disabled={isCodeSent}
          rightSection={
            <button
              onClick={handleSendCode}
              disabled={!phone || isCodeSent || isSending}
              className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] font-normal rounded-[9px] w-[121px] h-[38px] flex items-center justify-center transition-colors disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
              aria-label="인증번호 전송"
            >
              {isSending ? '전송 중...' : isCodeSent ? '전송 완료' : '인증번호 전송'}
            </button>
          }
          rightSectionWidth="pr-[136px]"
        />

        {/* 인증번호 입력 (전송 후 표시) */}
        {isCodeSent && !isVerified && (
          <Input
            placeholder="인증번호 입력"
            value={authCode}
            onChange={(e) => {
              setAuthCode(e.target.value);
              setAuthState('default');
              setAuthMessage('');
            }}
            state={authState}
            error={authState === 'error' ? authMessage : undefined}
            message={authState === 'success' ? authMessage : undefined}
            rightSection={
              <button
                onClick={handleVerify}
                disabled={!authCode || isVerifying || isVerified}
                className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] font-normal rounded-[9px] w-[100px] h-[38px] flex items-center justify-center transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="인증번호 확인"
              >
                {isVerifying ? '확인 중...' : '인증 확인'}
              </button>
            }
            rightSectionWidth="pr-[115px]"
          />
        )}
      </div>
    );
  },
};

// =============================================================================
// 6. 인터랙티브 예제 - 키보드 탐색 데모
// =============================================================================
export const Interactive_Keyboard_Navigation: Story = {
  name: 'Interactive - Keyboard Navigation',
  parameters: {
    docs: {
      description: {
        story: 'Tab 키로 Input 필드와 버튼을 탐색하고, Label을 클릭하면 Input에 포커스됩니다. 스크린 리더는 에러 메시지를 자동으로 읽어줍니다.',
      },
    },
  },
  render: () => {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [nameError, setNameError] = useState('');
    const [emailError, setEmailError] = useState('');

    const validateName = (value: string) => {
      if (value && value.length < 2) {
        setNameError('이름은 2자 이상 입력해주세요.');
      } else {
        setNameError('');
      }
    };

    const validateEmail = (value: string) => {
      if (value && !value.includes('@')) {
        setEmailError('올바른 이메일 형식이 아닙니다.');
      } else {
        setEmailError('');
      }
    };

    return (
      <div className="flex flex-col gap-4">
        <p className="text-[14px] text-text-secondary text-center mb-2">
          Tab 키로 이동, Label 클릭으로 Input 포커스
        </p>

        <Input
          label="이름"
          placeholder="이름을 입력하세요"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            validateName(e.target.value);
          }}
          onBlur={(e) => validateName(e.target.value)}
          error={nameError}
        />

        <Input
          label="이메일"
          type="email"
          placeholder="example@email.com"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            validateEmail(e.target.value);
          }}
          onBlur={(e) => validateEmail(e.target.value)}
          error={emailError}
        />
      </div>
    );
  },
};

// =============================================================================
// 7. Controls Playground (모든 Props 테스트)
// =============================================================================
export const Playground: Story = {
  name: 'Playground',
  parameters: {
    docs: {
      description: {
        story: 'Controls 패널에서 모든 props를 자유롭게 조작해보세요.',
      },
    },
  },
  args: {
    label: '라벨',
    placeholder: '입력해주세요',
    state: 'default',
    error: '',
    message: '',
    disabled: false,
  },
};
