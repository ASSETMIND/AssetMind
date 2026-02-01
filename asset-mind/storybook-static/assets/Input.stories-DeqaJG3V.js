import{i as e}from"./iframe-CjPFHwle.js";import{t}from"./jsx-runtime-DHv4dh-F.js";import{t as n}from"./utils-CCOIPmdI.js";var r=e(),i=t();const a=(0,r.forwardRef)(({className:e,label:t,error:r,message:a,state:o=`default`,icon:s,onIconClick:c,rightSection:l,rightSectionWidth:u=`pr-[50px]`,...d},f)=>{let p=r?`error`:o,m=r||a;return(0,i.jsxs)(`div`,{className:`w-full flex flex-col gap-2`,children:[t&&(0,i.jsx)(`label`,{className:`text-l2 font-normal text-text-primary`,children:t}),(0,i.jsxs)(`div`,{className:`relative`,children:[(0,i.jsx)(`input`,{ref:f,className:n(`w-full h-[57px] px-[25px] rounded-lg border outline-none transition-all duration-200`,`text-[14px] leading-[150%] font-normal`,`text-text-primary placeholder:text-text-placeholder`,`bg-[#1C1D21] border-border-inputNormal`,`focus:border-border-inputFocus focus:bg-[#1C1D21]`,(s||l)&&u,p===`error`&&`border-border-inputError focus:border-border-inputError text-text-error placeholder:text-text-error/50`,p===`success`&&`border-border-inputSuccess focus:border-border-inputSuccess`,e),...d}),s&&!l&&(0,i.jsx)(`button`,{type:`button`,onClick:c,className:`absolute right-[20px] top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary flex items-center justify-center`,children:s}),l&&(0,i.jsx)(`div`,{className:`absolute right-[10px] top-1/2 -translate-y-1/2`,children:l})]}),m&&(0,i.jsx)(`p`,{className:n(`text-l4 mt-1`,p===`error`?`text-text-error`:p===`success`?`text-text-success`:`text-text-secondary`),children:m})]})});a.displayName=`Input`,a.__docgenInfo={description:``,methods:[],displayName:`Input`,props:{label:{required:!1,tsType:{name:`string`},description:``},error:{required:!1,tsType:{name:`string`},description:``},message:{required:!1,tsType:{name:`string`},description:``},state:{required:!1,tsType:{name:`union`,raw:`'default' | 'error' | 'success'`,elements:[{name:`literal`,value:`'default'`},{name:`literal`,value:`'error'`},{name:`literal`,value:`'success'`}]},description:``,defaultValue:{value:`'default'`,computed:!1}},icon:{required:!1,tsType:{name:`ReactNode`},description:``},onIconClick:{required:!1,tsType:{name:`signature`,type:`function`,raw:`() => void`,signature:{arguments:[],return:{name:`void`}}},description:``},rightSection:{required:!1,tsType:{name:`ReactNode`},description:``},rightSectionWidth:{required:!1,tsType:{name:`string`},description:``,defaultValue:{value:`"pr-[50px]"`,computed:!1}}},composes:[`InputHTMLAttributes`]};const o=({className:e=`w-6 h-6`,isOpen:t})=>t?(0,i.jsx)(`svg`,{className:e,viewBox:`0 0 24 24`,fill:`none`,xmlns:`http://www.w3.org/2000/svg`,children:(0,i.jsx)(`path`,{d:`M12 16C13.25 16 14.3127 15.5627 15.188 14.688C16.0634 13.8133 16.5007 12.7507 16.5 11.5C16.4994 10.2493 16.062 9.187 15.188 8.313C14.314 7.439 13.2514 7.00133 12 7C10.7487 6.99867 9.68637 7.43633 8.81304 8.313C7.93971 9.18967 7.50204 10.252 7.50004 11.5C7.49804 12.748 7.93571 13.8107 8.81304 14.688C9.69037 15.5653 10.7527 16.0027 12 16ZM12 14.2C11.25 14.2 10.6127 13.9373 10.088 13.412C9.56337 12.8867 9.30071 12.2493 9.30004 11.5C9.29937 10.7507 9.56204 10.1133 10.088 9.588C10.614 9.06267 11.2514 8.8 12 8.8C12.7487 8.8 13.3864 9.06267 13.913 9.588C14.4397 10.1133 14.702 10.7507 14.7 11.5C14.698 12.2493 14.4357 12.887 13.913 13.413C13.3904 13.939 12.7527 14.2013 12 14.2ZM12 19C9.76671 19 7.72904 18.4 5.88704 17.2C4.04504 16 2.59104 14.4167 1.52504 12.45C1.44171 12.3 1.37937 12.146 1.33804 11.988C1.29671 11.83 1.27571 11.6673 1.27504 11.5C1.27437 11.3327 1.29537 11.17 1.33804 11.012C1.38071 10.854 1.44304 10.7 1.52504 10.55C2.59171 8.58333 4.04604 7 5.88804 5.8C7.73004 4.6 9.76737 4 12 4C14.2327 4 16.2704 4.6 18.113 5.8C19.9557 7 21.4097 8.58333 22.475 10.55C22.5584 10.7 22.621 10.8543 22.663 11.013C22.705 11.1717 22.7257 11.334 22.725 11.5C22.7244 11.666 22.7037 11.8287 22.663 11.988C22.6224 12.1473 22.5597 12.3013 22.475 12.45C21.4084 14.4167 19.9544 16 18.113 17.2C16.2717 18.4 14.234 19 12 19ZM12 17C13.8834 17 15.6127 16.5043 17.188 15.513C18.7634 14.5217 19.9674 13.184 20.8 11.5C19.9667 9.81667 18.7624 8.47933 17.187 7.488C15.6117 6.49667 13.8827 6.00067 12 6C10.1174 5.99933 8.38837 6.49533 6.81304 7.488C5.23771 8.48067 4.03337 9.818 3.20004 11.5C4.03337 13.1833 5.23771 14.521 6.81304 15.513C8.38837 16.505 10.1174 17.0007 12 17Z`,fill:`currentColor`})}):(0,i.jsxs)(`svg`,{className:e,viewBox:`0 0 24 24`,fill:`none`,xmlns:`http://www.w3.org/2000/svg`,children:[(0,i.jsxs)(`g`,{clipPath:`url(#clip0_39_57)`,children:[` `,(0,i.jsx)(`path`,{d:`M12 5.99995C13.8387 5.99384 15.6419 6.50673 17.2021 7.47968C18.7624 8.45262 20.0164 9.84611 20.82 11.5C20.2399 12.6947 19.4195 13.7569 18.41 14.62L19.82 16.03C21.21 14.8 22.31 13.26 23 11.5C21.27 7.10995 17 3.99995 12 3.99995C10.73 3.99995 9.51 4.19995 8.36 4.56995L10.01 6.21995C10.66 6.08995 11.32 5.99995 12 5.99995ZM10.93 7.13995L13 9.20995C13.57 9.45995 14.03 9.91995 14.28 10.49L16.35 12.56C16.43 12.22 16.49 11.86 16.49 11.49C16.5 9.00995 14.48 6.99995 12 6.99995C11.63 6.99995 11.28 7.04995 10.93 7.13995ZM2.01 3.86995L4.69 6.54995C3.04039 7.84118 1.76634 9.55028 1 11.5C2.73 15.89 7 19 12 19C13.52 19 14.98 18.71 16.32 18.18L19.74 21.6L21.15 20.19L3.42 2.44995L2.01 3.86995ZM9.51 11.37L12.12 13.98C12.08 13.99 12.04 14 12 14C11.337 14 10.7011 13.7366 10.2322 13.2677C9.76339 12.7989 9.5 12.163 9.5 11.5C9.5 11.45 9.51 11.42 9.51 11.37ZM6.11 7.96995L7.86 9.71995C7.62291 10.2835 7.50052 10.8886 7.5 11.5C7.5013 12.244 7.68677 12.9761 8.03987 13.631C8.39297 14.2859 8.90271 14.8432 9.52359 15.2532C10.1445 15.6631 10.8572 15.913 11.5982 15.9805C12.3391 16.048 13.0853 15.931 13.77 15.64L14.75 16.62C13.87 16.86 12.95 17 12 17C10.1613 17.0061 8.35813 16.4932 6.79788 15.5202C5.23763 14.5473 3.98362 13.1538 3.18 11.5C3.88 10.07 4.9 8.88995 6.11 7.96995Z`,fill:`currentColor`})]}),(0,i.jsx)(`defs`,{children:(0,i.jsx)(`clipPath`,{id:`clip0_39_57`,children:(0,i.jsx)(`rect`,{width:`24`,height:`24`,fill:`white`})})})]});o.__docgenInfo={description:``,methods:[],displayName:`EyeIcon`,props:{className:{required:!1,tsType:{name:`string`},description:``,defaultValue:{value:`"w-6 h-6"`,computed:!1}},isOpen:{required:!0,tsType:{name:`boolean`},description:``}}};var s={title:`UI_KIT/Input`,component:a,parameters:{layout:`centered`,backgrounds:{default:`surface`}},decorators:[e=>(0,i.jsx)(`div`,{style:{width:`451px`},children:(0,i.jsx)(e,{})})],argTypes:{state:{description:`인풋 상태 (default / error / success)`,control:`radio`,options:[`default`,`error`,`success`]},error:{description:`에러 메시지 (state가 error일 때 표시됨)`,control:`text`},value:{control:`text`},placeholder:{control:`text`},disabled:{control:`boolean`}}};const c={name:`로그인 - 아이디`,args:{label:`아이디`,placeholder:`아이디를 입력해 주세요.`,state:`default`,value:``}},l={name:`로그인 - 비밀번호`,args:{label:`비밀번호`,type:`password`,placeholder:`비밀번호를 입력해 주세요.`,icon:(0,i.jsx)(o,{isOpen:!1,className:`w-5 h-5`})}},u={name:`회원가입 - 아이디`,args:{label:`아이디`,placeholder:`영문 소문자, 숫자 포함 4~20자`,rightSection:(0,i.jsx)(`button`,{className:`bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] font-normal rounded-[9px] w-[100px] h-[38px] flex items-center justify-center transition-colors`,children:`중복 확인`}),rightSectionWidth:`pr-[115px]`}},d={name:`회원가입 - 비밀번호`,args:{label:`비밀번호`,type:`password`,placeholder:`영문, 숫자, 특수문자 포함 8자 이상`,icon:(0,i.jsx)(o,{isOpen:!1,className:`w-5 h-5`})}},f={name:`회원가입 - 휴대폰번호`,args:{label:`휴대폰 번호`,placeholder:`010-0000-0000`,rightSection:(0,i.jsx)(`button`,{className:`bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] font-normal rounded-[9px] w-[121px] h-[38px] flex items-center justify-center transition-colors`,children:`인증번호 전송`}),rightSectionWidth:`pr-[136px]`}},p={name:`회원가입 - 인증번호 입력`,args:{placeholder:`인증번호 입력`,rightSection:(0,i.jsx)(`button`,{className:`bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] font-normal rounded-[9px] w-[100px] h-[38px] flex items-center justify-center transition-colors`,children:`인증 확인`}),rightSectionWidth:`pr-[115px]`}};c.parameters={...c.parameters,docs:{...c.parameters?.docs,source:{originalSource:`{
  name: '로그인 - 아이디',
  args: {
    label: '아이디',
    placeholder: '아이디를 입력해 주세요.',
    state: 'default',
    value: ''
  }
}`,...c.parameters?.docs?.source}}},l.parameters={...l.parameters,docs:{...l.parameters?.docs,source:{originalSource:`{
  name: '로그인 - 비밀번호',
  args: {
    label: '비밀번호',
    type: 'password',
    placeholder: '비밀번호를 입력해 주세요.',
    icon: <EyeIcon isOpen={false} className="w-5 h-5" /> // 원본 아이콘 사이즈 유지
  }
}`,...l.parameters?.docs?.source}}},u.parameters={...u.parameters,docs:{...u.parameters?.docs,source:{originalSource:`{
  name: '회원가입 - 아이디',
  args: {
    label: '아이디',
    placeholder: '영문 소문자, 숫자 포함 4~20자',
    // 회원가입용 보라색 버튼 (중복 확인)
    rightSection: <button className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] font-normal rounded-[9px] w-[100px] h-[38px] flex items-center justify-center transition-colors">\r
        중복 확인\r
      </button>,
    rightSectionWidth: 'pr-[115px]'
  }
}`,...u.parameters?.docs?.source}}},d.parameters={...d.parameters,docs:{...d.parameters?.docs,source:{originalSource:`{
  name: '회원가입 - 비밀번호',
  args: {
    label: '비밀번호',
    type: 'password',
    placeholder: '영문, 숫자, 특수문자 포함 8자 이상',
    icon: <EyeIcon isOpen={false} className="w-5 h-5" />
  }
}`,...d.parameters?.docs?.source}}},f.parameters={...f.parameters,docs:{...f.parameters?.docs,source:{originalSource:`{
  name: '회원가입 - 휴대폰번호',
  args: {
    label: '휴대폰 번호',
    placeholder: '010-0000-0000',
    // 회원가입용 보라색 버튼 (인증번호 전송 - 너비 김)
    rightSection: <button className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] font-normal rounded-[9px] w-[121px] h-[38px] flex items-center justify-center transition-colors">\r
        인증번호 전송\r
      </button>,
    rightSectionWidth: 'pr-[136px]'
  }
}`,...f.parameters?.docs?.source}}},p.parameters={...p.parameters,docs:{...p.parameters?.docs,source:{originalSource:`{
  name: '회원가입 - 인증번호 입력',
  args: {
    // 라벨 없음
    placeholder: '인증번호 입력',
    // 회원가입용 보라색 버튼 (인증 확인)
    rightSection: <button className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] font-normal rounded-[9px] w-[100px] h-[38px] flex items-center justify-center transition-colors">\r
        인증 확인\r
      </button>,
    rightSectionWidth: 'pr-[115px]'
  }
}`,...p.parameters?.docs?.source}}};const m=[`Login_ID`,`Login_Password`,`Signup_ID`,`Signup_Password`,`Signup_Phone`,`Signup_AuthCode`];export{c as Login_ID,l as Login_Password,p as Signup_AuthCode,u as Signup_ID,d as Signup_Password,f as Signup_Phone,m as __namedExportsOrder,s as default};