import type { Meta, StoryObj } from '@storybook/react';
import { Modal } from './Modal';
import { Button } from './Button';
import { Input } from './Input';
import { useState, useRef, useEffect } from 'react';

const meta: Meta<typeof Modal> = {
  title: 'Components/Common/Modal',
  component: Modal,
  tags: ['autodocs'],
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
        component: '접근성 기능(Focus Trap, ESC 키, 백드롭 클릭)을 지원하는 모달 컴포넌트입니다. 버튼 클릭으로 열고 닫을 수 있으며, 중첩 사용도 가능합니다.',
      },
    },
  },
  argTypes: {
    isOpen: { table: { disable: true } },
    onClose: { table: { disable: true } },
    children: { table: { disable: true } },
    className: { table: { disable: true } },
    title: { table: { disable: true } },
    description: { table: { disable: true } },
  },
};

export default meta;
type Story = StoryObj<typeof Modal>;

// =============================================================================
// 1. 기본 모달 - 버튼 클릭으로 열고 닫기
// =============================================================================
export const Basic_Interaction: Story = {
  name: 'Basic - Open & Close',
  parameters: {
    docs: {
      description: {
        story: '버튼을 클릭하여 모달을 열고 닫을 수 있습니다. X 버튼, ESC 키, 백드롭 클릭으로 닫을 수 있습니다.',
      },
    },
  },
  render: () => {
    const [isOpen, setIsOpen] = useState(false);

    return (
      <div className="flex flex-col items-center gap-4">
        <Button
          variant="primary"
          size="lg"
          onClick={() => setIsOpen(true)}
          className="h-[52px] text-[16px] font-medium"
        >
          모달 열기
        </Button>

        <Modal
          isOpen={isOpen}
          onClose={() => setIsOpen(false)}
          title="기본 모달"
          description="모달의 내용을 여기에 표시합니다"
          className="w-[480px] bg-[#1C1D21] rounded-[40px] px-[40px] py-[50px]"
        >
          <div className="flex flex-col items-center gap-6">
            <h2 className="text-[28px] font-bold text-white">알림</h2>
            <p className="text-[16px] text-[#E5E5E5] text-center">
              이것은 기본 모달입니다.
              <br />
              X 버튼, ESC 키, 또는 바깥 영역을 클릭하여 닫을 수 있습니다.
            </p>
            <Button
              variant="primary"
              size="lg"
              fullWidth
              onClick={() => setIsOpen(false)}
              className="h-[52px] text-[16px] font-medium"
            >
              확인
            </Button>
          </div>
        </Modal>
      </div>
    );
  },
};

// =============================================================================
// 2. 중첩 모달 (Modal 위에 Modal)
// =============================================================================
export const Nested_Modals: Story = {
  name: 'Nested Modals',
  parameters: {
    docs: {
      description: {
        story: '모달 위에 또 다른 모달을 띄울 수 있습니다. 각 모달은 독립적으로 열고 닫을 수 있습니다.',
      },
    },
  },
  render: () => {
    const [isFirstOpen, setIsFirstOpen] = useState(false);
    const [isSecondOpen, setIsSecondOpen] = useState(false);

    return (
      <div className="flex flex-col items-center gap-4">
        <Button
          variant="primary"
          size="lg"
          onClick={() => setIsFirstOpen(true)}
          className="h-[52px] text-[16px] font-medium"
        >
          첫 번째 모달 열기
        </Button>

        {/* 첫 번째 모달 */}
        <Modal
          isOpen={isFirstOpen}
          onClose={() => setIsFirstOpen(false)}
          title="첫 번째 모달"
          description="두 번째 모달을 열 수 있습니다"
          className="w-[480px] bg-[#1C1D21] rounded-[40px] px-[40px] py-[50px]"
        >
          <div className="flex flex-col items-center gap-6">
            <h2 className="text-[28px] font-bold text-white">첫 번째 모달</h2>
            <p className="text-[16px] text-[#E5E5E5] text-center">
              이 모달 위에 또 다른 모달을 띄울 수 있습니다.
            </p>
            <Button
              variant="primary"
              size="lg"
              fullWidth
              onClick={() => setIsSecondOpen(true)}
              className="h-[52px] text-[16px] font-medium"
            >
              두 번째 모달 열기
            </Button>
          </div>
        </Modal>

        {/* 두 번째 모달 (중첩) */}
        <Modal
          isOpen={isSecondOpen}
          onClose={() => setIsSecondOpen(false)}
          title="두 번째 모달"
          description="중첩된 모달입니다"
          className="w-[400px] bg-[#1C1D21] rounded-[40px] px-[40px] py-[50px]"
        >
          <div className="flex flex-col items-center gap-6">
            <h2 className="text-[24px] font-bold text-white">두 번째 모달</h2>
            <p className="text-[14px] text-[#E5E5E5] text-center">
              이것은 중첩된 모달입니다.
              <br />
              이 모달을 닫아도 첫 번째 모달은 유지됩니다.
            </p>
            <Button
              variant="primary"
              size="lg"
              fullWidth
              onClick={() => setIsSecondOpen(false)}
              className="h-[52px] text-[16px] font-medium"
            >
              닫기
            </Button>
          </div>
        </Modal>
      </div>
    );
  },
};

