import type { Meta, StoryObj } from '@storybook/react';
import { Input } from './Input';
import { EyeIcon } from '../icons/EyeIcon';

const meta: Meta<typeof Input> = {
  title: 'UI_KIT/Input',
  component: Input,
  parameters: {
    layout: 'centered',
    backgrounds: { default: 'surface' },
    controls: { disable: true },
    actions: { disable: true },
  },
  // 인풋도 451px 너비 기준
  decorators: [
    (Story) => (
      <div style={{ width: '451px' }}>
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof Input>;

// 1. 기본 상태
export const Default: Story = {
  args: {
    label: '아이디',
    placeholder: '아이디를 입력해 주세요.',
  },
};

// 2. 에러 상태
export const With_Error: Story = {
  args: {
    label: '아이디',
    value: 'wrong_id',
    error: '존재하지 않는 아이디 입니다.',
    placeholder: '아이디를 입력해 주세요.',
  },
};

// 3. 비밀번호
export const Password: Story = {
  args: {
    label: '비밀번호',
    type: 'password',
    placeholder: '비밀번호를 입력해 주세요.',
    icon: <EyeIcon isOpen={false} className="w-5 h-5" />,
  },
};