"use client";

import { useState } from "react";

const KEYWORDS =
  /\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|FULL|ON|USING|GROUP|BY|ORDER|HAVING|LIMIT|OFFSET|AS|AND|OR|NOT|IN|IS|NULL|EXISTS|BETWEEN|LIKE|ILIKE|DISTINCT|CASE|WHEN|THEN|ELSE|END|WITH|UNION|ALL|ASC|DESC|OVER|PARTITION|FILTER|INTERVAL|DATE|CAST)\b/gi;
const FUNCTIONS = /\b(COUNT|SUM|AVG|MIN|MAX|ROUND|COALESCE|EXTRACT|DATE_TRUNC|TO_CHAR|RANK|DENSE_RANK|ROW_NUMBER|LAG|LEAD|BOOL_AND|BOOL_OR|NOW|CURRENT_DATE)\b/gi;

/** Minimal SQL highlighter: strings, numbers, keywords, functions. */
function highlight(sql: string) {
  const escaped = sql.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  // Split out string literals first so keywords inside them aren't coloured.
  return escaped
    .split(/('(?:[^']|'')*')/g)
    .map((part, i) =>
      i % 2
        ? `<span class="text-emerald-600 dark:text-emerald-400">${part}</span>`
        : part
            .replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="text-amber-600 dark:text-amber-400">$1</span>')
            .replace(KEYWORDS, (m) => `<span class="font-semibold text-indigo-600 dark:text-indigo-400">${m.toUpperCase()}</span>`)
            .replace(FUNCTIONS, (m) => `<span class="text-sky-600 dark:text-sky-400">${m}</span>`),
    )
    .join("");
}

export default function SqlBlock({ sql, muted = false }: { sql: string; muted?: boolean }) {
  const [copied, setCopied] = useState(false);

  return (
    <div className={`group relative rounded-lg border border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 ${muted ? "opacity-60" : ""}`}>
      <button
        onClick={() => {
          navigator.clipboard.writeText(sql);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        }}
        className="absolute right-2 top-2 rounded-md border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-600 opacity-0 transition group-hover:opacity-100 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
      >
        {copied ? "Copied" : "Copy"}
      </button>
      <pre className="overflow-x-auto p-4 font-mono text-[13px] leading-relaxed">
        <code dangerouslySetInnerHTML={{ __html: highlight(sql) }} />
      </pre>
    </div>
  );
}
