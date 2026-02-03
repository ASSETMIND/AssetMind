// src/main.tsx (프로젝트 구조에 따라 index.tsx일 수 있음)
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import { ToastProvider } from './context/ToastContext' // 추가

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {/* App을 ToastProvider로 감싸줍니다 */}
    <ToastProvider> 
      <App />
    </ToastProvider>
  </React.StrictMode>,
)