"use client";

import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { AskResult, StepEvent } from "@/lib/api";
import { detectChart } from "@/lib/chart";
import Chart from "./Chart";
import DataTable from "./DataTable";
import Pipeline from "./Pipeline";
import SqlBlock from "./SqlBlock";

export interface Turn {
  id: number;
  question: string;
  steps: StepEvent[];
  result: AskResult | null;
  failure: string | null; // network / API error
  running: boolean;
}

type Tab = "answer" | "sql" | "data";

export default function AssistantMessage({ turn }: { turn: Turn }) {
  const [tab, setTab] = useState<Tab>("answer");
  const r = turn.result;
  const chart = useMemo(() => (r && !r.error ? detectChart(r.columns, r.rows) : null), [r]);

  if (turn.failure)
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
        {turn.failure}
      </div>
    );

  if (!r) return <Pipeline steps={turn.steps} running={turn.running} />;

  const retries = r.attempts - 1;
  const tabs: { id: Tab; label: string }[] = [
    { id: "answer", label: "Answer" },
    { id: "sql", label: retries > 0 ? `SQL · fixed after ${retries} ${retries === 1 ? "retry" : "retries"}` : "SQL" },
    ...(r.columns.length ? [{ id: "data" as Tab, label: `Data · ${r.rows.length} ${r.rows.length === 1 ? "row" : "rows"}` }] : []),
  ];

  const rewritten = r.question && r.question.trim() !== turn.question.trim();

  return (
    <div className="flex flex-col gap-2">
      {rewritten && (
        <p className="text-xs text-zinc-500">
          <span className="font-medium">Interpreted as:</span> {r.question}
        </p>
      )}
      <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex gap-1 border-b border-zinc-200 px-2 pt-2 dark:border-zinc-800">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`-mb-px shrink-0 whitespace-nowrap border-b-2 px-3 py-2 text-sm transition ${
                tab === t.id
                  ? "border-indigo-500 font-medium text-zinc-900 dark:text-zinc-100"
                  : "border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
              }`}
            >
              {t.label}
            </button>
          ))}
          {r.tables.length > 0 && (
            <span title={r.tables.join(", ")} className="ml-auto hidden min-w-0 self-center truncate pr-2 font-mono text-xs text-zinc-400 sm:block">
              {r.tables.join(" · ")}
            </span>
          )}
        </div>

        <div className="p-4">
          {tab === "answer" && (
            <div className="flex flex-col gap-4">
              {chart && <Chart spec={chart} />}
              <div className={`prose-answer text-[15px] ${r.error ? "text-red-700 dark:text-red-300" : ""}`}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{r.answer}</ReactMarkdown>
              </div>
            </div>
          )}
          {tab === "sql" && (
            <div className="flex flex-col gap-3">
              <SqlBlock sql={r.sql} />
              {retries > 0 && (
                <>
                  <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Earlier failed attempts</p>
                  {r.sql_history.slice(0, -1).map((s, i) => (
                    <SqlBlock key={i} sql={s} muted />
                  ))}
                </>
              )}
            </div>
          )}
          {tab === "data" && <DataTable columns={r.columns} rows={r.rows} />}
        </div>
      </div>
    </div>
  );
}
