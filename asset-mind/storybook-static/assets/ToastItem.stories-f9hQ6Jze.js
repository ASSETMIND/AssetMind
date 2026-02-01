import{j as t}from"./jsx-runtime-Dp2Q4Dqs.js";import{T as C}from"./ToastItem-D4bDgvb8.js";import"./iframe-DzVlXYYL.js";import"./preload-helper-Dp1pzeXC.js";import"./utils-fNskMoFt.js";const j={title:"UI_KIT/Toast/Design_Spec",component:C,parameters:{layout:"centered",controls:{disable:!0},actions:{disable:!0}},decorators:[x=>t.jsx("div",{className:"bg-background-primary p-10 flex flex-col gap-4",children:t.jsx(x,{})})]},e={args:{variant:"success",title:"비밀번호가 변경되었습니다.",message:"서비스 이용을 위해 다시 로그인해 주세요."}},r={args:{variant:"error",title:"인증에 실패했습니다.",message:"입력하신 정보가 정확한지 확인해 주세요."}},s={args:{variant:"error",title:"본인인증에 실패했습니다.",message:"잠시 후 다시 시도해주세요."}},a={args:{variant:"error",title:"로그인에 실패했습니다.",message:"잠시 후 다시 시도해주세요."}};var o,n,i;e.parameters={...e.parameters,docs:{...(o=e.parameters)==null?void 0:o.docs,source:{originalSource:`{
  args: {
    variant: 'success',
    title: '비밀번호가 변경되었습니다.',
    message: '서비스 이용을 위해 다시 로그인해 주세요.'
  }
}`,...(i=(n=e.parameters)==null?void 0:n.docs)==null?void 0:i.source}}};var c,m,p;r.parameters={...r.parameters,docs:{...(c=r.parameters)==null?void 0:c.docs,source:{originalSource:`{
  args: {
    variant: 'error',
    title: '인증에 실패했습니다.',
    message: '입력하신 정보가 정확한지 확인해 주세요.'
  }
}`,...(p=(m=r.parameters)==null?void 0:m.docs)==null?void 0:p.source}}};var l,d,g;s.parameters={...s.parameters,docs:{...(l=s.parameters)==null?void 0:l.docs,source:{originalSource:`{
  args: {
    variant: 'error',
    title: '본인인증에 실패했습니다.',
    message: '잠시 후 다시 시도해주세요.'
  }
}`,...(g=(d=s.parameters)==null?void 0:d.docs)==null?void 0:g.source}}};var u,_,v;a.parameters={...a.parameters,docs:{...(u=a.parameters)==null?void 0:u.docs,source:{originalSource:`{
  args: {
    variant: 'error',
    title: '로그인에 실패했습니다.',
    message: '잠시 후 다시 시도해주세요.'
  }
}`,...(v=(_=a.parameters)==null?void 0:_.docs)==null?void 0:v.source}}};const y=["Case1_Password_Success","Case2_Verification_Fail","Case3_Identity_Fail","Case4_Login_Fail"];export{e as Case1_Password_Success,r as Case2_Verification_Fail,s as Case3_Identity_Fail,a as Case4_Login_Fail,y as __namedExportsOrder,j as default};
