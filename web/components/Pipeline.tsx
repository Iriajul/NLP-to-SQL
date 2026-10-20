import type { StepEvent } from "@/lib/api";

const LABELS: Record<string, string> = {
  rewrite_question: "Understanding the question",
  generate_sql: "Picking tables and writing SQL",
  check_sql: "Reviewing SQL",
  execute_sql: "Running query",
  fix_sql: "Fixing SQL from the database error",
  answer: "Writing answer",
};

// What comes after each step, so we can show the one in progress.
const NEXT: Record<string, string> = {
  rewrite_question: "generate_sql",
  generate_sql: "check_sql",
  check_sql: "execute_sql",
  fix_sql: "execute_sql",
};

/** Live list of finished steps plus the one currently running. */
export default function Pipeline({ steps, running }: { steps: StepEvent[]; running: boolean }) {
  const last = steps.at(-1);
  let current: string | null = null;
  if (running) {
    if (!last) current = "rewrite_question";
    else if (last.node === "execute_sql") current = last.error ? "fix_sql" : "answer";
    else current = NEXT[last.node] ?? null;
  }

  return (
    <ol className="flex flex-col gap-1.5 text-sm">
      {steps.map((s, i) => (
        <li key={i} className="flex items-start gap-2">
          {s.error ? <Icon kind="fail" /> : <Icon kind="done" />}
          <span className="text-zinc-600 dark:text-zinc-400">
            {LABELS[s.node]}
            {s.node === "execute_sql" && s.attempt > 1 && ` (attempt ${s.attempt})`}
            {s.error && <span className="mt-0.5 block font-mono text-xs text-red-600 dark:text-red-400">{s.error}</span>}
          </span>
        </li>
      ))}
      {current && (
        <li className="flex items-center gap-2">
          <Icon kind="spin" />
          <span className="text-zinc-900 dark:text-zinc-100">{LABELS[current]}…</span>
        </li>
      )}
    </ol>
  );
}

function Icon({ kind }: { kind: "done" | "fail" | "spin" }) {
  if (kind === "spin")
    return <span className="mt-0.5 h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />;
  return (
    <span
      className={`mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full text-[10px] font-bold text-white ${
        kind === "done" ? "bg-emerald-500" : "bg-red-500"
      }`}
    >
      {kind === "done" ? "✓" : "✕"}
    </span>
  );
}