// =============================================================================
// 3. 접근성 데모 - 키보드 탐색
// =============================================================================
export const Accessibility_Demo: Story = {
  name: 'Accessibility - Keyboard Navigation',
  parameters: {
    docs: {
      description: {
        story: 'Tab 키로 모달 내 요소들을 탐색할 수 있습니다. ESC 키로 모달을 닫을 수 있습니다. Focus Trap이 적용되어 있어 모달이 열리면 포커스가 모달 내부에만 머무릅니다.',
      },
    },
  },
  render: () => {
    const [isOpen, setIsOpen] = useState(false);
    const [focusedElement, setFocusedElement] = useState<string>('');
    const button1Ref = useRef<HTMLButtonElement>(null);

    // 모달이 열릴 때 첫 번째 버튼으로 포커스 이동
    useEffect(() => {
      if (isOpen && button1Ref.current) {
        // 모달이 열릴 때만 수동으로 포커스 이동 (리렌더링 유발 X)
        const timer = setTimeout(() => {
          button1Ref.current?.focus();
        }, 100);
        return () => clearTimeout(timer);
      }
    }, [isOpen]);

    return (
      <div className="flex flex-col items-center gap-4">
        <p className="text-[14px] text-[#E5E5E5] text-center mb-2">
          Tab 키로 모달 내 요소 탐색, ESC 키로 닫기
        </p>

        <Button
          variant="primary"
          size="lg"
          onClick={() => setIsOpen(true)}
          className="h-[52px] text-[16px] font-medium"
        >
          접근성 데모 열기
        </Button>

        <Modal
          isOpen={isOpen}
          onClose={() => setIsOpen(false)}
          title="접근성 데모"
          description="키보드로 탐색 가능한 모달입니다"
          className="w-[480px] bg-[#1C1D21] rounded-[40px] px-[40px] py-[50px]"
        >
          <div className="flex flex-col gap-6">
            <h2 className="text-[28px] font-bold text-white text-center">키보드 탐색</h2>
            
            <div className="flex flex-col gap-3">
              <Button
                ref={button1Ref}
                variant="primary"
                size="lg"
                fullWidth
                onClick={() => console.log('버튼 1 클릭')} 
                // onFocus 제거
                className="h-[52px] text-[16px] font-medium"
              >
                버튼 1
              </Button>
              
              <Button
                variant="primary"
                size="lg"
                fullWidth
                onClick={() => console.log('버튼 2 클릭')}
                className="h-[52px] text-[16px] font-medium"
              >
                버튼 2
              </Button>
              
              <Button
                variant="primary"
                size="lg"
                fullWidth
                onClick={() => console.log('버튼 3 클릭')}
                className="h-[52px] text-[16px] font-medium"
              >
                버튼 3
              </Button>
            </div>

            {focusedElement && (
              <p className="text-[14px] text-white text-center mt-2">
                현재 포커스: {focusedElement}
              </p>
            )}

            <Button
              variant="secondary"
              size="lg"
              fullWidth
              onClick={() => setIsOpen(false)}
              className="h-[52px] text-[16px] font-medium bg-[#2E2F33] text-white hover:bg-[#3E3F43] mt-2"
            >
              닫기 (또는 ESC 키)
            </Button>
          </div>
        </Modal>
      </div>
    );
  },
};