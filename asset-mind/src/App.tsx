function App() {
  return (
    <div className="modal-overlay">
      <div className="modal-container">
        
        <button className="absolute top-6 right-6 text-text-secondary hover:text-text-primary">
          ✕
        </button>

        <div className="text-center mb-10">
          {/* H1: 24px(M) -> 32px(T) -> 48px(D) */}
          <h1 className="text-h1 text-text-primary mb-2">LOGIN</h1>
          
          {/* T1: 14px(M) -> 16px(T) -> 20px(D) */}
          <p className="text-t1 text-text-secondary">AssetMind에 오신 것을 환영합니다.</p>
        </div>

        {/* ... (아래 폼 영역은 그대로 유지) ... */}
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-2">
            <label className="text-l2 text-text-secondary">아이디</label>
            <div className="relative">
              <input 
                type="text" 
                className="input-base input-error" 
                placeholder="아이디를 입력해 주세요."
                defaultValue="잘못된 아이디" 
              />
              <div className="absolute right-4 top-1/2 -translate-y-1/2 text-text-secondary cursor-pointer">👁️</div>
            </div>
            <p className="text-l4 text-text-error">존재하지 않는 아이디 입니다.</p>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-l2 text-text-secondary">비밀번호</label>
            <div className="relative">
              <input 
                type="password" 
                className="input-base" 
                placeholder="비밀번호를 입력해 주세요." 
              />
              <div className="absolute right-4 top-1/2 -translate-y-1/2 text-text-secondary cursor-pointer">👁️</div>
            </div>
          </div>

          <button className="btn-full py-4 mt-2 bg-button-large-primary hover:bg-button-large-primaryHover text-button-large-label">
            로그인
          </button>

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

          <div className="flex justify-center gap-4">
            <button className="w-12 h-12 rounded-full bg-social-google-bg flex items-center justify-center">G</button>
            <button className="w-12 h-12 rounded-full bg-social-kakao-bg flex items-center justify-center text-social-kakao-icon">K</button>
          </div>

        </div>
      </div>
    </div>
  )
}

export default App