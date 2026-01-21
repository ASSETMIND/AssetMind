import { useState } from 'react';
import * as PortOne from '@portone/browser-sdk/v2';
import Button from '../common/button';
import type { IdentityVerificationResponse } from '../../types/portone';

/*
  컴포넌트 외부 주입 속성(Props) 정의
  onSuccess: 인증 성공 시 결과 데이터를 상위로 전달하는 콜백
  onError: 인증 실패 시 에러 메시지를 전달하는 콜백
  isVerified: 이미 인증이 완료되었는지 여부
 */
interface Props {
	onSuccess: (response: IdentityVerificationResponse) => void;
	onError?: (errorMsg: string) => void;
	isVerified?: boolean;
}

/*
  PortOne V2 SDK 기반 본인인증 버튼 컴포넌트
  본인인증 요청 로직 및 로딩 상태 관리의 캡슐화
 */
export default function IdentityVerifyButton({
	onSuccess,
	onError,
	isVerified = false, // 기본값: 미인증 상태
}: Props) {
	// SDK 호출 및 인증창 로딩 상태 관리
	const [isLoading, setIsLoading] = useState(false);

	/*
    본인인증 프로세스 실행 핸들러
    1. 로딩 상태 활성화 및 고유 ID 생성
    2. PortOne SDK 인증 요청 실행
    3. 응답 결과(성공/실패/예외)에 따른 분기 처리
   */
	const handleVerify = async () => {
		setIsLoading(true);
		try {
			// 요청 고유 식별을 위한 랜덤 ID 생성 (Web Crypto API)
			const verificationId = `cert-${crypto.randomUUID()}`;

			// PortOne V2 SDK: 본인인증 요청 호출
			const response = await PortOne.requestIdentityVerification({
				storeId: import.meta.env.VITE_PUBLIC_PORTONE_STORE_ID as string,
				identityVerificationId: verificationId,
				channelKey: import.meta.env.VITE_PUBLIC_PORTONE_CHANNEL_KEY as string,
			});

			// 응답 객체 누락 시 예외 처리
			if (!response) {
				if (onError) onError('인증 응답이 없습니다.');
				return;
			}

			// 응답 내 에러 코드 존재 시 실패 처리
			if (response.code != null) {
				const msg = response.message || '본인인증에 실패했습니다.';
				if (onError) onError(msg);
			} else {
				// 에러 코드가 없는 경우 인증 성공 처리
				onSuccess(response);
			}
		} catch (error: any) {
			console.error(error);
			// 런타임 예외 발생 시 에러 콜백 실행
			if (onError) onError('본인인증 중 오류가 발생했습니다.');
		} finally {
			// 프로세스 종료 후 로딩 상태 초기화
			setIsLoading(false);
		}
	};

	return (
		/*
      버튼 UI 렌더링
      isVerified(true): 파란색 배경, '본인인증 완료' 텍스트, 클릭 비활성화
      isLoading(true): '인증창 로딩 중...' 텍스트, 클릭 비활성화
      Default: '본인인증하기' 텍스트, 클릭 활성화
     */
		<Button
			type='button'
			size='md'
			onClick={handleVerify}
			disabled={isVerified || isLoading}
			className={isVerified ? 'bg-blue-500' : ''}
		>
			{isVerified
				? '본인인증 완료'
				: isLoading
					? '인증창 로딩 중...'
					: '본인인증하기'}
		</Button>
	);
}
