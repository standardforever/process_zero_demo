import type { ReactNode } from "react";

import { BotIcon } from "./icons";
import { useStreamText } from "./use-stream-text";

function MarkdownInline({ text }: { text: string }) {
  const parts: ReactNode[] = [];
  const regex = /\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let index = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) parts.push(<span key={index++}>{text.slice(last, match.index)}</span>);

    if (match[1]) parts.push(<strong key={index++} className="font-semibold text-slate-100">{match[1]}</strong>);
    else if (match[2]) parts.push(<em key={index++} className="text-sky-200">{match[2]}</em>);
    else if (match[3]) parts.push(<code key={index++} className="rounded bg-slate-700/80 px-1.5 py-0.5 font-mono text-xs text-sky-200">{match[3]}</code>);

    last = match.index + match[0].length;
  }

  if (last < text.length) parts.push(<span key={index++}>{text.slice(last)}</span>);
  return <>{parts}</>;
}

function StreamText({ text }: { text: string }) {
  const { shown, done } = useStreamText(text, true);

  return (
    <div className="space-y-1 text-[15px] leading-7 text-slate-200">
      {shown.split("\n").map((line, idx) => (
        <div key={`${idx}-${line}`} className="min-h-[1.25rem]">
          {line ? <MarkdownInline text={line} /> : <span className="opacity-0">.</span>}
        </div>
      ))}
      {!done ? <span className="ml-1 inline-block h-4 w-0.5 animate-pulse bg-sky-300 align-middle" /> : null}
    </div>
  );
}

export function AgentBubble({
  children,
  time,
  streamText,
}: {
  children?: ReactNode;
  time: string;
  streamText?: string;
}) {
  return (
    <div className="mb-6 flex items-start gap-3">
      <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-blue-400/40 bg-gradient-to-br from-blue-600 to-violet-600 text-slate-100">
        <BotIcon />
      </div>
      <div className="min-w-0 flex-1">
        <p className="mb-1 font-mono text-[11px] tracking-[0.08em] text-slate-400">TRANSFORM AGENT</p>
        <div className="rounded-[14px] rounded-tl-[4px] border border-slate-700 bg-slate-900/80 p-4">
          {streamText ? <StreamText text={streamText} /> : children}
        </div>
        <p className="mt-1 font-mono text-[11px] text-slate-500">{time}</p>
      </div>
    </div>
  );
}

export function UserBubble({ text, time }: { text: string; time: string }) {
  return (
    <div className="mb-6 flex justify-end">
      <div className="max-w-[80%]">
        <div className="rounded-[14px] rounded-tr-[4px] border border-slate-700 bg-slate-800 p-3.5 text-[15px] leading-6 text-slate-100">
          {text}
        </div>
        <p className="mt-1 text-right font-mono text-[11px] text-slate-500">{time}</p>
      </div>
    </div>
  );
}
