"use client";

import { useState } from "react";
import type { ChatSummary, Health, TableInfo } from "@/lib/api";

/** Group chats like "Today", "Previous 7 days", "Older" (list is already newest first). */
function groupByDate(chats: ChatSummary[]) {
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const day = 86_400_000;
  const groups: { label: string; chats: ChatSummary[] }[] = [];
  for (const c of chats) {
    const t = new Date(c.updated_at).getTime();
    const label =
      t >= startOfToday.getTime() ? "Today" :
      t >= startOfToday.getTime() - day ? "Yesterday" :
      t >= startOfToday.getTime() - 7 * day ? "Previous 7 days" : "Older";
    if (groups.at(-1)?.label !== label) groups.push({ label, chats: [] });
    groups.at(-1)!.chats.push(c);
  }
  return groups;
}

export default function Sidebar({
  chats,
  activeId,
  onSelect,
  onNew,
  onDelete,
  tables,
  health,
  disabled,
}: {
  chats: ChatSummary[] | null;
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  tables: TableInfo[] | null;
  health: Health | null;
  disabled: boolean;
}) {
  const [showTables, setShowTables] = useState(false);
  const [openTable, setOpenTable] = useState<string | null>(null);

  return (
    <aside className="flex h-full w-full flex-col border-r border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex flex-col gap-3 p-4">
        <div className="flex items-center gap-2">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-indigo-600 text-sm font-bold text-white">SQL</div>
          <div className="min-w-0">
            <h1 className="text-sm font-semibold">NLP to SQL</h1>
            <p className="flex items-center gap-1.5 truncate text-xs text-zinc-500">
              <span
                className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                  health === null ? "bg-red-500" : health.has_api_key ? "bg-emerald-500" : "bg-amber-500"
                }`}
              />
              {health === null ? "API offline" : health.has_api_key ? health.model : "GROQ_API_KEY missing"}
            </p>
          </div>
        </div>
        <button
          onClick={onNew}
          disabled={disabled}
          className="flex items-center justify-center gap-2 rounded-lg border border-zinc-200 px-3 py-2 text-sm font-medium transition hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
        >
          <span className="text-base leading-none">+</span> New chat
        </button>
      </div>

      <nav className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">
        {chats === null && <p className="px-2 text-sm text-zinc-500">Loading chats…</p>}
        {chats?.length === 0 && <p className="px-2 text-sm text-zinc-500">No saved chats yet.</p>}
        {chats &&
          groupByDate(chats).map((g) => (
            <div key={g.label} className="mb-3">
              <h2 className="px-2 pb-1 text-xs font-medium text-zinc-500">{g.label}</h2>
              {g.chats.map((c) => (
                <div
                  key={c.id}
                  className={`group flex items-center rounded-lg ${
                    c.id === activeId ? "bg-zinc-100 dark:bg-zinc-900" : "hover:bg-zinc-50 dark:hover:bg-zinc-900/60"
                  }`}
                >
                  <button
                    onClick={() => onSelect(c.id)}
                    disabled={disabled}
                    title={c.title}
                    className="min-w-0 flex-1 truncate px-2.5 py-2 text-left text-sm text-zinc-700 disabled:cursor-not-allowed dark:text-zinc-300"
                  >
                    {c.title}
                  </button>
                  <button
                    onClick={() => onDelete(c.id)}
                    disabled={disabled}
                    aria-label={`Delete chat: ${c.title}`}
                    className="mr-1 rounded-md px-2 py-1 text-zinc-400 opacity-0 transition hover:bg-zinc-200 hover:text-red-600 focus:opacity-100 group-hover:opacity-100 disabled:hidden dark:hover:bg-zinc-800"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          ))}
      </nav>

      <div className="border-t border-zinc-200 p-2 dark:border-zinc-800">
        <button
          onClick={() => setShowTables(!showTables)}
          className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-xs font-medium text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-900"
        >
          <span>Database tables</span>
          <span>{showTables ? "▾" : "▸"}</span>
        </button>
        {showTables && (
          <div className="mt-1 max-h-72 overflow-y-auto">
            {!tables && <p className="px-2 text-sm text-zinc-500">Loading…</p>}
            {tables?.map((t) => (
              <div key={t.name}>
                <button
                  onClick={() => setOpenTable(openTable === t.name ? null : t.name)}
                  className="flex w-full items-center justify-between rounded-md px-2 py-1 text-sm hover:bg-zinc-100 dark:hover:bg-zinc-900"
                >
                  <span className="font-mono text-[13px]">
                    <span className="mr-1.5 inline-block w-2 text-zinc-400">{openTable === t.name ? "▾" : "▸"}</span>
                    {t.name}
                  </span>
                  <span className="text-xs tabular-nums text-zinc-500">{t.rows.toLocaleString()}</span>
                </button>
                {openTable === t.name && (
                  <ul className="mb-2 ml-6 border-l border-zinc-200 pl-3 dark:border-zinc-800">
                    {t.columns.map((c) => (
                      <li key={c.name} className="flex justify-between gap-2 py-0.5 font-mono text-xs">
                        <span>{c.name}</span>
                        <span className="truncate text-zinc-500">{c.type.replace("character varying", "varchar")}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
