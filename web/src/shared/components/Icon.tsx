/** Minimal stroke icon set (24x24 grid, currentColor) — no icon font, CSP-safe. */

const PATHS = {
  shield: 'M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6l7-3z',
  'shield-check': 'M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6l7-3z M9 12l2 2 4-4',
  'shield-alert': 'M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6l7-3z M12 8v4 M12 15.5v.5',
  alert: 'M12 4l9 16H3l9-16z M12 10v4 M12 17v.5',
  'x-octagon': 'M8 3h8l5 5v8l-5 5H8l-5-5V8l5-5z M9.5 9.5l5 5 M14.5 9.5l-5 5',
  info: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M12 11v5 M12 7.5v.5',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  'check-circle': 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M8 12.5l3 3 5-6',
  x: 'M6 6l12 12 M18 6L6 18',
  'x-circle': 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M9 9l6 6 M15 9l-6 6',
  clock: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M12 7v5l3 2',
  eye: 'M2 12s3.5-6.5 10-6.5S22 12 22 12s-3.5 6.5-10 6.5S2 12 2 12z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
  menu: 'M4 6h16 M4 12h16 M4 18h16',
  sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z M12 2v2 M12 20v2 M4.9 4.9l1.4 1.4 M17.7 17.7l1.4 1.4 M2 12h2 M20 12h2 M4.9 19.1l1.4-1.4 M17.7 6.3l1.4-1.4',
  moon: 'M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z',
  monitor: 'M3 4h18v12H3z M8 20h8 M12 16v4',
  globe: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M3 12h18 M12 3c2.5 2.5 3.8 5.5 3.8 9s-1.3 6.5-3.8 9c-2.5-2.5-3.8-5.5-3.8-9S9.5 5.5 12 3z',
  logout: 'M10 4H5v16h5 M15 8l4 4-4 4 M19 12H9',
  refresh: 'M20 11a8 8 0 0 0-14.5-4.5L4 8 M4 4v4h4 M4 13a8 8 0 0 0 14.5 4.5L20 16 M20 20v-4h-4',
  download: 'M12 4v11 M7 10l5 5 5-5 M5 20h14',
  copy: 'M9 9h11v11H9z M5 15H4V4h11v1',
  play: 'M7 4.5v15l12-7.5-12-7.5z',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z M20 20l-4-4',
  filter: 'M4 5h16l-6 7.5V19l-4 1.5v-8L4 5z',
  'chevron-left': 'M15 5l-7 7 7 7',
  'chevron-right': 'M9 5l7 7-7 7',
  'chevron-down': 'M5 9l7 7 7-7',
  'arrow-left': 'M19 12H5 M11 6l-6 6 6 6',
  external: 'M14 4h6v6 M20 4l-9 9 M18 14v6H4V6h6',
  key: 'M8 11a4 4 0 1 0 0 8 4 4 0 0 0 0-8z M11 13l9-9 M17 7l3 3 M14 10l2 2',
  user: 'M12 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8z M4 21c0-4 3.6-6.5 8-6.5s8 2.5 8 6.5',
  users: 'M9 4a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z M2.5 20c0-3.5 3-5.5 6.5-5.5s6.5 2 6.5 5.5 M16 4.5a3.5 3.5 0 0 1 0 6.5 M18 14.8c2 .6 3.5 2.4 3.5 5.2',
  tool: 'M14.5 6.5a4 4 0 0 0 5 5l-9 9a2.1 2.1 0 0 1-3-3l9-9a4 4 0 0 0-2-2z M14.5 6.5L17 4l3 3-2.5 2.5',
  beaker: 'M9 3h6 M10 3v6l-5.5 9.5A1.7 1.7 0 0 0 6 21h12a1.7 1.7 0 0 0 1.5-2.5L14 9V3 M7 15h10',
  chat: 'M4 5h16v11H9l-5 4V5z M8 9.5h8 M8 12.5h5',
  settings: 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z M12 2.5l1.8 2.6 3.1-.6.6 3.1 2.6 1.8-1.4 2.6 1.4 2.6-2.6 1.8-.6 3.1-3.1-.6L12 21.5l-1.8-2.6-3.1.6-.6-3.1-2.6-1.8L5.3 12 3.9 9.4l2.6-1.8.6-3.1 3.1.6L12 2.5z',
  activity: 'M3 12h4l3-8 4 16 3-8h4',
  'file-text': 'M6 3h8l4 4v14H6z M14 3v4h4 M9 12h6 M9 16h6',
  inbox: 'M4 13l2.5-8h11l2.5 8v6H4z M4 13h5l1 2.5h4l1-2.5h5',
  grid: 'M4 4h7v7H4z M13 4h7v7h-7z M4 13h7v7H4z M13 13h7v7h-7z',
  bell: 'M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15L6 16z M10 20.5a2 2 0 0 0 4 0',
  'wifi-off': 'M3 3l18 18 M8.5 16.5a5 5 0 0 1 7 0 M5 12.5a10 10 0 0 1 4.5-2.4 M14.5 10.1A10 10 0 0 1 19 12.5 M2 8.8a15 15 0 0 1 4-2.3 M10 5.1a15 15 0 0 1 12 3.7 M12 20h.01',
  lock: 'M5 11h14v10H5z M8 11V7a4 4 0 1 1 8 0v4',
  database: 'M12 3c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3z M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6 M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3',
  trash: 'M4 7h16 M9 7V4h6v3 M6 7l1 14h10l1-14',
  plus: 'M12 5v14 M5 12h14',
  send: 'M21 3L10 14 M21 3l-7 18-4-7-7-4 18-7z',
  pause: 'M8 5v14 M16 5v14',
  flame: 'M12 21c-3.9 0-7-2.8-7-6.6 0-3.3 2.4-5.4 3.6-8.4.4 2 1.6 3.2 2.6 3.7C11 6.8 12.4 4.4 15 3c-.4 3 1.1 4.8 2.5 6.6 1 1.4 1.5 3 1.5 4.8 0 3.8-3.1 6.6-7 6.6z',
  layers: 'M12 3l9 5-9 5-9-5 9-5z M3 13l9 5 9-5 M3 17.5l9 5 9-5',
  smartphone: 'M7 2.5h10v19H7z M11 18h2',
  hash: 'M9 3L7 21 M17 3l-2 18 M4 8.5h17 M3 15.5h17',
  diff: 'M6 3v12 M6 15a3 3 0 1 0 0 6 3 3 0 0 0 0-6z M18 21V9 M18 3a3 3 0 1 0 0 6 3 3 0 0 0 0-6z M6 9h7 M11 7l2 2-2 2 M18 15h-7 M13 13l-2 2 2 2',
  zap: 'M13 2L4 14h7l-1 8 9-12h-7l1-8z',
  'circle-dot': 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M12 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4z',
} as const;

export type IconName = keyof typeof PATHS;

/** Icons that point somewhere; mirrored in right-to-left layouts. */
const DIRECTIONAL = new Set<IconName>(['chevron-left', 'chevron-right', 'arrow-left', 'logout', 'send', 'external']);

export interface IconProps {
  name: IconName;
  size?: number;
  className?: string;
  /** When set the icon is announced; otherwise it is decorative (aria-hidden). */
  label?: string;
  strokeWidth?: number;
}

export function Icon({ name, size = 20, className, label, strokeWidth = 1.9 }: IconProps) {
  const classes = ['icon', DIRECTIONAL.has(name) ? 'icon--directional' : '', className ?? ''].filter(Boolean).join(' ');
  return (
    <svg
      className={classes}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      {label ? <title>{label}</title> : null}
      <path d={PATHS[name]} />
    </svg>
  );
}
