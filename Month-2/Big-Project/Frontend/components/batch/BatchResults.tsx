"use client";

/*!
 * AeroDelay AI - Batch prediction results.
 *
 * Summary cards, inline-SVG risk donut + outcome bars, per-file stats,
 * paged prediction rows, the row-level failure ledger and every download.
 * No chart library: the visuals are plain SVG so the bundle stays light.
 *
 * Probabilities are presented as MODEL OUTPUTS, never as certainty.
 */

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import {
  Download,
  FileDown,
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Cpu,
  Layers,
} from "lucide-react";
import {
  GlassPanel,
  LoadingSkeleton,
  SectionDivider,
  StatusBadge,
} from "../ui";
import { useReducedMotion } from "../../hooks/use-reduced-motion";
import {
  api,
  describeApiError,
  type BatchJobStatus,
  type BatchResults as BatchResultsPayload,
} from "../../lib/api";

const RISK_COLORS: Record<string, string> = {
  Low: "#22c55e",
  Medium: "#eab308",
  High: "#ef4444",
};

/* ── Inline SVG visuals ─────────────────────────────────────────────────── */

function RiskDonut({
  counts,
  total,
}: {
  counts: { Low: number; Medium: number; High: number };
  total: number;
}) {
  const size = 148;
  const stroke = 20;
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const segments = [
    { key: "Low" as const, value: counts.Low },
    { key: "Medium" as const, value: counts.Medium },
    { key: "High" as const, value: counts.High },
  ];

  let offset = 0;
  const arcs = segments.map((seg) => {
    const fraction = total > 0 ? seg.value / total : 0;
    const length = fraction * circumference;
    const arc = {
      key: seg.key,
      dash: `${length} ${Math.max(0, circumference - length)}`,
      offset: -offset,
      color: RISK_COLORS[seg.key],
      fraction,
    };
    offset += length;
    return arc;
  });

  return (
    <div className="flex flex-col sm:flex-row items-center gap-5">
      <div
        className="relative shrink-0"
        style={{ width: size, height: size }}
        role="img"
        aria-label={`Risk distribution: ${counts.Low} low, ${counts.Medium} medium, ${counts.High} high`}
        data-testid="batch-donut"
      >
        <svg viewBox={`0 0 ${size} ${size}`} className="w-full h-full -rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="var(--color-navy-800, #1e293b)"
            strokeWidth={stroke}
          />
          {arcs.map((arc) => (
            <circle
              key={arc.key}
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={arc.color}
              strokeWidth={stroke}
              strokeDasharray={arc.dash}
              strokeDashoffset={arc.offset}
              strokeLinecap="butt"
            />
          ))}
        </svg>
        <span className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-semibold text-navy-100">{total}</span>
          <span className="text-[10px] uppercase tracking-wider text-navy-500">
            rows
          </span>
        </span>
      </div>

      <ul className="space-y-2 text-sm w-full">
        {arcs.map((arc) => (
          <li
            key={arc.key}
            className="flex items-center justify-between gap-3"
          >
            <span className="flex items-center gap-2 text-navy-300">
              <span
                className="w-3 h-3 rounded-sm shrink-0"
                style={{ backgroundColor: arc.color }}
                aria-hidden="true"
              />
              {arc.key}
            </span>
            <span className="text-navy-100 font-medium">
              {counts[arc.key]}{" "}
              <span className="text-navy-500 font-normal">
                ({Math.round(arc.fraction * 100)}%)
              </span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function OutcomeBars({ delayed, onTime }: { delayed: number; onTime: number }) {
  const total = delayed + onTime;
  const delayedPct = total > 0 ? (delayed / total) * 100 : 0;

  return (
    <div data-testid="batch-outcome-bars" className="w-full">
      <div className="flex items-center justify-between text-sm mb-2">
        <span className="text-navy-400">Predicted class split</span>
        <span className="text-navy-200 font-medium">
          {Math.round(delayedPct)}% delayed
        </span>
      </div>
      <div
        className="flex h-4 rounded-full overflow-hidden bg-navy-950 border border-navy-800"
        role="img"
        aria-label={`${delayed} delayed, ${onTime} on time`}
      >
        <div
          className="h-full bg-red-500/80 transition-all duration-500"
          style={{ width: `${delayedPct}%` }}
        />
        <div
          className="h-full bg-green-500/70 transition-all duration-500"
          style={{ width: `${100 - delayedPct}%` }}
        />
      </div>
      <div className="flex justify-between text-xs mt-2">
        <span className="text-red-300">Delayed · {delayed}</span>
        <span className="text-green-300">On time · {onTime}</span>
      </div>
    </div>
  );
}

/* ── Download helper ────────────────────────────────────────────────────── */

async function triggerDownload(jobId: string, file: string): Promise<void> {
  const { blob, filename } = await api.batchDownload(jobId, file);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 4000);
}

/* ── Main results panel ─────────────────────────────────────────────────── */

const PAGE_SIZE = 50;

export function BatchResults({ job }: { job: BatchJobStatus }) {
  const { reduced } = useReducedMotion();
  const [page, setPage] = useState(1);
  const [data, setData] = useState<BatchResultsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  const summary = job.summary;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const res = await api.batchResults(job.job_id, page, PAGE_SIZE);
        if (!cancelled) setData(res);
      } catch (err) {
        if (!cancelled) setError(describeApiError(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job.job_id, page]);

  async function download(label: string, file: string) {
    setDownloadError(null);
    setDownloading(label);
    try {
      await triggerDownload(job.job_id, file);
    } catch (err) {
      setDownloadError(describeApiError(err));
    } finally {
      setDownloading(null);
    }
  }

  if (!summary) return null;

  const risk = summary.risk_counts;
  const predicted = summary.rows_predicted;

  const stats = [
    { label: "Files", value: `${summary.files_succeeded}/${summary.files_uploaded}`, hint: "processed" },
    { label: "Rows predicted", value: summary.rows_predicted.toLocaleString(), hint: "real model output" },
    { label: "Rows rejected", value: summary.rows_rejected.toLocaleString(), hint: "invalid input" },
    { label: "Delayed", value: summary.delayed.toLocaleString(), hint: "predicted class 1" },
    { label: "On time", value: summary.on_time.toLocaleString(), hint: "predicted class 0" },
    {
      label: "Avg probability",
      value:
        summary.average_probability === null
          ? "—"
          : `${(summary.average_probability * 100).toFixed(1)}%`,
      hint: "model output",
    },
  ];

  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      data-testid="batch-summary"
      data-status={job.status}
    >
      {/* Job-level banners */}
      {summary.files_rejected > 0 && (
        <div
          data-testid="batch-rejected-files"
          className="mb-6 flex items-start gap-3 p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/40 text-yellow-200 text-sm"
        >
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" aria-hidden="true" />
          <span>
            {summary.files_rejected} file
            {summary.files_rejected === 1 ? "" : "s"} failed upload validation
            and {summary.files_rejected === 1 ? "was" : "were"} not processed.
            See the file list above for the exact reason.
          </span>
        </div>
      )}
      {summary.rows_failed > 0 && (
        <div className="mb-6 flex items-start gap-3 p-4 rounded-lg bg-red-500/10 border border-red-500/40 text-red-200 text-sm">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" aria-hidden="true" />
          <span>
            {summary.rows_failed} row
            {summary.rows_failed === 1 ? "" : "s"} could not be read and were
            not predicted. Nothing was silently dropped.
          </span>
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        {stats.map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={reduced ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, delay: i * 0.04 }}
            className="p-4 rounded-xl bg-navy-950/70 border border-navy-800/70 min-w-0"
          >
            <p className="text-[11px] uppercase tracking-wider text-navy-500 truncate">
              {stat.label}
            </p>
            <p className="text-lg font-semibold text-navy-100 mt-1 break-words">
              {stat.value}
            </p>
            <p className="text-[11px] text-navy-600 mt-0.5">{stat.hint}</p>
          </motion.div>
        ))}
      </div>

      {/* Charts */}
      <div
        data-testid="batch-charts"
        className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6"
      >
        <GlassPanel className="p-5">
          <h3 className="text-sm font-medium text-navy-300 mb-4">
            Risk distribution
          </h3>
          <RiskDonut counts={risk} total={predicted} />
        </GlassPanel>
        <GlassPanel className="p-5">
          <h3 className="text-sm font-medium text-navy-300 mb-4">
            Outcome split
          </h3>
          <div className="flex flex-col justify-center h-full gap-5">
            <OutcomeBars delayed={summary.delayed} onTime={summary.on_time} />
            <div className="text-xs text-navy-500 leading-relaxed border-t border-navy-800/70 pt-3">
              Class threshold {summary.class_threshold.toFixed(2)} · risk bands
              High &ge; {summary.risk_threshold_high.toFixed(2)} · Medium &ge;{" "}
              {summary.risk_threshold_medium.toFixed(2)} · Low &lt;{" "}
              {summary.risk_threshold_medium.toFixed(2)}. These are model
              outputs, not guarantees.
            </div>
          </div>
        </GlassPanel>
      </div>

      {/* Downloads */}
      <div
        data-testid="batch-downloads"
        className="mb-6 p-4 rounded-xl bg-navy-950/70 border border-navy-800/70"
      >
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm text-navy-300 flex items-center gap-2">
            <Download className="w-4 h-4 text-cyan-400" aria-hidden="true" />
            Downloads
          </span>
          <button
            type="button"
            data-testid="batch-download-combined"
            disabled={downloading !== null}
            onClick={() => download("combined", "combined")}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-60 text-navy-950 text-sm font-medium transition-colors"
          >
            <FileDown className="w-4 h-4" aria-hidden="true" />
            Combined CSV
          </button>
          <button
            type="button"
            data-testid="batch-download-summary"
            disabled={downloading !== null}
            onClick={() => download("summary", "summary")}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-navy-800 hover:bg-navy-700 disabled:opacity-60 text-navy-100 text-sm border border-navy-700 transition-colors"
          >
            <FileDown className="w-4 h-4" aria-hidden="true" />
            Batch summary CSV
          </button>
          <button
            type="button"
            data-testid="batch-download-failures"
            disabled={downloading !== null}
            onClick={() => download("failures", "failures")}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-navy-800 hover:bg-navy-700 disabled:opacity-60 text-navy-100 text-sm border border-navy-700 transition-colors"
          >
            <FileDown className="w-4 h-4" aria-hidden="true" />
            Failed rows CSV ({summary.rows_rejected + summary.rows_failed})
          </button>
          <span className="text-xs text-navy-600 ml-auto flex items-center gap-1">
            <Cpu className="w-3.5 h-3.5" aria-hidden="true" />
            {summary.model_version}
          </span>
        </div>
        {downloadError && (
          <p
            data-testid="batch-download-error"
            className="mt-3 text-sm text-red-300"
            role="alert"
          >
            {downloadError}
          </p>
        )}
      </div>

      {/* Per-file stats */}
      <SectionDivider label="Per-file results" />
      <div className="overflow-x-auto mb-2">
        <table
          data-testid="batch-file-stats"
          className="w-full text-sm min-w-[640px]"
        >
          <thead>
            <tr className="text-left text-navy-500 text-xs uppercase tracking-wider">
              <th className="py-2 pr-4 font-medium">File</th>
              <th className="py-2 pr-4 font-medium">Status</th>
              <th className="py-2 pr-4 font-medium text-right">Rows</th>
              <th className="py-2 pr-4 font-medium text-right">Rejected</th>
              <th className="py-2 pr-4 font-medium text-right">Delayed</th>
              <th className="py-2 pr-4 font-medium text-right">On time</th>
              <th className="py-2 pr-4 font-medium text-right">Avg P</th>
              <th className="py-2 font-medium text-right">Download</th>
            </tr>
          </thead>
          <tbody>
            {job.files.map((f) => (
              <tr
                key={f.file_id}
                data-testid="batch-file-stat"
                data-status={f.status}
                className="border-t border-navy-800/70 text-navy-200"
              >
                <td className="py-2.5 pr-4 max-w-[240px]">
                  <span className="block truncate" title={f.name}>
                    {f.name}
                  </span>
                  {f.error && (
                    <span
                      data-testid="batch-file-error"
                      className="block text-xs text-red-300 mt-0.5 break-words"
                    >
                      {f.error.code}: {f.error.detail}
                    </span>
                  )}
                </td>
                <td className="py-2.5 pr-4">
                  <StatusBadge status={f.status} />
                </td>
                <td className="py-2.5 pr-4 text-right">
                  {f.rows_total ?? "—"}
                </td>
                <td className="py-2.5 pr-4 text-right">
                  {f.stats ? f.stats.rows_rejected : "—"}
                </td>
                <td className="py-2.5 pr-4 text-right">
                  {f.stats ? f.stats.delayed : "—"}
                </td>
                <td className="py-2.5 pr-4 text-right">
                  {f.stats ? f.stats.on_time : "—"}
                </td>
                <td className="py-2.5 pr-4 text-right">
                  {f.stats && f.stats.average_probability !== null
                    ? `${(f.stats.average_probability * 100).toFixed(1)}%`
                    : "—"}
                </td>
                <td className="py-2.5 text-right">
                  {f.status === "completed" && (
                    <button
                      type="button"
                      data-testid={`batch-file-download-${f.file_id}`}
                      disabled={downloading !== null}
                      onClick={() => download(`file-${f.file_id}`, f.file_id)}
                      className="px-2.5 py-1.5 rounded border border-navy-700 text-xs text-navy-200 hover:border-cyan-500 hover:text-cyan-300 disabled:opacity-60 transition-colors"
                    >
                      CSV
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Row-level failure ledger */}
      <SectionDivider label="Rejected rows" />
      <div data-testid="batch-failures" className="mb-2">
        {summary.rows_rejected === 0 && summary.rows_failed === 0 ? (
          <p className="text-sm text-green-300 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" aria-hidden="true" />
            Every row passed validation.
          </p>
        ) : loading ? (
          <LoadingSkeleton rows={3} />
        ) : error ? (
          <p className="text-sm text-red-300" role="alert">
            {error}
          </p>
        ) : (
          <>
            <p className="text-xs text-navy-500 mb-3">
              Showing the first {data?.failures.length ?? 0} of{" "}
              {data?.failures_total ?? 0} rejected row
              {(data?.failures_total ?? 0) === 1 ? "" : "s"}
              {(data?.failures_truncated ?? false) &&
                " — download the failed rows CSV for the complete ledger"}.
            </p>
            <ul className="space-y-2">
              {(data?.failures || []).map((f, i) => (
                <li
                  key={`${f.file_id}-${f.row_number}-${i}`}
                  className="p-3 rounded-lg bg-navy-950/70 border border-navy-800/70 text-sm"
                >
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span className="text-navy-100 font-medium">
                      {f.file_name}
                    </span>
                    <span className="text-navy-500">row {f.row_number}</span>
                    <span className="text-cyan-400">{f.column}</span>
                    <span className="px-2 py-0.5 rounded bg-red-500/15 text-red-300 text-xs">
                      {f.error_code}
                    </span>
                  </div>
                  <p className="text-navy-400 text-xs mt-1">{f.error_detail}</p>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      {/* Prediction rows */}
      <SectionDivider label="Prediction rows" />
      <div className="overflow-x-auto mb-3">
        <table
          data-testid="batch-results-table"
          className="w-full text-sm min-w-[720px]"
        >
          <thead>
            <tr className="text-left text-navy-500 text-xs uppercase tracking-wider">
              <th className="py-2 pr-4 font-medium">#</th>
              <th className="py-2 pr-4 font-medium">Flight</th>
              <th className="py-2 pr-4 font-medium">Route</th>
              <th className="py-2 pr-4 font-medium">Date</th>
              <th className="py-2 pr-4 font-medium">Prediction</th>
              <th className="py-2 pr-4 font-medium text-right">Probability</th>
              <th className="py-2 font-medium">Risk</th>
            </tr>
          </thead>
          <tbody>
            {loading && !data && (
              <tr>
                <td colSpan={7} className="py-4">
                  <LoadingSkeleton rows={3} />
                </td>
              </tr>
            )}
            {!loading && error && (
              <tr>
                <td colSpan={7} className="py-4 text-red-300 text-sm">
                  {error}
                </td>
              </tr>
            )}
            {(data?.rows || []).map((row) => (
              <tr
                key={`${row.file_id}-${row.row_number}`}
                data-testid="batch-result-row"
                className="border-t border-navy-800/70 text-navy-200"
              >
                <td className="py-2.5 pr-4 text-navy-500">{row.row_number}</td>
                <td className="py-2.5 pr-4 text-navy-100">
                  {row.flight_number || row.carrier}
                </td>
                <td className="py-2.5 pr-4">
                  {row.origin} → {row.destination}
                </td>
                <td className="py-2.5 pr-4">{row.date}</td>
                <td className="py-2.5 pr-4">
                  <span
                    className={
                      row.predicted_class === 1
                        ? "text-red-300"
                        : "text-green-300"
                    }
                  >
                    {row.predicted_label}
                  </span>
                </td>
                <td className="py-2.5 pr-4 text-right font-medium text-navy-100">
                  {(row.probability * 100).toFixed(1)}%
                </td>
                <td className="py-2.5">
                  <span
                    className="px-2 py-0.5 rounded text-xs"
                    style={{
                      backgroundColor: `${RISK_COLORS[row.risk_level]}22`,
                      color: RISK_COLORS[row.risk_level],
                    }}
                  >
                    {row.risk_level}
                  </span>
                </td>
              </tr>
            ))}
            {!loading && !error && (data?.rows.length ?? 0) === 0 && (
              <tr>
                <td colSpan={7} className="py-4 text-navy-500 text-sm">
                  No prediction rows.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {(data?.pages ?? 1) > 1 && (
        <div className="flex items-center justify-between gap-3">
          <button
            type="button"
            data-testid="batch-page-prev"
            disabled={page <= 1 || loading}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="inline-flex items-center gap-1 px-3 py-2 rounded-lg border border-navy-700 text-sm text-navy-200 hover:border-cyan-500 disabled:opacity-40 transition-colors"
          >
            <ChevronLeft className="w-4 h-4" aria-hidden="true" />
            Previous
          </button>
          <span className="text-xs text-navy-500" aria-live="polite">
            Page {data?.page ?? page} of {data?.pages ?? 1} ·{" "}
            {(data?.rows_total ?? 0).toLocaleString()} rows
          </span>
          <button
            type="button"
            data-testid="batch-page-next"
            disabled={page >= (data?.pages ?? 1) || loading}
            onClick={() => setPage((p) => p + 1)}
            className="inline-flex items-center gap-1 px-3 py-2 rounded-lg border border-navy-700 text-sm text-navy-200 hover:border-cyan-500 disabled:opacity-40 transition-colors"
          >
            Next
            <ChevronRight className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>
      )}

      {/* Honest-model note */}
      <div className="mt-8 flex items-start gap-3 p-4 rounded-lg bg-navy-950/70 border border-navy-800/70 text-xs text-navy-500">
        <Layers className="w-4 h-4 shrink-0 mt-0.5 text-cyan-500" aria-hidden="true" />
        <span>
          Every probability above was produced by the loaded ML model
          ({summary.model_version}) through the same pipeline as the single
          prediction screen. Probabilities are uncalibrated model outputs and
          must not be read as certainty; rows rejected during validation were
          never scored.
        </span>
      </div>
    </motion.div>
  );
}
