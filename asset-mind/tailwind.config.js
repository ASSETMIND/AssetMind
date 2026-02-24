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
        sans: ["Pretendard", "Pretendard Variable", "-apple-system", "BlinkMacSystemFont", "system-ui", "sans-serif"],
      },

      // 2. 타이포그래피 사이즈 (전체 시스템)
      fontSize: {
        // Headline (H) - 페이지 최상위 제목
        'h1': ['48px', { lineHeight: '120%', letterSpacing: '-0.05em', fontWeight: '500' }],
        'h1-t': ['32px', { lineHeight: '120%', letterSpacing: '-0.05em', fontWeight: '500' }],
        'h1-m': ['24px', { lineHeight: '120%', letterSpacing: '-0.05em', fontWeight: '500' }],
        
        // Title (T) - 섹션 제목
        't1': ['20px', { lineHeight: '140%', letterSpacing: '0em', fontWeight: '400' }],
        't1-t': ['16px', { lineHeight: '140%', letterSpacing: '0em', fontWeight: '400' }],
        't1-m': ['14px', { lineHeight: '140%', letterSpacing: '0em', fontWeight: '400' }],
        
        // Body (B) - 본문
        'b1': ['16px', { lineHeight: '150%', letterSpacing: '0em', fontWeight: '400' }],
        'b2': ['14px', { lineHeight: '150%', letterSpacing: '0em', fontWeight: '400' }],
        
        // Label (L) - UI 요소
        'l1': ['18px', { lineHeight: '100%', letterSpacing: '0.05em', fontWeight: '500' }],
        'l2': ['16px', { lineHeight: '130%', letterSpacing: '0em', fontWeight: '400' }],
        'l3': ['14px', { lineHeight: '100%', letterSpacing: '0.05em', fontWeight: '500' }],
        'l4': ['14px', { lineHeight: '140%', letterSpacing: '0em', fontWeight: '400' }],
      },

      // 3. 컬러 팔레트
      colors: {
        // Base Colors (Dark Mode)
        background: {
          primary:  "#131316",
          disabled: "#161617",
          surface:  "#1C1D21",
          elevated: "#21242C",
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

        // Toast (확장)
        toast: {
          bg: "#21242C",
          textTitle: "#FFFFFF",
          textBody: "#C8C5C5",
          iconSuccess: "#0D59F2",
          iconError: "#EC1A13",
          gradientSuccess: "#0D59F2",
          gradientError: "#EC1A13",
        },

        // Chart
        chart: {
          setA: "#C9A24D",
          setB: "#4FA3B8",
          setC: "#8A6BBE",
        },

        // Social (확장)
        social: {
          google: { 
            bg: "#FFFFFF", 
            red: "#EB4335",
            blue: "#4285F4",
            yellow: "#FBBC05",
            green: "#34A853",
          },
          kakao: { 
            bg: "#FEE500", 
            icon: "#000000" 
          }
        },

        // Light Mode
        light: {
          background: {
            primary: "#FFFFFF",
            surface:  "#F4F5F7",
            elevated: "#E9EBEF",
            surfaceError:   "rgba(236, 26, 19, 0.1)",
            surfaceWarning: "rgba(245, 158, 11, 0.1)",
          },
          text: {
            primary:   "#131316",
            secondary: "#4B4B50",
            disabled:  "#9194A1",
          },
          border: {
            divider: "#D1D3D8",
            inputNormal: "#C4C6CC",
            inputHover:  "#9194A1",
            inputFocus:  "#0D59F2",
            inputError:   "#EC1A13",
            inputWarning: "#F59E0B",
            inputSuccess: "#256AF4",
          },
          brand: {
            primary:      "#0D59F2",
            primaryHover: "#256AF4",
          },
          status: {
            error:   "#EC1A13",
            warning: "#F59E0B",
            success: "#256AF4",
            rise:    "#EA580C",
            fall:    "#256AF4",
            premium: "#EAB308",
          },
        },
      },

      // 4. 애니메이션 설정
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