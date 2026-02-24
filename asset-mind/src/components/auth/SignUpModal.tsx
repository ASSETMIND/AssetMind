import { useState } from "react";
import { X } from "lucide-react";
import { Button } from "../common/Button";
import { Input } from "../common/Input";
import { EyeIcon } from "../icons/EyeIcon";

interface SignUpModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSwitchToLogin: () => void;
}

export const SignUpModal = ({ isOpen, onClose, onSwitchToLogin }: SignUpModalProps) => {
  const [showPw, setShowPw] = useState(false);
  const [showPwCheck, setShowPwCheck] = useState(false);

  const [formData, setFormData] = useState({
    id: "",
    password: "",
    passwordCheck: "",
    phone: "",
    authCode: "",
  });

  if (!isOpen) return null;

  const purpleBtnBase = "bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-l3 rounded-[9px] flex items-center justify-center transition-colors";
  const eyeIconSize = "w-6 h-6";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="relative w-[480px] bg-[#1C1D21] rounded-[40px] px-[40px] py-[50px] shadow-2xl animate-in fade-in zoom-in-95 duration-200">
        
        <button onClick={onClose} className="absolute top-6 right-6 text-text-secondary hover:text-white transition-colors">
          <X size={24} />
        </button>

        <h2 className="text-h1 text-center text-white mb-[40px]">
          SIGN UP
        </h2>

        <div className="flex flex-col gap-5">
          <Input 
            label="아이디"
            placeholder="영문 소문자, 숫자 포함 4~20자"
            value={formData.id}
            onChange={(e) => setFormData({...formData, id: e.target.value})}
            rightSection={
              <button className={`${purpleBtnBase} w-[100px] h-[38px]`}>
                중복 확인
              </button>
            }
            rightSectionWidth="pr-[115px]"
          />

          <Input 
            label="비밀번호"
            type={showPw ? "text" : "password"}
            placeholder="영문, 숫자, 특수문자 포함 8자 이상"
            value={formData.password}
            onChange={(e) => setFormData({...formData, password: e.target.value})}
            icon={<EyeIcon isOpen={showPw} className={eyeIconSize} />}
            onIconClick={() => setShowPw(!showPw)}
          />

          <Input 
            label="비밀번호 확인"
            type={showPwCheck ? "text" : "password"}
            placeholder="비밀번호를 한 번 더 입력해 주세요."
            value={formData.passwordCheck}
            onChange={(e) => setFormData({...formData, passwordCheck: e.target.value})}
            icon={<EyeIcon isOpen={showPwCheck} className={eyeIconSize} />}
            onIconClick={() => setShowPwCheck(!showPwCheck)}
          />

          <Input 
            label="휴대폰 번호"
            placeholder="010-0000-0000"
            value={formData.phone}
            onChange={(e) => setFormData({...formData, phone: e.target.value})}
            rightSection={
              <button className={`${purpleBtnBase} w-[121px] h-[38px]`}>
                인증번호 전송
              </button>
            }
            rightSectionWidth="pr-[136px]"
          />

          <Input 
            placeholder="인증번호 입력"
            value={formData.authCode}
            onChange={(e) => setFormData({...formData, authCode: e.target.value})}
            rightSection={
              <button className={`${purpleBtnBase} w-[100px] h-[38px]`}>
                인증 확인
              </button>
            }
            rightSectionWidth="pr-[115px]"
          />

          <Button 
            variant="primary" 
            size="lg" 
            fullWidth 
            className="mt-4"
          >
            가입하기
          </Button>

          <div className="flex items-center justify-center gap-2 mt-2">
            <span className="text-text-secondary text-[14px]">이미 계정이 있으신가요?</span>
            <button 
              onClick={onSwitchToLogin}
              className="text-white text-[14px] font-medium hover:underline"
            >
              로그인
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};