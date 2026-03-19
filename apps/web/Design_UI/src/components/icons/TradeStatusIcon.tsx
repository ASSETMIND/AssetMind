interface IconProps {
  className?: string;
  color?: string;
}

export const TradeStatusIcon = ({ className, color = "currentColor" }: IconProps) => (
  <svg
    width="20"
    height="20"
    viewBox="0 0 20 20"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
  >
    <mask
      id="mask0_223_3165"
      style={{ maskType: "luminance" }}
      maskUnits="userSpaceOnUse"
      x="0"
      y="0"
      width="20"
      height="20"
    >
      <path
        d="M17.5 1H2.5C2.10218 1 1.72064 1.15804 1.43934 1.43934C1.15804 1.72064 1 2.10218 1 2.5V17.5C1 17.8978 1.15804 18.2794 1.43934 18.5607C1.72064 18.842 2.10218 19 2.5 19H17.5C17.8978 19 18.2794 18.842 18.5607 18.5607C18.842 18.2794 19 17.8978 19 17.5V2.5C19 2.10218 18.842 1.72064 18.5607 1.43934C18.2794 1.15804 17.8978 1 17.5 1Z"
        fill="white"
        stroke="white"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M8.5 13.5L11 15.5L15 10.5M5 5.5H15M5 9.5H9"
        stroke="black"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </mask>
    <g mask="url(#mask0_223_3165)">
      <path d="M-2 -2H22V22H-2V-2Z" fill={color} />
    </g>
  </svg>
);