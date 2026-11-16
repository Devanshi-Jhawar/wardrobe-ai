// Thin-line icons drawn inline, so there is no icon dependency.
import type { ReactNode } from "react";

function Svg({ children, size = 18 }: { children: ReactNode; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  );
}

type P = { size?: number };

export const IconHanger = ({ size }: P) => (
  <Svg size={size}><path d="M12 6.5a2 2 0 1 1 2 2c-.8 0-2 .6-2 1.5v.8M12 10.8 3.6 16.6c-.8.6-.4 1.9.6 1.9h15.6c1 0 1.4-1.3.6-1.9L12 10.8z" /></Svg>
);
export const IconSpark = ({ size }: P) => (
  <Svg size={size}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6.3 6.3l2.5 2.5M15.2 15.2l2.5 2.5M6.3 17.7l2.5-2.5M15.2 8.8l2.5-2.5" /></Svg>
);
export const IconGrid = ({ size }: P) => (
  <Svg size={size}><rect x="3.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="3.5" y="13.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="13.5" width="7" height="7" rx="1.5" /></Svg>
);
export const IconSliders = ({ size }: P) => (
  <Svg size={size}><path d="M4 7h10M18 7h2M4 17h4M12 17h8" /><circle cx="16" cy="7" r="2" /><circle cx="10" cy="17" r="2" /></Svg>
);
export const IconSend = ({ size }: P) => (
  <Svg size={size}><path d="M5 12h13M13 6l6 6-6 6" /></Svg>
);
export const IconUpload = ({ size }: P) => (
  <Svg size={size}><path d="M12 15V4M7.5 8.5 12 4l4.5 4.5M4.5 15v3a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-3" /></Svg>
);
export const IconClose = ({ size }: P) => (
  <Svg size={size}><path d="M6 6l12 12M18 6 6 18" /></Svg>
);
export const IconCheck = ({ size }: P) => (
  <Svg size={size}><path d="m5 12.5 4.5 4.5L19 7.5" /></Svg>
);
export const IconThumbUp = ({ size }: P) => (
  <Svg size={size}><path d="M7 10.5V20H4.5a1 1 0 0 1-1-1v-7.5a1 1 0 0 1 1-1H7zm0 0 3.6-6.3a1.7 1.7 0 0 1 3.1 1.2l-.6 3.6h5.2a2 2 0 0 1 2 2.4l-1.3 6.6a2 2 0 0 1-2 1.5H7" /></Svg>
);
export const IconThumbDown = ({ size }: P) => (
  <Svg size={size}><path d="M17 13.5V4h2.5a1 1 0 0 1 1 1v7.5a1 1 0 0 1-1 1H17zm0 0-3.6 6.3a1.7 1.7 0 0 1-3.1-1.2l.6-3.6H5.7a2 2 0 0 1-2-2.4L5 6a2 2 0 0 1 2-1.5h10" /></Svg>
);
export const IconStar = ({ size, filled }: P & { filled?: boolean }) => (
  <svg width={size ?? 18} height={size ?? 18} viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"}
    stroke="currentColor" strokeWidth={1.5} strokeLinejoin="round" aria-hidden="true">
    <path d="m12 3.8 2.5 5.1 5.6.8-4 4 .9 5.6-5-2.7-5 2.7.9-5.6-4-4 5.6-.8z" />
  </svg>
);
export const IconArrowOut = ({ size }: P) => (
  <Svg size={size}><path d="M9 6h9v9M18 6 6 18" /></Svg>
);
export const IconRefresh = ({ size }: P) => (
  <Svg size={size}><path d="M20 11a8 8 0 0 0-14.6-4.5M4 4v3.5h3.5M4 13a8 8 0 0 0 14.6 4.5M20 20v-3.5h-3.5" /></Svg>
);
export const IconTrash = ({ size }: P) => (
  <Svg size={size}><path d="M4.5 7h15M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 1.8h6a2 2 0 0 0 2-1.8L18 7M9 7V4.8a.8.8 0 0 1 .8-.8h4.4a.8.8 0 0 1 .8.8V7" /></Svg>
);
export const IconPlus = ({ size }: P) => (
  <Svg size={size}><path d="M12 5v14M5 12h14" /></Svg>
);
export const IconChevron = ({ size }: P) => (
  <Svg size={size}><path d="m9 6 6 6-6 6" /></Svg>
);
export const IconImage = ({ size }: P) => (
  <Svg size={size}><rect x="3.5" y="4.5" width="17" height="15" rx="2" /><circle cx="9" cy="10" r="1.6" /><path d="m4 17 5-4.5 4 3.5 3-2.5 4 3.5" /></Svg>
);
