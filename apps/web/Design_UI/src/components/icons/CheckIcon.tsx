interface IconProps {
  className?: string;
  color?: string;
}

export const CheckIcon = ({ className, color = "currentColor" }: IconProps) => (
  <svg
    width="20"
    height="20"
    viewBox="0 0 20 20"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
  >
    <path
      d="M7.95801 15.0001L3.20801 10.2501L4.39551 9.06258L7.95801 12.6251L15.6038 4.97925L16.7913 6.16675L7.95801 15.0001Z"
      fill={color}
    />
  </svg>
);