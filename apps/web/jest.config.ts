export default {
	preset: 'ts-jest',
	testEnvironment: 'jsdom',
	testMatch: ['**/?(*.)+(spec|test).[tj]s?(x)'],
	setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],
	moduleNameMapper: {
		'\\.(css|less|sass|scss)$': 'identity-obj-proxy',
		'\\.(jpg|jpeg|png|gif|webp|svg)$': '<rootDir>/__mocks__/fileMock.js',
		'^@/(.*)$': '<rootDir>/src/$1',
	},
	transform: {
		'^.+\\.tsx?$': [
			'ts-jest',
			{
				// ts-jest를 위한 별도 설정
				tsconfig: {
					// Vite 프로젝트의 기본 설정인 verbatimModuleSyntax가 Jest와 충돌하므로 끔
					verbatimModuleSyntax: false,
					// import 호환성 문제를 해결하기 위해 킴
					esModuleInterop: true,
					jsx: 'react-jsx',
				},
			},
		],
	},
};
