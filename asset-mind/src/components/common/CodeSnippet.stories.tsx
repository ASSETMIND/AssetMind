import type { Meta, StoryObj } from '@storybook/react';
import { CodeSnippet } from './CodeSnippet';

const meta: Meta<typeof CodeSnippet> = {
  title: 'Components/Common/CodeSnippet',
  component: CodeSnippet,
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
        component: 'Syntax Highlighting과 원클릭 복사 기능을 제공하는 코드 스니펫 컴포넌트입니다. 개발자 문서나 예제 코드를 보여줄 때 사용합니다.',
      },
    },
  },
  decorators: [
    (Story) => (
      <div style={{ width: '800px', maxWidth: '100%' }}>
        <Story />
      </div>
    ),
  ],
  argTypes: {
    language: {
      control: 'select',
      options: ['javascript', 'typescript', 'jsx', 'tsx', 'css', 'html', 'bash', 'json'],
      description: '코드 언어',
    },
    showLineNumbers: {
      control: 'boolean',
      description: '라인 번호 표시 여부',
    },
  },
};

export default meta;
type Story = StoryObj<typeof CodeSnippet>;

// =============================================================================
// 1. TypeScript 예제
// =============================================================================
export const TypeScript_Example: Story = {
  name: 'TypeScript',
  args: {
    title: 'Button.tsx',
    language: 'typescript',
    code: `interface ButtonProps {
  variant: 'primary' | 'secondary';
  size: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
  onClick?: () => void;
}

export const Button = ({ 
  variant, 
  size, 
  children, 
  onClick 
}: ButtonProps) => {
  return (
    <button
      onClick={onClick}
      className={\`btn btn-\${variant} btn-\${size}\`}
    >
      {children}
    </button>
  );
};`,
  },
};

// =============================================================================
// 2. React (TSX) 예제
// =============================================================================
export const React_TSX_Example: Story = {
  name: 'React (TSX)',
  args: {
    title: 'LoginModal.tsx',
    language: 'tsx',
    code: `import { useState } from 'react';
import { Modal } from './Modal';
import { Input } from './Input';
import { Button } from './Button';

export const LoginModal = ({ isOpen, onClose }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = () => {
    console.log('로그인:', { email, password });
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <h2>로그인</h2>
      <Input 
        label="이메일"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <Input 
        label="비밀번호"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <Button onClick={handleSubmit}>로그인</Button>
    </Modal>
  );
};`,
  },
};

// =============================================================================
// 3. CSS 예제
// =============================================================================
export const CSS_Example: Story = {
  name: 'CSS',
  args: {
    title: 'styles.css',
    language: 'css',
    code: `.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.button-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.button-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.button-secondary {
  background: #2E2F33;
  color: #E5E5E5;
  border: 1px solid #3E3F43;
}`,
  },
};

// =============================================================================
// 4. Bash 명령어 예제
// =============================================================================
export const Bash_Example: Story = {
  name: 'Bash',
  args: {
    title: 'installation.sh',
    language: 'bash',
    code: `# 프로젝트 설치
npm install

# Storybook 실행
npm run storybook

# 빌드
npm run build

# 테스트 실행
npm test`,
    showLineNumbers: false,
  },
};

// =============================================================================
// 5. JSON 예제
// =============================================================================
export const JSON_Example: Story = {
  name: 'JSON',
  args: {
    title: 'package.json',
    language: 'json',
    code: `{
  "name": "asset-mind",
  "version": "1.0.0",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "storybook": "storybook dev -p 6006"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@storybook/react": "^10.2.5",
    "typescript": "~5.9.3",
    "vite": "^6.0.11"
  }
}`,
  },
};

// =============================================================================
// 6. 라인 번호 없는 버전
// =============================================================================
export const Without_Line_Numbers: Story = {
  name: 'Without Line Numbers',
  args: {
    title: 'useToast.ts',
    language: 'typescript',
    showLineNumbers: false,
    code: `export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
};`,
  },
};

// =============================================================================
// 7. 인터랙티브 예제 - 다양한 언어 전환
// =============================================================================
export const Interactive_Language_Switch: Story = {
  name: 'Interactive - Language Switch',
  parameters: {
    docs: {
      description: {
        story: 'Controls 패널에서 언어를 변경하여 Syntax Highlighting을 확인할 수 있습니다.',
      },
    },
  },
  args: {
    title: 'example.tsx',
    language: 'tsx',
    code: `const greeting = "Hello, World!";
console.log(greeting);

function add(a: number, b: number): number {
  return a + b;
}

const result = add(5, 3);`,
  },
};

// =============================================================================
// 8. 긴 코드 예제
// =============================================================================
export const Long_Code_Example: Story = {
  name: 'Long Code Example',
  args: {
    title: 'Modal.tsx',
    language: 'tsx',
    code: `import { type ReactNode, useEffect, useRef, useCallback } from "react";
import { CloseIcon } from "../icons/CloseIcon";
import { cn } from "../../lib/utils";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
  className?: string;
  title?: string;
  description?: string;
}

export const Modal = ({ 
  isOpen, 
  onClose, 
  children, 
  className,
  title,
  description
}: ModalProps) => {
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  const handleEscapeKey = useCallback((event: KeyboardEvent) => {
    if (event.key === 'Escape') {
      onClose();
    }
  }, [onClose]);

  const handleTabKey = useCallback((event: KeyboardEvent) => {
    if (event.key !== 'Tab' || !modalRef.current) return;

    const focusableElements = modalRef.current.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled])'
    );

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    if (event.shiftKey) {
      if (document.activeElement === firstElement) {
        lastElement?.focus();
        event.preventDefault();
      }
    } else {
      if (document.activeElement === lastElement) {
        firstElement?.focus();
        event.preventDefault();
      }
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      previousFocusRef.current = document.activeElement as HTMLElement;
      document.body.style.overflow = 'hidden';
      
      setTimeout(() => {
        closeButtonRef.current?.focus();
      }, 0);

      document.addEventListener('keydown', handleEscapeKey);
      document.addEventListener('keydown', handleTabKey);
    } else {
      document.body.style.overflow = '';
      
      if (previousFocusRef.current) {
        previousFocusRef.current.focus();
      }

      document.removeEventListener('keydown', handleEscapeKey);
      document.removeEventListener('keydown', handleTabKey);
    }

    return () => {
      document.body.style.overflow = '';
      document.removeEventListener('keydown', handleEscapeKey);
      document.removeEventListener('keydown', handleTabKey);
    };
  }, [isOpen, handleEscapeKey, handleTabKey]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div 
        className="absolute inset-0 bg-transparent" 
        onClick={onClose} 
        aria-hidden="true" 
      />

      <div 
        ref={modalRef}
        className={cn("modal-container", className)}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? "modal-title" : undefined}
        aria-describedby={description ? "modal-description" : undefined}
      >
        <button
          ref={closeButtonRef}
          type="button"
          onClick={onClose}
          className="close-button"
          aria-label="모달 닫기"
        >
          <CloseIcon className="w-6 h-6" />
        </button>

        {title && (
          <h2 id="modal-title" className="sr-only">
            {title}
          </h2>
        )}
        {description && (
          <p id="modal-description" className="sr-only">
            {description}
          </p>
        )}

        {children}
      </div>
    </div>
  );
};`,
  },
};

// =============================================================================
// 9. Playground
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
    title: 'example.ts',
    language: 'typescript',
    showLineNumbers: true,
    code: `const greeting = "Hello, World!";
console.log(greeting);`,
  },
};