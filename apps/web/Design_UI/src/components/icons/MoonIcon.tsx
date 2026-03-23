interface IconProps {
  className?: string;
  color?: string;
  width?: number;
  height?: number;
}

export const MoonIcon = ({ className, color = "currentColor", width = 28, height = 31 }: IconProps) => (
  <svg
    width={width}
    height={height}
    viewBox="0 0 28 31"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
  >
    <path
      d="M6.83333 7.2916C6.83333 16.1583 14.0083 23.3333 22.875 23.3333C23.6479 23.3333 24.4062 23.2749 25.15 23.1728C22.8021 26.7749 18.7479 29.1666 14.125 29.1666C6.87708 29.1666 1 23.2895 1 16.0416C1 11.4187 3.39167 7.36452 6.99375 5.0166C6.89167 5.76035 6.83333 6.51868 6.83333 7.2916Z"
      fill={color}
      stroke={color}
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M18.821 7.33542L22.5106 4.50625L17.8585 4.375L16.3127 0L14.7668 4.375L10.1147 4.50625L13.8043 7.33542L12.4772 11.7979L16.3127 9.15833L20.1481 11.7979L18.821 7.33542Z"
      fill={color}
    />
    <path
      d="M25.2229 16.4063L27.6146 14.5834L24.6104 14.5105L23.6042 11.6667L22.5979 14.5105L19.5938 14.5834L21.9854 16.4063L21.125 19.2938L23.6042 17.5876L26.0833 19.2938L25.2229 16.4063Z"
      fill={color}
    />
  </svg>
);