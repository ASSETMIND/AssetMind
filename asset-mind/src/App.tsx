// src/App.tsx
import { useState } from 'react';
import { GoogleIcon } from './components/icons/GoogleIcon';
import { KakaoIcon } from './components/icons/KakaoIcon';
import { EyeIcon } from './components/icons/EyeIcon';

import { Modal } from './components/common/Modal';
import { Button } from './components/common/Button';
import { Input } from './components/common/Input';

function App() {
  const [isModalOpen, setIsModalOpen] = useState(true); // 모달 상태 관리
  const [showPassword, setShowPassword] = useState(false);
  const [userId, setUserId] = useState("");

  const isError = userId === 'error';

  return (
    <>
      {/* (테스트용) 모달이 닫혔을 때 여는 버튼 */}
      {!isModalOpen && (
        <div className="flex h-screen items-center justify-center">
          <Button onClick={() => setIsModalOpen(true)}>로그인 열기</Button>
        </div>
      )}

      {/* div 래퍼 대신 Modal 컴포넌트 사용 */}
      <Modal 
        isOpen={isModalOpen} 
        onClose={() => setIsModalOpen(false)}
      >
        {/* 1. 헤더 영역 */}
        <div className="text-center mb-10">
          <h1 className="text-h1 text-text-primary mb-2">LOGIN</h1>
          <p className="text-t1 text-text-secondary">AssetMind에 오신 것을 환영합니다.</p>
        </div>

        {/* 2. 폼 영역 */}
        <div className="flex flex-col gap-6">
          <Input 
            label="아이디"
            placeholder="아이디를 입력해 주세요."
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            error={isError ? "존재하지 않는 아이디 입니다." : undefined}
          />

          <Input 
            label="비밀번호"
            type={showPassword ? "text" : "password"}
            placeholder="비밀번호를 입력해 주세요."
            icon={<EyeIcon isOpen={!showPassword} className="w-5 h-5" />}
            onIconClick={() => setShowPassword(!showPassword)}
          />

          <Button fullWidth size="lg" className="mt-2 py-4">
            로그인
          </Button>

          <div className="flex justify-center items-center gap-4 text-l4 text-text-secondary mt-2">
            <button className="hover:text-text-primary transition-colors">아이디 찾기</button>
            <span className="w-[1px] h-3 bg-border-divider"></span>
            <button className="hover:text-text-primary transition-colors">비밀번호 찾기</button>
            <span className="w-[1px] h-3 bg-border-divider"></span>
            <button className="hover:text-text-primary transition-colors">회원가입</button>
          </div>

          <div className="relative flex items-center justify-center my-2">
            <div className="absolute w-full h-[1px] bg-border-divider"></div>
            <span className="relative px-4 bg-background-surface text-l4 text-text-secondary">or continue with</span>
          </div>

          <div className="flex justify-center gap-4">
            <Button variant="google" size="icon">
              <GoogleIcon className="w-10 h-10" />
            </Button>
            
            <Button variant="kakao" size="icon">
              <KakaoIcon className="w-10 h-10 text-social-kakao-icon" />
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}

export default App;