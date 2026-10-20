"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { formatCompact, formatFull, formatTimeLabel, niceTicks, prettyName, type ChartSpec } from "@/lib/chart";

/* Mark specs: bars <= 24px thick with a 4px rounded data end, 2px lines, 8px end dot with a 2px
   surface ring, 10% area wash, solid hairline grid. Colors come from --series-1 / --chart-* in globals.css. */
const BAR_THICKNESS = 16;
const ROW_HEIGHT = 30;
const LINE_HEIGHT = 220;
const CHAR_WIDTH = 6.6; // approx. width of a 12px label character, for truncation
const SERIES = "var(--series-1)";

function useWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.floor(e.contentRect.width)));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

function truncate(s: string, maxPx: number) {
  const max = Math.max(3, Math.floor(maxPx / CHAR_WIDTH));
  return s.length <= max ? s : s.slice(0, max - 1) + "…";
}

function Tooltip({ x, y, width, children }: { x: number; y: number; width: number; children: ReactNode }) {
  // Keep the box inside the chart: flip to the left of the pointer near the right edge.
  const left = x > width - 180 ? x - 12 : x + 12;
  return (
    <div
      className="pointer-events-none absolute z-10 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs shadow-md dark:border-zinc-700 dark:bg-zinc-900"
      style={{ left, top: y, transform: `translate(${x > width - 180 ? "-100%" : "0"}, -50%)` }}
    >
      {children}
    </div>
  );
}

function TooltipRow({ label, value, metric }: { label: string; value: number | null; metric: string }) {
  return (
    <>
      <div className="text-sm font-semibold tabular-nums text-zinc-900 dark:text-zinc-50">
        {value === null ? "—" : formatFull(value)}
      </div>
      <div className="mt-0.5 flex items-center gap-1.5 text-zinc-500">
        <span className="inline-block h-0.5 w-3 rounded-full" style={{ background: SERIES }} />
        {prettyName(metric)} · {label}
      </div>
    </>
  );
}

/** Rectangle with a 4px rounded end at the data end (right for positive, left for negative). */
function barPath(x0: number, x1: number, y: number, h: number) {
  const w = Math.abs(x1 - x0);
  const r = Math.min(4, w, h / 2);
  const dir = x1 >= x0 ? 1 : -1;
  const xr = x1 - dir * r;
  return `M${x0},${y} H${xr} Q${x1},${y} ${x1},${y + r} V${y + h - r} Q${x1},${y + h} ${xr},${y + h} H${x0} Z`;
}

