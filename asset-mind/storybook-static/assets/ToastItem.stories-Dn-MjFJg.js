import{t as e}from"./jsx-runtime-DHv4dh-F.js";import"./utils-CCOIPmdI.js";import{t}from"./ToastItem-BuRKvZ_F.js";var n=e(),r={title:`UI_KIT/Toast/Design_Spec`,component:t,parameters:{layout:`centered`,controls:{disable:!0},actions:{disable:!0}},decorators:[e=>(0,n.jsx)(`div`,{className:`bg-background-primary p-10 flex flex-col gap-4`,children:(0,n.jsx)(e,{})})]};const i={args:{variant:`success`,title:`비밀번호가 변경되었습니다.`,message:`서비스 이용을 위해 다시 로그인해 주세요.`}},a={args:{variant:`error`,title:`인증에 실패했습니다.`,message:`입력하신 정보가 정확한지 확인해 주세요.`}},o={args:{variant:`error`,title:`본인인증에 실패했습니다.`,message:`잠시 후 다시 시도해주세요.`}},s={args:{variant:`error`,title:`로그인에 실패했습니다.`,message:`잠시 후 다시 시도해주세요.`}};i.parameters={...i.parameters,docs:{...i.parameters?.docs,source:{originalSource:`{
  args: {
    variant: 'success',
    title: '비밀번호가 변경되었습니다.',
    message: '서비스 이용을 위해 다시 로그인해 주세요.'
  }
}`,...i.parameters?.docs?.source}}},a.parameters={...a.parameters,docs:{...a.parameters?.docs,source:{originalSource:`{
  args: {
    variant: 'error',
    title: '인증에 실패했습니다.',
    message: '입력하신 정보가 정확한지 확인해 주세요.'
  }
}`,...a.parameters?.docs?.source}}},o.parameters={...o.parameters,docs:{...o.parameters?.docs,source:{originalSource:`{
  args: {
    variant: 'error',
    title: '본인인증에 실패했습니다.',
    message: '잠시 후 다시 시도해주세요.'
  }
}`,...o.parameters?.docs?.source}}},s.parameters={...s.parameters,docs:{...s.parameters?.docs,source:{originalSource:`{
  args: {
    variant: 'error',
    title: '로그인에 실패했습니다.',
    message: '잠시 후 다시 시도해주세요.'
  }
}`,...s.parameters?.docs?.source}}};const c=[`Case1_Password_Success`,`Case2_Verification_Fail`,`Case3_Identity_Fail`,`Case4_Login_Fail`];export{i as Case1_Password_Success,a as Case2_Verification_Fail,o as Case3_Identity_Fail,s as Case4_Login_Fail,c as __namedExportsOrder,r as default};