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
      <button className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] font-normal rounded-[9px] w-[100px] h-[38px] flex items-center justify-center transition-colors">
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
      <button className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] font-normal rounded-[9px] w-[121px] h-[38px] flex items-center justify-center transition-colors">
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
      <button className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] font-normal rounded-[9px] w-[100px] h-[38px] flex items-center justify-center transition-colors">
        인증 확인
      </button>
    ),
    rightSectionWidth: 'pr-[115px]',
  },
};