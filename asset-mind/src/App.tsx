import { useState } from 'react';
import { LoginModal } from './components/auth/LoginModal';
import { Button } from './components/common/Button';
import { useToast } from './context/ToastContext';

function App() {
  const [isModalOpen, setIsModalOpen] = useState(true);
  
  // 1. Hook 가져오기
  const { showToast } = useToast();

  const handleLogin = (id: string, pw: string) => {
    // 2. [로그인 실패 시나리오 예시]
    // 아이디에 'fail'이라고 입력하면 '로그인 실패' 토스트를 띄웁니다.
    if (id === 'fail') {
      // [핵심 변경점] 이제 'LOGIN_FAIL'만 넣으면, 아까 설정한 문구가 자동으로 뜹니다.
      showToast('LOGIN_FAIL');
      return;
    }

    // 3. 성공 시 처리 (모달 닫기 등)
    console.log('로그인 성공:', id);
    setIsModalOpen(false);
  };

  return (
    <>
      <div className="flex h-screen items-center justify-center bg-background-primary">
        {!isModalOpen && (
          <Button onClick={() => setIsModalOpen(true)}>로그인 모달 열기</Button>
        )}
      </div>

      <LoginModal 
        isOpen={isModalOpen} 
        onClose={() => setIsModalOpen(false)} 
        onLogin={handleLogin}
      />
    </>
  );
}

export default App;