function BarChart({ labels, values, metric, width }: { labels: string[]; values: (number | null)[]; metric: string; width: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const nums = values.filter((v): v is number => v !== null);
  const ticks = niceTicks(Math.min(0, ...nums), Math.max(0, ...nums));
  const [lo, hi] = [ticks[0], ticks.at(-1)!];

  const labelW = Math.min(width * 0.38, Math.max(...labels.map((l) => l.length)) * CHAR_WIDTH + 12, 220);
  const valueW = 64;
  const plotL = labelW, plotR = width - valueW;
  const x = (v: number) => plotL + ((v - lo) / (hi - lo)) * (plotR - plotL);
  const height = labels.length * ROW_HEIGHT;

  return (
    <div className="relative">
      <svg width={width} height={height} role="img" aria-label={`Bar chart of ${prettyName(metric)}`}>
        {/* zero baseline */}
        <line x1={x(0)} x2={x(0)} y1={0} y2={height} style={{ stroke: "var(--chart-axis)" }} strokeWidth={1} />
        {labels.map((label, i) => {
          const v = values[i];
          const y = i * ROW_HEIGHT + (ROW_HEIGHT - BAR_THICKNESS) / 2;
          const tipX = v === null ? x(0) : v >= 0 ? x(v) + 6 : x(v) - 6;
          return (
            <g
              key={i}
              tabIndex={0}
              onPointerEnter={() => setHover(i)}
              onPointerLeave={() => setHover(null)}
              onFocus={() => setHover(i)}
              onBlur={() => setHover(null)}
              className="outline-none"
            >
              {/* hit target: the whole row, bigger than the bar */}
              <rect x={0} y={i * ROW_HEIGHT} width={width} height={ROW_HEIGHT} className="fill-transparent" />
              {hover === i && (
                <rect x={0} y={i * ROW_HEIGHT} width={width} height={ROW_HEIGHT} rx={4} style={{ fill: "var(--chart-hover)" }} />
              )}
              <text x={plotL - 10} y={i * ROW_HEIGHT + ROW_HEIGHT / 2} dy="0.35em" textAnchor="end" className="fill-zinc-600 text-xs dark:fill-zinc-400">
                {truncate(label, labelW - 12)}
              </text>
              {v !== null && (
                <path d={barPath(x(0), x(v), y, BAR_THICKNESS)} style={{ fill: SERIES }} opacity={hover === null || hover === i ? 1 : 0.7} />
              )}
              <text
                x={tipX}
                y={i * ROW_HEIGHT + ROW_HEIGHT / 2}
                dy="0.35em"
                textAnchor={v !== null && v < 0 ? "end" : "start"}
                className="fill-zinc-500 text-xs tabular-nums"
              >
                {v === null ? "—" : formatCompact(v)}
              </text>
            </g>
          );
        })}
      </svg>
      {hover !== null && (
        <Tooltip x={Math.min(plotR, x(values[hover] ?? 0))} y={hover * ROW_HEIGHT + ROW_HEIGHT / 2} width={width}>
          <TooltipRow label={labels[hover]} value={values[hover]} metric={metric} />
        </Tooltip>
      )}
    </div>
  );
}

function LineChart({ labels, values, metric, width }: { labels: string[]; values: (number | null)[]; metric: string; width: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const monthly = labels.every((l) => /^\d{4}-\d{2}(-01([T ]00:00(:00)?([+-]\d{2}:?\d{2}|Z)?)?)?$/.test(l));
  const fmt = (l: string) => formatTimeLabel(monthly ? l.slice(0, 7) : l);
  const nums = values.filter((v): v is number => v !== null);
  const ticks = niceTicks(Math.min(0, ...nums), Math.max(0, ...nums));
  const [lo, hi] = [ticks[0], ticks.at(-1)!];

  const m = { top: 12, right: 60, bottom: 28, left: Math.max(...ticks.map((t) => formatCompact(t).length)) * 7 + 12 };
  const plotW = width - m.left - m.right, plotH = LINE_HEIGHT - m.top - m.bottom;
  const n = labels.length;
  const x = (i: number) => m.left + (n === 1 ? plotW / 2 : (i / (n - 1)) * plotW);
  const y = (v: number) => m.top + plotH - ((v - lo) / (hi - lo)) * plotH;

  // Line segments, broken at nulls.
  const segments: string[] = [];
  let current = "";
  values.forEach((v, i) => {
    if (v === null) { if (current) segments.push(current); current = ""; return; }
    current += `${current ? "L" : "M"}${x(i)},${y(v)} `;
  });
  if (current) segments.push(current);
  const area = segments.map((d) => {
    const pts = d.trim().split(" ");
    const first = pts[0].slice(1).split(",")[0], last = pts.at(-1)!.slice(1).split(",")[0];
    return `${d} L${last},${y(Math.max(lo, 0))} L${first},${y(Math.max(lo, 0))} Z`;
  });

  // At most ~6 x labels, evenly spread, always including the last.
  const every = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(plotW / 90))));
  const xTicks = labels.map((_, i) => i).filter((i) => i % every === 0 || i === n - 1)
    .filter((i, k, arr) => i === n - 1 || arr.at(-1)! - i >= every * 0.6);

  const lastIdx = values.findLastIndex((v) => v !== null);
  const nearest = (px: number) => Math.max(0, Math.min(n - 1, Math.round(((px - m.left) / plotW) * (n - 1))));

  return (
    <div className="relative">
      <svg
        width={width}
        height={LINE_HEIGHT}
        role="img"
        aria-label={`Line chart of ${prettyName(metric)} over time`}
        tabIndex={0}
        className="outline-none"
        onPointerMove={(e) => setHover(nearest(e.clientX - e.currentTarget.getBoundingClientRect().left))}
        onPointerLeave={() => setHover(null)}
        onFocus={() => setHover(lastIdx)}
        onBlur={() => setHover(null)}
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft") setHover((h) => Math.max(0, (h ?? n) - 1));
          if (e.key === "ArrowRight") setHover((h) => Math.min(n - 1, (h ?? -1) + 1));
        }}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={m.left} x2={width - m.right} y1={y(t)} y2={y(t)} strokeWidth={1}
              style={{ stroke: t === 0 ? "var(--chart-axis)" : "var(--chart-grid)" }} />
            <text x={m.left - 8} y={y(t)} dy="0.35em" textAnchor="end" className="fill-zinc-500 text-[11px] tabular-nums">
              {formatCompact(t)}
            </text>
          </g>
        ))}
        {xTicks.map((i) => (
          <text key={i} x={x(i)} y={LINE_HEIGHT - 8} textAnchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"}
            className="fill-zinc-500 text-[11px]">
            {fmt(labels[i])}
          </text>
        ))}
        {area.map((d, i) => <path key={i} d={d} style={{ fill: SERIES }} opacity={0.1} />)}
        {segments.map((d, i) => (
          <path key={i} d={d} fill="none" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" style={{ stroke: SERIES }} />
        ))}
        {hover !== null && (
          <line x1={x(hover)} x2={x(hover)} y1={m.top} y2={m.top + plotH} strokeWidth={1} className="stroke-zinc-400 dark:stroke-zinc-500" />
        )}
        {[lastIdx, hover].filter((i): i is number => i !== null && i >= 0 && values[i] !== null).map((i) => (
          <circle key={`dot-${i}`} cx={x(i)} cy={y(values[i]!)} r={4} strokeWidth={2}
            style={{ fill: SERIES, stroke: "var(--chart-surface)" }} />
        ))}
        {lastIdx >= 0 && (
          <text x={x(lastIdx) + 10} y={y(values[lastIdx]!)} dy="0.35em" className="fill-zinc-600 text-xs font-medium tabular-nums dark:fill-zinc-300">
            {formatCompact(values[lastIdx]!)}
          </text>
        )}
      </svg>
      {hover !== null && (
        <Tooltip x={x(hover)} y={values[hover] === null ? m.top + plotH / 2 : y(values[hover]!)} width={width}>
          <TooltipRow label={fmt(labels[hover])} value={values[hover]} metric={metric} />
        </Tooltip>
      )}
    </div>
  );
}

