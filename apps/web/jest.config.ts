export default {
	preset: 'ts-jest/presets/js-with-ts',
	testEnvironment: 'jsdom',
	testMatch: ['**/?(*.)+(spec|test).[tj]s?(x)'],
	setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],
	collectCoverageFrom: [
		'src/hooks/auth/use-login-logic.ts',
		'src/hooks/auth/use-refresh.ts',
		'src/hooks/auth/use-signup-logic.ts',
		'src/hooks/auth/use-social-login-logic.ts',
	],
	coverageDirectory: 'coverage',
	transformIgnorePatterns: ['node_modules/(?!(msw|@mswjs|until-async)/)'],
	testEnvironmentOptions: {
		customExportConditions: [''],
	},
	moduleNameMapper: {
		'\\.(css|less|sass|scss)$': 'identity-obj-proxy',
		'\\.(jpg|jpeg|png|gif|webp|svg)$': '<rootDir>/__mocks__/fileMock.js',
		'^@/(.*)$': '<rootDir>/src/$1',
	},
	transform: {
		'^.+\\.[tj]sx?$': [
			'ts-jest',
			{
				// ts-jest를 위한 별도 설정
				tsconfig: {
					isolatedModules: true,
					// Vite 프로젝트의 기본 설정인 verbatimModuleSyntax가 Jest와 충돌하므로 끔
					verbatimModuleSyntax: false,
					// import 호환성 문제를 해결하기 위해 킴
					esModuleInterop: true,
					jsx: 'react-jsx',
					allowJs: true,
				},
			},
		],
	},
};
