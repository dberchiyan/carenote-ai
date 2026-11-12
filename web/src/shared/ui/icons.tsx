import { useId } from "react";
import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

/** 24px stroke icons (1.75px), decorative by default. Pair with visible text or an aria-label. */
function Icon({ size = 18, children, ...props }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {children}
    </svg>
  );
}

export const MicIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="9" y="2.5" width="6" height="12" rx="3" />
    <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7" />
  </Icon>
);
export const PlayIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M8 5.5v13l10.5-6.5z" fill="currentColor" stroke="none" />
  </Icon>
);
export const PauseIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="6" y="5" width="4.5" height="14" rx="1.5" fill="currentColor" stroke="none" />
    <rect x="13.5" y="5" width="4.5" height="14" rx="1.5" fill="currentColor" stroke="none" />
  </Icon>
);
export const StopIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="6" y="6" width="12" height="12" rx="2.5" fill="currentColor" stroke="none" />
  </Icon>
);
export const UploadIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 15V3.5M7.5 8 12 3.5 16.5 8M4 15.5v3A2.5 2.5 0 0 0 6.5 21h11a2.5 2.5 0 0 0 2.5-2.5v-3" />
  </Icon>
);
export const TypeIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="2.5" y="5.5" width="19" height="13" rx="2.5" />
    <path d="M6.5 9.5h.01M10 9.5h.01M13.5 9.5h.01M17 9.5h.01M7.5 14.5h9" />
  </Icon>
);
export const WardIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 21V7.5L12 3l9 4.5V21" />
    <path d="M9.5 21v-5h5v5M12 7.5v4M10 9.5h4" />
  </Icon>
);
export const ChartIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3.5 3.5v15a2 2 0 0 0 2 2h15" />
    <path d="M8 16v-4M12.5 16V8M17 16v-6" />
  </Icon>
);
export const ShieldIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 21s7.5-3.2 7.5-9.5V5.8L12 3 4.5 5.8v5.7C4.5 17.8 12 21 12 21Z" />
    <path d="m9 12 2 2 4-4" />
  </Icon>
);
export const LockIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="4.5" y="10.5" width="15" height="10" rx="2.5" />
    <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
  </Icon>
);
export const LogoutIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M14.5 4.5h3A2.5 2.5 0 0 1 20 7v10a2.5 2.5 0 0 1-2.5 2.5h-3M10 16.5 5.5 12 10 7.5M5.5 12H15" />
  </Icon>
);
export const CheckIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m5 12.5 4.5 4.5L19 7.5" />
  </Icon>
);
export const XIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" />
  </Icon>
);
export const PlusIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 5v14M5 12h14" />
  </Icon>
);
export const AlertIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M10.3 4.2 2.9 17.5A2 2 0 0 0 4.6 20.5h14.8a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0Z" />
    <path d="M12 9.5v4M12 17h.01" />
  </Icon>
);
export const DownloadIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3.5V15M7.5 10.5 12 15l4.5-4.5M4 15.5v3A2.5 2.5 0 0 0 6.5 21h11a2.5 2.5 0 0 0 2.5-2.5v-3" />
  </Icon>
);
export const ChevronRightIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m9.5 6 6 6-6 6" />
  </Icon>
);
export const SparkIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3.5 13.8 9a2 2 0 0 0 1.2 1.2l5.5 1.8-5.5 1.8a2 2 0 0 0-1.2 1.2L12 20.5 10.2 15A2 2 0 0 0 9 13.8L3.5 12 9 10.2A2 2 0 0 0 10.2 9Z" />
  </Icon>
);
export const ActivityIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 12h3.5l2.5-6.5 4.5 13 2.5-6.5H21" />
  </Icon>
);
export const UsersIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.8a3.5 3.5 0 0 1 0 6.4M18.5 14.2A6.5 6.5 0 0 1 21.5 20" />
  </Icon>
);
export const FileIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M14 3H7a2.5 2.5 0 0 0-2.5 2.5v13A2.5 2.5 0 0 0 7 21h10a2.5 2.5 0 0 0 2.5-2.5V8.5Z" />
    <path d="M14 3v5.5h5.5M8.5 13h7M8.5 16.5h5" />
  </Icon>
);
export const PillIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m10.5 20.5 10-10a4.95 4.95 0 0 0-7-7l-10 10a4.95 4.95 0 0 0 7 7ZM8.5 8.5l7 7" />
  </Icon>
);
export const HeartPulseIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M19.5 13.5c1.3-1.4 2-2.9 2-4.8A5.2 5.2 0 0 0 12 6 5.2 5.2 0 0 0 2.5 8.7c0 5.3 6 9.3 9.5 11.8 1.4-1 3.3-2.3 4.9-3.9" />
    <path d="M3.5 12h4l1.5-2.5 3 5 1.5-2.5h3" />
  </Icon>
);
export const ThermometerIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0Z" />
  </Icon>
);
export const ClockIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 2" />
  </Icon>
);

export const ClipboardIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="5.5" y="4.5" width="13" height="16" rx="2" />
    <path d="M9 4.5V3.75A.75.75 0 0 1 9.75 3h4.5a.75.75 0 0 1 .75.75v.75M9 10h6M9 13.5h6M9 17h3.5" />
  </Icon>
);

export const PrinterIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M7 9V4h10v5M7 17H5a1.5 1.5 0 0 1-1.5-1.5v-5A1.5 1.5 0 0 1 5 9h14a1.5 1.5 0 0 1 1.5 1.5v5A1.5 1.5 0 0 1 19 17h-2" />
    <rect x="7" y="14" width="10" height="6" rx="1" />
  </Icon>
);

/** Brand mark: a rounded tile with a voice waveform that ends in a check. */
export const UndoIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M9 14 4 9l5-5" />
    <path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11" />
  </Icon>
);
export const TargetIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="12" r="5" />
    <circle cx="12" cy="12" r="1" />
  </Icon>
);
export const EditIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16v4Z" />
    <path d="m13.5 6.5 4 4" />
  </Icon>
);

export const PanelLeftIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3" y="4" width="18" height="16" rx="2.5" />
    <path d="M9 4v16M15.5 10 13.5 12l2 2" />
  </Icon>
);

export const ChevronDownIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="m6 9 6 6 6-6" />
  </Icon>
);
export const SunIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </Icon>
);
export const MoonIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />
  </Icon>
);
export const MonitorIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3" y="4" width="18" height="12" rx="2" />
    <path d="M8 20h8M12 16v4" />
  </Icon>
);
export const SearchIcon = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </Icon>
);
export const CopyIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M5 15V6a2 2 0 0 1 2-2h9" />
  </Icon>
);
export function LogoMark({ size = 32 }: { size?: number }) {
  // A unique gradient id per instance: with a shared id, a copy inside a hidden subtree (the
  // desktop sidebar on a phone) owns the gradient and every visible copy renders empty.
  const gradient = `cn-logo-${useId().replace(/:/g, "")}`;
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={gradient} x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#2dd4bf" />
          <stop offset="1" stopColor="#0b6e69" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill={`url(#${gradient})`} />
      <path
        d="M7 16h2.5M12 12v8M16 9v14M20 13v6"
        stroke="#fff"
        strokeWidth="2.2"
        strokeLinecap="round"
      />
      <path
        d="m22.5 16.5 1.8 1.8 3.2-3.8"
        stroke="#fff"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}