export default function Chart({ spec }: { spec: ChartSpec }) {
  const [ref, width] = useWidth();
  const [metricIdx, setMetricIdx] = useState(0);
  const metric = spec.metrics[Math.min(metricIdx, spec.metrics.length - 1)];

  return (
    <figure className="flex flex-col gap-3">
      <figcaption className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          {prettyName(metric.name)}
          {spec.kind === "line" ? " over time" : ""}
        </span>
        {spec.metrics.length > 1 && (
          // One y-axis per chart: several numeric columns are shown one at a time.
          <div className="flex rounded-lg bg-zinc-100 p-0.5 text-xs dark:bg-zinc-900">
            {spec.metrics.map((mt, i) => (
              <button
                key={mt.name}
                onClick={() => setMetricIdx(i)}
                className={`rounded-md px-2.5 py-1 transition ${
                  mt === metric ? "bg-white font-medium shadow-sm dark:bg-zinc-700" : "text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
                }`}
              >
                {prettyName(mt.name)}
              </button>
            ))}
          </div>
        )}
      </figcaption>
      <div ref={ref} className="w-full">
        {width > 0 &&
          (spec.kind === "bar" ? (
            <BarChart labels={spec.labels} values={metric.values} metric={metric.name} width={width} />
          ) : (
            <LineChart labels={spec.labels} values={metric.values} metric={metric.name} width={width} />
          ))}
      </div>
    </figure>
  );
}
