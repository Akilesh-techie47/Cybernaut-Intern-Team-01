"use client";

/*!
 * Next.js - AeroDelay AI Premium Frontend
 * Batch CSV prediction screen (bulk workflow).
 *
 * Flow: pick CSVs -> client pre-checks -> optional column mapping ->
 * POST /api/v1/predict/batch -> poll job status -> results + downloads.
 *
 * Every prediction shown here comes from the real ML model served by the
 * backend. If the model cannot run, the backend answers HTTP 550
 * model_unavailable and this screen says so explicitly; no heuristic or
 * dummy score is ever displayed.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  FileSpreadsheet,
  FileDown,
  Loader2,
  Play,
  RotateCcw,
  Table2,
  Trash2,
  XCircle,
} from "lucide-react";
import {
  GlassPanel,
  SectionDivider,
  StatusBadge,
  LoadingSkeleton,
} from "../../components/ui";
import {
  BatchDropzone,
  FileQueue,
  BATCH_LIMITS,
  CANONICAL_FIELDS,
  buildQueue,
  formatBytes,
  readCsvHeader,
  type QueuedFile,
} from "../../components/batch/BatchQueue";
import { BatchResults } from "../../components/batch/BatchResults";
import {
  api,
  ApiRequestError,
  describeApiError,
  type BatchAllRejectedResponse,
  type BatchJobStatus,
} from "../../lib/api";

type Phase = "idle" | "uploading" | "running" | "done";

const TERMINAL = new Set([
  "completed",
  "completed_with_errors",
  "failed",
  "cancelled",
]);

function saveBlob(blob: Blob, filename: string) {
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

export default function BatchPage() {
  const [queued, setQueued] = useState<QueuedFile[]>([]);
  const [phase, setPhase] = useState<Phase>("idle");
  const [job, setJob] = useState<BatchJobStatus | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [allRejected, setAllRejected] = useState<
    BatchAllRejectedResponse["files"] | null
  >(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [headers, setHeaders] = useState<string[]>([]);
  const [templateError, setTemplateError] = useState<string | null>(null);
  const [templateBusy, setTemplateBusy] = useState(false);

  const sendable = useMemo(
    () => queued.filter((q) => !q.error),
    [queued],
  );
  const busy = phase === "uploading" || phase === "running";

  /* Mirror of `queued` so rapid successive adds never read a stale list. */
  const queueRef = useRef<QueuedFile[]>([]);
  const addChain = useRef<Promise<void>>(Promise.resolve());
  useEffect(() => {
    queueRef.current = queued;
  }, [queued]);

  /* Read the header of the first sendable file to offer column mapping. */
  useEffect(() => {
    let cancelled = false;
    const first = sendable[0];
    if (!first) {
      setHeaders([]);
      return;
    }
    readCsvHeader(first.file)
      .then((cols) => {
        if (!cancelled) setHeaders(cols);
      })
      .catch(() => {
        if (!cancelled) setHeaders([]);
      });
    return () => {
      cancelled = true;
    };
  }, [sendable]);

  /* Poll job status while a batch is running. */
  useEffect(() => {
    if (phase !== "running" || !job) return;
    let cancelled = false;
    let timer: number | undefined;
    const jobId = job.job_id;

    const tick = async () => {
      if (cancelled) return;
      try {
        const status = await api.batchStatus(jobId);
        if (cancelled) return;
        setJob(status);
        if (TERMINAL.has(status.status)) {
          setPhase("done");
          return;
        }
      } catch (err) {
        if (!cancelled) {
          setUploadError(describeApiError(err));
          setPhase("idle");
        }
        return;
      }
      timer = window.setTimeout(tick, 700);
    };

    timer = window.setTimeout(tick, 600);
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, job?.job_id]);

  function addFiles(incoming: File[]): Promise<void> {
    /* Serialise adds so overlapping drops/picks never lose entries. */
    addChain.current = addChain.current
      .then(async () => {
        setUploadError(null);
        setAllRejected(null);
        const next = await buildQueue(incoming, queueRef.current);
        queueRef.current = next;
        setQueued(next);
      })
      .catch(() => undefined);
    return addChain.current;
  }

  function removeFile(key: string) {
    setQueued((prev) => prev.filter((q) => q.key !== key));
  }

  function clearFiles() {
    setQueued([]);
    setMapping({});
    setHeaders([]);
  }

  async function runBatch(e: React.FormEvent) {
    e.preventDefault();
    if (!sendable.length) {
      setUploadError("Add at least one valid CSV file before running.");
      return;
    }
    setUploadError(null);
    setAllRejected(null);
    setPhase("uploading");
    try {
      const created = await api.batchCreate(
        sendable.map((q) => q.file),
        mapping,
      );
      setJob(created);
      setPhase("running");
    } catch (err) {
      const files =
        err instanceof ApiRequestError
          ? (err as ApiRequestError & {
              files?: BatchAllRejectedResponse["files"];
            }).files
          : undefined;
      if (
        err instanceof ApiRequestError &&
        err.status === 422 &&
        files &&
        files.length
      ) {
        setAllRejected(files);
      } else {
        setUploadError(describeApiError(err));
      }
      setPhase("idle");
    }
  }

  async function cancelBatch() {
    if (job) {
      try {
        await api.batchDelete(job.job_id);
      } catch {
        /* job may already be gone */
      }
    }
    resetAll();
  }

  function resetAll() {
    setJob(null);
    setPhase("idle");
    setUploadError(null);
    setAllRejected(null);
    setMapping({});
    setHeaders([]);
    setQueued([]);
  }

  async function downloadTemplate(style: "canonical" | "bts") {
    setTemplateError(null);
    setTemplateBusy(true);
    try {
      const { blob, filename } = await api.batchTemplate(style);
      saveBlob(blob, filename);
    } catch (err) {
      setTemplateError(describeApiError(err));
    } finally {
      setTemplateBusy(false);
    }
  }

  const progress = job?.progress;
  const summary = job?.summary;

  return (
    <div className="flex-1 px-4 py-8">
      <div className="max-w-6xl mx-auto">
        {/* Heading */}
        <div className="mb-6">
          <h1 className="text-2xl md:text-3xl font-display-bold text-navy-100">
            Batch Prediction
          </h1>
          <p className="text-navy-400 text-sm mt-1">
            Upload up to {BATCH_LIMITS.max_files} CSV files and score every row
            with the real ML model. Invalid rows are reported, never silently
            dropped.
          </p>
        </div>

        {/* ── Stage: results ─────────────────────────────────────────── */}
        {phase === "done" && job && (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
              <p
                data-testid="batch-job-status"
                data-status={job.status}
                className="text-sm text-navy-300 flex items-center gap-2"
              >
                <StatusBadge status={job.status} size="md" />
                <span className="text-navy-500">
                  job {job.job_id.slice(0, 8)} · expires{" "}
                  {new Date(job.expires_at * 1000).toLocaleTimeString()}
                </span>
              </p>
              <button
                type="button"
                data-testid="batch-reset"
                onClick={resetAll}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-navy-950 text-sm font-medium transition-colors"
              >
                <RotateCcw className="w-4 h-4" aria-hidden="true" />
                Start another batch
              </button>
            </div>
            <BatchResults job={job} />
          </>
        )}

        {/* ── Stage: uploading / running ─────────────────────────────── */}
        {(phase === "uploading" || phase === "running") && job && (
          <GlassPanel>
            <div data-testid="batch-progress">
            <div className="flex items-center gap-3 mb-4">
              <Loader2
                className="w-5 h-5 animate-spin text-cyan-400"
                aria-hidden="true"
              />
              <div className="min-w-0">
                <p className="text-navy-100 font-medium">
                  {phase === "uploading"
                    ? "Uploading and validating files…"
                    : job.status === "processing"
                      ? "Running model inference…"
                      : "Preparing batch…"}
                </p>
                <p className="text-navy-500 text-xs truncate">
                  job {job.job_id.slice(0, 8)} · {job.model_version}
                </p>
              </div>
            </div>

            {progress && (
              <div className="mb-5">
                <div className="flex items-center justify-between text-xs text-navy-400 mb-2">
                  <span>
                    {progress.files_done}/{progress.files_total} files ·{" "}
                    {progress.rows_processed.toLocaleString()}/
                    {progress.rows_total.toLocaleString()} rows
                  </span>
                  <span className="text-navy-100 font-medium">
                    {progress.percent}%
                  </span>
                </div>
                <div
                  className="h-3 bg-navy-950 rounded-full overflow-hidden border border-navy-800"
                  role="progressbar"
                  aria-valuenow={progress.percent}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div
                    className="h-full bg-gradient-to-r from-cyan-600 to-cyan-400 transition-all duration-300"
                    style={{ width: `${progress.percent}%` }}
                  />
                </div>
              </div>
            )}

            <ul className="space-y-2 max-h-[320px] overflow-y-auto pr-1">
              {job.files.map((f) => (
                <li
                  key={f.file_id}
                  data-testid="batch-status-file"
                  data-status={f.status}
                  className="flex items-center gap-3 p-3 rounded-lg bg-navy-950/70 border border-navy-800/70"
                >
                  <span className="text-navy-400 shrink-0" aria-hidden="true">
                    <FileSpreadsheet className="w-4 h-4" />
                  </span>
                  <span className="flex-1 min-w-0 text-sm">
                    <span className="block truncate text-navy-100">
                      {f.name}
                    </span>
                    {f.rows_total !== null && (
                      <span className="text-xs text-navy-500">
                        {f.rows_total.toLocaleString()} rows ·{" "}
                        {formatBytes(f.size_bytes)}
                      </span>
                    )}
                  </span>
                  {f.error && (
                    <span className="text-xs text-red-300 max-w-[45%] truncate text-right">
                      {f.error.detail}
                    </span>
                  )}
                  <StatusBadge status={f.status} />
                </li>
              ))}
            </ul>

            {job.warnings.length > 0 && (
              <ul className="mt-4 space-y-1 text-xs text-navy-500">
                {job.warnings.map((w, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <AlertTriangle
                      className="w-3.5 h-3.5 shrink-0 mt-0.5 text-yellow-500/80"
                      aria-hidden="true"
                    />
                    <span>{w}</span>
                  </li>
                ))}
              </ul>
            )}

            <div className="mt-5 flex flex-wrap items-center gap-3">
              <button
                type="button"
                data-testid="batch-cancel"
                onClick={cancelBatch}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-red-500/40 text-red-300 hover:bg-red-500/10 text-sm transition-colors"
              >
                <Trash2 className="w-4 h-4" aria-hidden="true" />
                Cancel &amp; delete job
              </button>
              <span className="text-xs text-navy-600">
                Results are downloadable once the job finishes.
              </span>
            </div>
            </div>
          </GlassPanel>
        )}

        {(phase === "uploading" || phase === "running") && !job && (
          <GlassPanel>
            <div data-testid="batch-progress">
              <LoadingSkeleton rows={4} />
            </div>
          </GlassPanel>
        )}

        {/* ── Stage: upload ──────────────────────────────────────────── */}
        {phase === "idle" && (
          <>
            {/* Errors */}
            {uploadError && (
              <div
                data-testid="batch-upload-error"
                className="mb-6 flex items-start gap-3 p-4 rounded-lg bg-red-500/10 border border-red-500/40 text-red-300 text-sm"
                role="alert"
              >
                <AlertTriangle
                  className="w-5 h-5 shrink-0 mt-0.5"
                  aria-hidden="true"
                />
                <span>{uploadError}</span>
              </div>
            )}

            {allRejected && (
              <div
                data-testid="batch-all-rejected"
                className="mb-6 p-4 rounded-lg bg-red-500/10 border border-red-500/40"
                role="alert"
              >
                <p className="text-red-200 text-sm font-medium flex items-center gap-2">
                  <XCircle className="w-4 h-4" aria-hidden="true" />
                  Every uploaded file failed validation. Fix the files below
                  and try again.
                </p>
                <ul className="mt-3 space-y-2">
                  {allRejected.map((f, i) => (
                    <li
                      key={`${f.name}-${i}`}
                      data-testid="batch-rejected-file"
                      className="text-sm bg-navy-950/70 border border-red-500/25 rounded p-3"
                    >
                      <span className="text-navy-100 font-medium">
                        {f.name}
                      </span>
                      <span className="block text-red-200/90 text-xs mt-1">
                        {f.error?.code ? `${f.error.code}: ` : ""}
                        {f.error?.detail || "Validation failed."}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <form onSubmit={runBatch}>
              <GlassPanel>
                <BatchDropzone disabled={busy} onAdd={addFiles} />
                {queued.length > 0 && (
                  <FileQueue
                    files={queued}
                    onRemove={removeFile}
                    onClear={clearFiles}
                  />
                )}

                {/* Template + schema help */}
                <div className="mt-6 pt-5 border-t border-navy-800/70">
                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      data-testid="batch-template"
                      disabled={templateBusy}
                      onClick={() => downloadTemplate("canonical")}
                      className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-navy-700 text-sm text-navy-100 hover:border-cyan-500 hover:text-cyan-300 disabled:opacity-60 transition-colors"
                    >
                      <FileDown className="w-4 h-4" aria-hidden="true" />
                      CSV template
                    </button>
                    <button
                      type="button"
                      data-testid="batch-template-bts"
                      disabled={templateBusy}
                      onClick={() => downloadTemplate("bts")}
                      className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-navy-700 text-sm text-navy-100 hover:border-cyan-500 hover:text-cyan-300 disabled:opacity-60 transition-colors"
                    >
                      <FileDown className="w-4 h-4" aria-hidden="true" />
                      BTS-style template
                    </button>
                    <span className="text-xs text-navy-600">
                      Accepts UTF-8 (with or without BOM) and CP1252 CSV.
                    </span>
                  </div>
                  {templateError && (
                    <p className="mt-2 text-xs text-red-300" role="alert">
                      {templateError}
                    </p>
                  )}

                  <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs text-navy-400">
                    <div>
                      <p className="text-navy-300 font-medium mb-1">
                        Required columns
                      </p>
                      <p>
                        <code className="text-cyan-400">flight_number</code>,{" "}
                        <code className="text-cyan-400">origin</code>,{" "}
                        <code className="text-cyan-400">destination</code>,{" "}
                        <code className="text-cyan-400">date</code>
                        {" "}(<code className="text-cyan-400">carrier</code>{" "}
                        optional). Common aliases and BTS{" "}
                        <code className="text-cyan-400">Year/Month/DayOfMonth</code>{" "}
                        splits are recognised automatically.
                      </p>
                    </div>
                    <div>
                      <p className="text-navy-300 font-medium mb-1">
                        Supported values
                      </p>
                      <p>
                        Carriers AA, DL, UA, B6, WN, F9, AS · airports JFK,
                        LAX, SFO, ORD, SEA. Label/outcome columns (e.g.{" "}
                        <code className="text-cyan-400">Depdel15</code>) are
                        excluded from the model inputs.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Column mapping */}
                {headers.length > 0 && (
                  <div className="mt-6 pt-5 border-t border-navy-800/70">
                    <div className="flex items-center gap-2 mb-3">
                      <Table2
                        className="w-4 h-4 text-cyan-400"
                        aria-hidden="true"
                      />
                      <h2 className="text-sm font-medium text-navy-200">
                        Column mapping
                      </h2>
                      <span className="text-xs text-navy-600">
                        (optional, applies to every file in this batch)
                      </span>
                    </div>

                    <div className="flex flex-wrap gap-1.5 mb-4">
                      {headers.map((h) => (
                        <span
                          key={h}
                          className="px-2 py-1 rounded bg-navy-950 border border-navy-800 text-[11px] text-navy-300"
                        >
                          {h}
                        </span>
                      ))}
                    </div>

                    <div
                      data-testid="batch-mapping"
                      className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3"
                    >
                      {CANONICAL_FIELDS.map((field) => (
                        <label key={field.key} className="block">
                          <span className="block text-xs text-navy-400 mb-1">
                            {field.label}
                            {field.required ? (
                              <span className="text-cyan-500"> *</span>
                            ) : (
                              <span className="text-navy-600"> (optional)</span>
                            )}
                          </span>
                          <select
                            data-testid={`batch-map-${field.key}`}
                            value={mapping[field.key] || ""}
                            onChange={(e) => {
                              const value = e.target.value;
                              setMapping((prev) => {
                                const next = { ...prev };
                                if (value) next[field.key] = value;
                                else delete next[field.key];
                                return next;
                              });
                            }}
                            className="w-full bg-navy-900 border border-navy-700 rounded-lg px-3 py-2.5 text-sm text-navy-100 focus:outline-none focus:border-cyan-500 transition-colors"
                          >
                            <option value="">Auto-detect</option>
                            {headers.map((h) => (
                              <option key={h} value={h}>
                                {h}
                              </option>
                            ))}
                          </select>
                        </label>
                      ))}
                    </div>
                    <p className="text-[11px] text-navy-600 mt-3">
                      Auto-detect resolves aliases per file. A manual mapping
                      is applied to all files, so a file missing that column
                      will be rejected with a clear message.
                    </p>
                  </div>
                )}

                {/* Run */}
                <div className="mt-6 pt-5 border-t border-navy-800/70 flex flex-col sm:flex-row sm:items-center gap-4">
                  <button
                    type="submit"
                    data-testid="batch-run"
                    disabled={sendable.length === 0}
                    className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed text-navy-950 font-medium transition-all shadow-lg shadow-cyan-500/20"
                  >
                    <Play className="w-4 h-4" aria-hidden="true" />
                    {`Run prediction on ${sendable.length} file${sendable.length === 1 ? "" : "s"}`}
                  </button>
                  <p className="text-xs text-navy-600 flex items-center gap-1.5">
                    <Cpu className="w-3.5 h-3.5" aria-hidden="true" />
                    Scores come from the loaded ML model only — no heuristic
                    or dummy predictions.
                  </p>
                </div>
              </GlassPanel>
            </form>

            {/* Limits */}
            <SectionDivider label="Limits" className="mt-8" />
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-center">
              {[
                { k: "Files / batch", v: String(BATCH_LIMITS.max_files) },
                { k: "Per file", v: `${BATCH_LIMITS.max_file_bytes / 1048576} MB` },
                { k: "Batch total", v: `${BATCH_LIMITS.max_batch_bytes / 1048576} MB` },
                { k: "Rows / file", v: BATCH_LIMITS.max_rows_per_file.toLocaleString() },
                { k: "Rows / batch", v: BATCH_LIMITS.max_total_rows.toLocaleString() },
                { k: "Job retention", v: "1 hour" },
              ].map((item) => (
                <div
                  key={item.k}
                  className="p-3 rounded-xl bg-navy-950/70 border border-navy-800/70"
                >
                  <p className="text-[11px] uppercase tracking-wider text-navy-600">
                    {item.k}
                  </p>
                  <p className="text-sm font-medium text-navy-100 mt-1">
                    {item.v}
                  </p>
                </div>
              ))}
            </div>

            {/* Honest-model note */}
            <div className="mt-6 flex items-start gap-3 p-4 rounded-lg bg-navy-950/70 border border-navy-800/70 text-xs text-navy-500">
              <CheckCircle2
                className="w-4 h-4 shrink-0 mt-0.5 text-cyan-500"
                aria-hidden="true"
              />
              <span>
                Rows that fail validation are written to a downloadable
                failure ledger with the exact column and reason; they are never
                scored or silently discarded. Duplicate files and duplicate
                rows are detected and reported rather than removed.
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
