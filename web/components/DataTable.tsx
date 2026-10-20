import type { Cell } from "@/lib/api";

function format(v: Cell) {
  if (v === null) return <span className="text-zinc-400">null</span>;
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return String(v);
}

export default function DataTable({ columns, rows }: { columns: string[]; rows: Cell[][] }) {
  if (!rows.length) return <p className="text-sm text-zinc-500">The query returned no rows.</p>;
  const numeric = columns.map((_, i) => rows.every((r) => r[i] === null || typeof r[i] === "number"));

  return (
    <div className="max-h-96 overflow-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-zinc-100 dark:bg-zinc-900">
          <tr>
            {columns.map((c, i) => (
              <th key={c} className={`whitespace-nowrap px-3 py-2 font-medium ${numeric[i] ? "text-right" : "text-left"}`}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, ri) => (
            <tr key={ri} className="border-t border-zinc-100 dark:border-zinc-800/70">
              {r.map((v, ci) => (
                <td key={ci} className={`whitespace-nowrap px-3 py-1.5 ${numeric[ci] ? "text-right tabular-nums" : ""}`}>
                  {format(v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
