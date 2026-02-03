/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      // 1. 폰트 패밀리 설정 (Pretendard)
      fontFamily: {
        sans: ['Pretendard', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      
      // 2. 타이포그래피 토큰 (Desktop 기준)
      fontSize: {
        // Body (B)
        'b1': ['16px', { lineHeight: '150%', letterSpacing: '0em', fontWeight: '400' }],
        'b2': ['14px', { lineHeight: '150%', letterSpacing: '0em', fontWeight: '400' }],
        
        // Label (L)
        'l1': ['18px', { lineHeight: '100%', letterSpacing: '0.05em', fontWeight: '500' }],
        'l2': ['16px', { lineHeight: '130%', letterSpacing: '0em', fontWeight: '400' }],
        'l3': ['14px', { lineHeight: '100%', letterSpacing: '0.05em', fontWeight: '500' }],
        'l4': ['14px', { lineHeight: '140%', letterSpacing: '0em', fontWeight: '400' }],
      },

      // 3. 컬러 팔레트
      colors: {
        // Base Colors
        background: {
          primary:  "#131316",   // 메인 배경
          disabled: "#161617",
          surface:  "#1C1D21",   // 모달, 카드
          elevated: "#21242C",   // 토스트
          hover:    "#2C2C30",
          overlay:  "rgba(19,19,22,0.7)",
          surfaceError:   "rgba(236, 26, 19, 0.1)",
          surfaceWarning: "rgba(245, 158, 11, 0.1)",
        },
        text: {
          primary:     "#FFFFFF",
          secondary:   "#9194A1",
          disabled:    "#4B4B50",
          placeholder: "#808080",
          brand:       "#0D59F2",
          link:        "#0D59F2",
          error:       "#EC1A13",
          success:     "#256AF4",
          value:       "#FFFFFF",
        },
        border: {
          divider:     "#2F3037",
          inputNormal: "#383A42",
          inputHover:  "#9194A1",
          inputFocus:  "#FFFFFF",
          inputError:   "#EC1A13",
          inputWarning: "#F59E0B",
          inputSuccess: "#256AF4",
        },
        icon: {
          secondary: "#9194A1",
        },

        // Brand & Action
        brand: {
          primary:      "#0D59F2",
          primaryHover: "#256AF4",
          disabled:     "#18181B",
          onPrimary:    "#FFFFFF",
        },

        // Button
        button: {
          large: {
            primary:       "#131316",
            primaryHover:  "#2C2C30",
            disabled:      "#18181B",
            label:         "#FFFFFF",
            labelDisabled: "#4B4B50",
          },
          small: {
            primary:       "#6D4AE6",
            primaryHover:  "#5F3FD1",
            disabled:      "#18181B",
            label:         "#FFFFFF",
            labelDisabled: "#4B4B50",
          }
        },

        // Status
        status: {
          error:       "#EC1A13",
          errorHover:  "#C01510",
          warning:     "#F59E0B",
          warningHover:"#D97706",
          success:     "#256AF4",
          rise:        "#EA580C",
          fall:        "#256AF4",
          premium:     "#EAB308",
          spinner:     "#FFFFFF", 
        },

        // Toast & Chart
        toast: {
          bg: "#21242C",
          textTitle: "#FFFFFF",
          textBody: "#C8C5C5",
        },
        chart: {
          setA: "#C9A24D",
          setB: "#4FA3B8",
          setC: "#8A6BBE",
        },
        social: {
          google: { bg: "#FFFFFF", red: "#EB4335" },
          kakao:  { bg: "#FEE500", icon: "#000000" }
        }
      }, // <<< [중요] colors 객체는 여기서 끝나야 합니다.

      // 4. 애니메이션 설정 (colors 바깥, extend 안쪽)
      keyframes: {
        'toast-in': {
          '0%': { transform: 'translateY(-100%)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
      animation: {
        'toast-in': 'toast-in 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards',
      },

    },
  },
  plugins: [],
}