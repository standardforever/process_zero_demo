type Props = {
  mode: "add" | "update";
  email: string;
  submitted: boolean;
  onChange: (value: string) => void;
};

export function InlineEmailForm({ mode, email, submitted, onChange }: Props) {
  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-slate-700 bg-slate-900/80">
      <div className="border-b border-slate-700 px-4 py-3">
        <p className="font-mono text-[11px] font-semibold tracking-[0.1em] text-sky-300">
          {mode === "add" ? "ADD NOTIFICATION EMAIL" : "UPDATE NOTIFICATION EMAIL"}
        </p>
      </div>

      <div className="space-y-2 px-4 py-4">
        <label className="space-y-1">
          <span className="font-mono text-[11px] text-slate-300">Notification Email</span>
          <input
            value={email}
            onChange={(event) => onChange(event.target.value)}
            disabled={submitted}
            type="email"
            placeholder="name@example.com"
            className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-sky-500 disabled:opacity-60"
          />
        </label>
      </div>

      {!submitted ? (
        <div className="border-t border-slate-700 bg-slate-950/60 px-4 py-2.5 text-xs text-slate-300">
          Enter the email, then press <span className="font-semibold text-sky-300">Send</span> to save.
        </div>
      ) : null}
    </div>
  );
}

