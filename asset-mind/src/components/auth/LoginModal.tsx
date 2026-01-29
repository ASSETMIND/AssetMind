import { useState } from 'react';
import { Modal } from '../common/Modal';
import { Input } from '../common/Input';
import { Button } from '../common/Button';
import { EyeIcon } from '../icons/EyeIcon';
import { GoogleIcon } from '../icons/GoogleIcon';
import { KakaoIcon } from '../icons/KakaoIcon';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLogin: (id: string, pw: string) => void;
}

export const LoginModal = ({ isOpen, onClose, onLogin }: LoginModalProps) => {
  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // 에러 상태 시뮬레이션
  const isIdError = userId === 'error'; 

  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      {/* 1. Header Section */}
      <div className="text-center mb-10">
        {/* [복구] text-h1 클래스 원복 (index.css에 정의된 크기 적용) */}
        <h1 className="text-h1 text-text-primary mb-2">LOGIN</h1>
        <p className="text-t1 text-text-secondary">
          AssetMind에 오신 것을 환영합니다.
        </p>
      </div>

      {/* 2. Input Form Section */}
      <div className="flex flex-col gap-6">
        <Input
          label="아이디"
          placeholder="아이디를 입력해 주세요."
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          error={isIdError ? "존재하지 않는 아이디 입니다." : undefined}
        />

        <Input
          label="비밀번호"
          type={showPassword ? "text" : "password"}
          placeholder="비밀번호를 입력해 주세요."
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          icon={<EyeIcon isOpen={showPassword} className="w-5 h-5" />}
          onIconClick={() => setShowPassword(!showPassword)}
        />

        {/* 3. Main Action Button */}
        <Button
          fullWidth
          size="lg"
          className="mt-4" 
          onClick={() => onLogin(userId, password)}
        >
          로그인
        </Button>

        {/* 4. Footer Links */}
        <div className="flex justify-center items-center gap-4 mt-1">
          <FooterLink>아이디 찾기</FooterLink>
          <div className="w-[1px] h-3 bg-border-divider" />
          <FooterLink>비밀번호 찾기</FooterLink>
          <div className="w-[1px] h-3 bg-border-divider" />
          <FooterLink>회원가입</FooterLink>
        </div>

        {/* 5. Social Login Divider */}
        <div className="relative flex items-center justify-center mt-6 mb-2">
          <div className="absolute w-full h-[1px] bg-border-divider" />
          <span className="relative px-4 bg-background-surface text-l4 text-text-secondary">
            or continue with
          </span>
        </div>

        {/* 6. Social Buttons */}
        <div className="flex justify-center gap-4">
          <Button variant="google" size="icon">
            {/* [복구] 아이콘 크기 w-10 h-10 원복 (App.tsx 원본 참조) */}
            <GoogleIcon className="w-10 h-10" />
          </Button>
          <Button variant="kakao" size="icon">
             {/* [복구] 아이콘 크기 w-10 h-10 원복 */}
            <KakaoIcon className="w-10 h-10 text-social-kakao-icon" />
          </Button>
        </div>
      </div>
    </Modal>
  );
};

const FooterLink = ({ children }: { children: React.ReactNode }) => (
  <button className="text-l4 text-text-secondary hover:text-text-primary transition-colors">
    {children}
  </button>
);