import { useState } from "react";
import { X } from "lucide-react";
import { Button } from "../common/Button";
import { Input } from "../common/Input";
import { EyeIcon } from "../icons/EyeIcon";
import { GoogleIcon } from "../icons/GoogleIcon";
import { KakaoIcon } from "../icons/KakaoIcon";

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLogin: (id: string, pw: string) => void;
}

export const LoginModal = ({ isOpen, onClose, onLogin }: LoginModalProps) => {
  const [showPw, setShowPw] = useState(false);
  const [id, setId] = useState("");
  const [pw, setPw] = useState("");

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background-overlay backdrop-blur-[2px]">
      {/* [수정] rounded-[24px] -> rounded-[40px] */}
      <div className="relative w-[480px] bg-[#1C1D21] rounded-[40px] px-[40px] py-[50px] shadow-2xl animate-in fade-in zoom-in-95 duration-200">
        
        <button 
          onClick={onClose} 
          className="absolute top-6 right-6 text-text-secondary hover:text-white transition-colors"
        >
          <X size={24} />
        </button>

        <div className="text-center mb-[40px]">
          <h2 className="text-h1 text-text-primary mb-2">LOGIN</h2>
          <p className="text-t1 text-text-primary">
            AssetMind에 오신 것을 환영합니다.
          </p>
        </div>

        <div className="flex flex-col gap-5">
          <Input 
            label="아이디"
            placeholder="아이디를 입력해 주세요."
            value={id}
            onChange={(e) => setId(e.target.value)}
          />

          <Input 
            label="비밀번호"
            type={showPw ? "text" : "password"}
            placeholder="비밀번호를 입력해 주세요."
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            icon={<EyeIcon isOpen={showPw} className="w-6 h-6" />}
            onIconClick={() => setShowPw(!showPw)}
          />

          <Button 
            variant="primary" 
            size="lg" 
            fullWidth 
            className="mt-4"
            onClick={() => onLogin(id, pw)}
          >
            로그인
          </Button>

          <div className="flex items-center justify-center gap-4 text-[13px] text-text-secondary">
            <button className="hover:text-text-primary">아이디 찾기</button>
            <div className="w-[1px] h-[12px] bg-border-divider"></div>
            <button className="hover:text-text-primary">비밀번호 찾기</button>
            <div className="w-[1px] h-[12px] bg-border-divider"></div>
            <button className="hover:text-text-primary">회원가입</button>
          </div>

          <div className="relative my-4">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-border-divider"></div>
            </div>
            <div className="relative flex justify-center text-[14px] text-text-secondary">
              <span className="bg-[#1C1D21] px-2">
                or continue with
              </span>
            </div>
          </div>

          <div className="flex flex-row items-center justify-center gap-4">
            <Button variant="google" size="icon" className="w-14 h-14 p-0">
              <GoogleIcon className="w-15 h-15" />
            </Button>
            <Button variant="kakao" size="icon" className="w-14 h-14 p-0">
              <KakaoIcon className="w-15 h-15" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};