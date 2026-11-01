import type { ReactNode } from "react";

interface IconProps {
  size?: number;
}

function Svg({ size = 16, children }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export const IconLogo = ({ size = 22 }: IconProps) => (
  <Svg size={size}>
    <path d="M12 3l7.5 4.3v8.4L12 20l-7.5-4.3V7.3z" />
    <circle cx="12" cy="11.5" r="2.4" />
    <circle cx="19.5" cy="7.3" r="1" fill="currentColor" />
    <circle cx="4.5" cy="15.7" r="1" fill="currentColor" />
  </Svg>
);
export const IconPlay = (p: IconProps) => (
  <Svg {...p}><path d="M7 4.5v15l12-7.5z" fill="currentColor" stroke="none" /></Svg>
);
export const IconTrash = (p: IconProps) => (
  <Svg {...p}><path d="M4 7h16M10 11v6M14 11v6M6 7l1 12h10l1-12M9 7V4h6v3" /></Svg>
);
export const IconDownload = (p: IconProps) => (
  <Svg {...p}><path d="M12 4v11M7 11l5 5 5-5M5 20h14" /></Svg>
);
export const IconCopy = (p: IconProps) => (
  <Svg {...p}><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V6a2 2 0 012-2h9" /></Svg>
);
export const IconSun = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </Svg>
);
export const IconMoon = (p: IconProps) => (
  <Svg {...p}><path d="M20 14.5A8 8 0 019.5 4a8 8 0 1010.5 10.5z" /></Svg>
);
export const IconCube = (p: IconProps) => (
  <Svg {...p}><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9zM12 12l8-4.5M12 12L4 7.5M12 12v9" /></Svg>
);
export const IconInfo = (p: IconProps) => (
  <Svg {...p}><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7.5v.01" /></Svg>
);
export const IconCheck = (p: IconProps) => (
  <Svg {...p}><path d="M5 12.5l4.5 4.5L19 7.5" /></Svg>
);
export const IconAlert = (p: IconProps) => (
  <Svg {...p}><path d="M12 4l9 16H3zM12 10v4M12 17.5v.01" /></Svg>
);
export const IconFolder = (p: IconProps) => (
  <Svg {...p}><path d="M3 6.5A1.5 1.5 0 014.5 5H9l2 2h8.5A1.5 1.5 0 0121 8.5v9a1.5 1.5 0 01-1.5 1.5h-15A1.5 1.5 0 013 17.5z" /></Svg>
);
export const IconUpload = (p: IconProps) => (
  <Svg {...p}><path d="M12 16V5M7 9l5-5 5 5M5 20h14" /></Svg>
);
export const IconChevron = (p: IconProps) => (
  <Svg {...p}><path d="M6 9l6 6 6-6" /></Svg>
);
