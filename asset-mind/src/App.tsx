import { useState } from 'react';
import { GoogleIcon } from './components/icons/GoogleIcon';
import { KakaoIcon } from './components/icons/KakaoIcon';
import { EyeIcon } from './components/icons/EyeIcon';
import { X } from 'lucide-react'; 

import { Button } from './components/common/Button';
import { Input } from './components/common/Input';

function App() {
  const [showPassword, setShowPassword] = useState(false);
  const [userId, setUserId] = useState(""); // [수정] 빈 값으로 초기화

  // 테스트용: 아이디가 'error'일 때만 에러 메시지 출력 (필요 없으면 삭제 가능)
  const isError = userId === 'error';

  return (
    <div className="modal-overlay">
      <div className="modal-container">
        
        <button className="absolute top-6 right-6 text-text-secondary hover:text-text-primary">
          <X className="w-6 h-6" />
        </button>

        <div className="text-center mb-10">
          <h1 className="text-h1 text-text-primary mb-2">LOGIN</h1>
          <p className="text-t1 text-text-secondary">AssetMind에 오신 것을 환영합니다.</p>
        </div>

        <div className="flex flex-col gap-6">
          
          {/* 아이디 입력창 */}
          <Input 
            label="아이디"
            placeholder="아이디를 입력해 주세요."
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            // [수정] 강제 에러 삭제. 'error'라고 입력할 때만 뜨도록 조건부 처리
            error={isError ? "존재하지 않는 아이디 입니다." : undefined}
          />

          {/* 비밀번호 입력창 */}
          <Input 
            label="비밀번호"
            type={showPassword ? "text" : "password"}
            placeholder="비밀번호를 입력해 주세요."
            icon={<EyeIcon isOpen={!showPassword} className="w-5 h-5" />}
            onIconClick={() => setShowPassword(!showPassword)}
          />

          {/* 로그인 버튼 */}
          <Button fullWidth size="lg" className="mt-2 py-4">
            로그인
          </Button>

          <div className="flex justify-center items-center gap-4 text-l4 text-text-secondary mt-2">
            <button className="hover:text-text-primary">아이디 찾기</button>
            <span className="w-[1px] h-3 bg-border-divider"></span>
            <button className="hover:text-text-primary">비밀번호 찾기</button>
            <span className="w-[1px] h-3 bg-border-divider"></span>
            <button className="hover:text-text-primary">회원가입</button>
          </div>

          <div className="relative flex items-center justify-center my-2">
            <div className="absolute w-full h-[1px] bg-border-divider"></div>
            <span className="relative px-4 bg-background-surface text-l4 text-text-secondary">or continue with</span>
          </div>

          {/* 소셜 버튼 */}
          <div className="flex justify-center gap-4">
            <Button variant="google" size="icon">
              <GoogleIcon className="w-10 h-10" />
            </Button>
            
            <Button variant="kakao" size="icon">
              <KakaoIcon className="w-10 h-10 text-social-kakao-icon" />
            </Button>
          </div>
          
        </div>
      </div>
    </div>
  );
}

export default App;