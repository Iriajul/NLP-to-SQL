import type { Cell } from "./api";

/**
 * Decide whether a query result should get a chart, and which one, from its shape alone:
 *   - a date / month / year column + a number  -> line chart (sorted by time)
 *   - text categories (2-25 rows) + a number   -> horizontal bar chart (SQL order kept)
 *   - one row, no numbers, or too many categories -> no chart (answer / table say it better)
 */
export interface ChartSpec {
  kind: "line" | "bar";
  labels: string[];       // x values (line) or category names (bar), in drawing order
  metrics: { name: string; values: (number | null)[] }[];  // one is shown at a time: one y-axis only
}

const MAX_BARS = 25;
const TIME_VALUE = /^\d{4}-\d{2}(-\d{2})?([T ].*)?$/;           // 2026-05, 2026-05-03, ISO timestamps
const TIME_NAME = /(^|_)(date|day|week|month|year|quarter|period)(_|$)/i;
const ID_NAME = /(^|_)id$/i;

const isNumber = (v: Cell): v is number => typeof v === "number" && Number.isFinite(v);

function columnIs(rows: Cell[][], i: number, test: (v: Cell) => boolean) {
  const values = rows.map((r) => r[i]).filter((v) => v !== null);
  return values.length > 0 && values.every(test);
}

export function detectChart(columns: string[], rows: Cell[][]): ChartSpec | null {
  if (rows.length < 2 || columns.length < 2) return null;

  const numeric = columns.map((_, i) => columnIs(rows, i, isNumber));
  const timeCol = columns.findIndex(
    (name, i) =>
      columnIs(rows, i, (v) => typeof v === "string" && TIME_VALUE.test(v)) ||
      (numeric[i] && TIME_NAME.test(name)), // e.g. EXTRACT(MONTH ...) AS month
  );
  const metricCols = columns
    .map((name, i) => i)
    .filter((i) => numeric[i] && i !== timeCol && !ID_NAME.test(columns[i]));
  if (!metricCols.length) return null;

  const metricsFor = (order: Cell[][]) =>
    metricCols.map((i) => ({ name: columns[i], values: order.map((r) => (isNumber(r[i]) ? r[i] : null)) }));

  if (timeCol !== -1) {
    const sorted = [...rows].sort((a, b) => String(a[timeCol]).localeCompare(String(b[timeCol]), undefined, { numeric: true }));
    return { kind: "line", labels: sorted.map((r) => String(r[timeCol])), metrics: metricsFor(sorted) };
  }

  if (rows.length > MAX_BARS) return null;
  // Category name: all text columns joined ("C0169 Melissa Hayes"); fall back to an id column.
  let labelCols = columns.map((_, i) => i).filter((i) => !numeric[i]);
  if (!labelCols.length) labelCols = columns.map((_, i) => i).filter((i) => ID_NAME.test(columns[i]));
  if (!labelCols.length) return null;
  const labels = rows.map((r) => labelCols.slice(0, 3).map((i) => r[i] ?? "").join(" ").trim() || "(blank)");
  return { kind: "bar", labels, metrics: metricsFor(rows) };
}

const compact = new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 });
const full = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });

export const formatCompact = (v: number) => (Math.abs(v) < 1000 ? full.format(v) : compact.format(v));
export const formatFull = (v: number) => full.format(v);

/** "2026-05" -> "May 2026", "2026-05-03" -> "May 3, 2026"; anything else unchanged. */
export function formatTimeLabel(label: string) {
  const m = label.match(/^(\d{4})-(\d{2})(?:-(\d{2}))?/);
  if (!m) return label;
  const date = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3] ?? 1));
  return date.toLocaleDateString(undefined, m[3] ? { month: "short", day: "numeric", year: "numeric" } : { month: "short", year: "numeric" });
}

/** Round axis ticks: 0 / 250 / 500 ... covering [min, max]. */
export function niceTicks(min: number, max: number, count = 4) {
  if (min === max) max = min + 1;
  const raw = (max - min) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((s) => s * mag).find((s) => s >= raw)!;
  const ticks = [];
  for (let t = Math.floor(min / step) * step; t <= max + step * 0.001; t += step) ticks.push(Number(t.toFixed(10)));
  if (ticks.at(-1)! < max) ticks.push(ticks.at(-1)! + step);
  return ticks;
}

/** Turn "total_spent" into "Total spent". */
export const prettyName = (s: string) => (s.charAt(0).toUpperCase() + s.slice(1)).replace(/_/g, " ");
