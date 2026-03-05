import type { SVGProps } from "react";

function IconBase({ path, size = 16, ...rest }: { path: string; size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      dangerouslySetInnerHTML={{ __html: path }}
      {...rest}
    />
  );
}

export const SendIcon = () => (
  <IconBase size={16} path={'<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>'} />
);
export const ChevronDownIcon = () => <IconBase size={11} path={'<polyline points="6 9 12 15 18 9"/>'} />;
export const LockIcon = () => (
  <IconBase size={10} path={'<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/>'} />
);
export const PlusIcon = () => (
  <IconBase size={11} path={'<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>'} />
);
export const XIcon = () => (
  <IconBase size={13} path={'<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>'} />
);
export const ArrowRightIcon = () => (
  <IconBase size={13} path={'<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>'} />
);
export const CheckIcon = () => <IconBase size={12} path={'<polyline points="20 6 9 17 4 12"/>'} />;
export const RulesIcon = () => (
  <IconBase size={14} path={'<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>'} />
);
export const TagIcon = () => (
  <IconBase size={10} path={'<path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/>'} />
);
export const BotIcon = () => (
  <IconBase size={18} path={'<rect x="3" y="8" width="18" height="12" rx="3"/><path d="M9 12h.01M15 12h.01"/><path d="M12 8V4"/><circle cx="12" cy="3" r="1"/><path d="M7 20v2M17 20v2"/>'} />
);
export const TrashIcon = () => (
  <IconBase size={13} path={'<polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>'} />
);
export const EditIcon = () => (
  <IconBase size={12} path={'<path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>'} />
);
