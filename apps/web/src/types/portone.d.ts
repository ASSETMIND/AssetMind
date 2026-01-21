export {};

declare global {
	interface Window {
		IMP: Iamport;
	}
}

export interface Iamport {
	init: (accountID: string) => void;
	// 본인인증 (certification) 메서드 정의
	certification: (
		params: RequestCertificationParams,
		callback?: (response: RequestCertificationResponse) => void,
	) => void;
}

// v2버전
export interface IdentityVerificationResponse {
	identityVerificationId?: string;
	code?: string;
	message?: string;
}

interface IdentityVerificationResponse {
	identityVerificationId?: string;
	code?: string;
	message?: string;
}
