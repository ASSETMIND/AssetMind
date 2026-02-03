import { useState } from 'react';
import { LoginModal } from './components/auth/LoginModal';
import { SignUpModal } from './components/auth/SignUpModal'; // 방금 만든 파일
import { Button } from './components/common/Button';
import { useToast } from './context/ToastContext';

// 화면 상태 타입 정의
type AuthView = 'none' | 'login' | 'signup';

function App() {
  const [currentView, setCurrentView] = useState<AuthView>('login'); // 기본값: 로그인 모달
  const { showToast } = useToast();

  const handleLogin = (id: string, pw: string) => {
    if (id === 'fail') {
      showToast('LOGIN_FAIL');
      return;
    }
    console.log('로그인 성공:', id);
    setCurrentView('none'); // 성공 시 모달 닫기
  };

  return (
    <>
      <div className="flex h-screen items-center justify-center bg-background-primary gap-4">
        {/* 모달이 닫혀있을 때 여는 버튼들 */}
        {currentView === 'none' && (
          <>
            <Button onClick={() => setCurrentView('login')}>로그인 모달 열기</Button>
            <Button variant="secondary" onClick={() => setCurrentView('signup')}>회원가입 모달 열기</Button>
          </>
        )}
      </div>

      {/* 1. 로그인 모달 */}
      <LoginModal 
        isOpen={currentView === 'login'} 
        onClose={() => setCurrentView('none')} 
        onLogin={handleLogin}
        // 로그인 모달 안에 "회원가입" 버튼이 있다면 이 함수를 연결해줘야 함 (필요 시 LoginModal 수정)
      />

      {/* 2. 회원가입 모달 */}
      <SignUpModal 
        isOpen={currentView === 'signup'}
        onClose={() => setCurrentView('none')}
        onSwitchToLogin={() => setCurrentView('login')} // '로그인' 텍스트 클릭 시 전환
      />
    </>
  );
}

export default App;