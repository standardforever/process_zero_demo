import { useMemo, useState } from "react";

import { CheckIcon, ChevronDownIcon, PlusIcon, TagIcon, XIcon } from "./icons";

type Props = {
  value: string;
  options: readonly string[];
  onChange: (value: string) => void;
};

export function RuleDropdown({ value, options, onChange }: Props) {
  const [custom, setCustom] = useState("");
  const [extras, setExtras] = useState<string[]>([]);

  const mergedOptions = useMemo(() => [...new Set([...options, ...extras])], [options, extras]);

  const addCustom = () => {
    const trimmed = custom.trim();
    if (!trimmed) return;
    if (!mergedOptions.includes(trimmed)) setExtras((prev) => [...prev, trimmed]);
    onChange(trimmed);
    setCustom("");
  };

  return (
    <div className="space-y-2">
      <div className="relative">
        <select
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="w-full appearance-none rounded-lg border border-slate-600 bg-slate-900 px-3 py-2.5 pr-9 text-sm text-slate-100 outline-none transition focus:border-sky-500"
        >
          {mergedOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400">
          <ChevronDownIcon />
        </span>
      </div>

      <div className="rounded-lg border border-slate-700 bg-slate-900/70 p-2.5">
        <p className="mb-2 font-mono text-[11px] tracking-[0.08em] text-slate-400">Add Custom Option</p>
        <div className="flex gap-2">
          <input
            value={custom}
            onChange={(event) => setCustom(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") addCustom();
            }}
            placeholder="Type Custom Value..."
            className="flex-1 rounded-md border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-sky-500"
          />
          <button
            type="button"
            onClick={addCustom}
            disabled={!custom.trim()}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-600 bg-slate-800 px-3 py-2 text-sm font-medium text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <PlusIcon />
            Add
          </button>
        </div>
        {extras.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {extras.map((extra) => (
              <span key={extra} className="inline-flex items-center gap-1 rounded-md border border-slate-600 bg-slate-800 px-2 py-1 text-xs text-slate-200">
                <TagIcon />
                {extra}
                <button
                  type="button"
                  onClick={() => setExtras((prev) => prev.filter((item) => item !== extra))}
                  className="text-slate-400 hover:text-slate-200"
                  aria-label={`Remove ${extra}`}
                >
                  <XIcon />
                </button>
              </span>
            ))}
          </div>
        ) : null}
      </div>

      {value ? (
        <p className="inline-flex items-center gap-1 text-xs text-emerald-300">
          <CheckIcon />
          Selected: {value}
        </p>
      ) : null}
    </div>
  );
}
