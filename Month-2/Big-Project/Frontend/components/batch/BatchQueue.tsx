"use client";

/*!
 * AeroDelay AI - Batch prediction: drag & drop queue.
 *
 * The queue performs FAST client-side pre-checks (extension, size, count,
 * total bytes, UTF-16 BOM, obvious duplicates) so the user gets instant
 * feedback. It is NOT the validator: the backend re-checks everything and
 * is authoritative (encoding, headers, schema, exact row counts). Client
 * checks only ever reject a file earlier than the server would.
 */

import { useCallback, useRef, useState } from "react";
import { motion } from "motion/react";
import {
  Upload,
  FileSpreadsheet,
  X,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";
import { useReducedMotion } from "../../hooks/use-reduced-motion";

/* Mirrors batch_prediction.LIMITS. The backend enforces these; these
   constants only power the instant pre-checks shown before upload. */
export const BATCH_LIMITS = {
  max_files: 200,
  max_file_bytes: 10 * 1024 * 1024, // 10 MB
  max_batch_bytes: 100 * 1024 * 1024, // 100 MB
  max_rows_per_file: 50_000,
  max_total_rows: 500_000,
};

export const CANONICAL_FIELDS = [
  { key: "flight_number", label: "Flight number", required: true },
  { key: "carrier", label: "Carrier", required: false },
  { key: "origin", label: "Origin", required: true },
  { key: "destination", label: "Destination", required: true },
  { key: "date", label: "Date", required: true },
] as const;

export type QueuedFile = {
  key: string;
  file: File;
  /** Client-side pre-check failure; null means "will be sent to the server". */
  error: string | null;
  encodingWarning: string | null;
  /** Name of an earlier queued file with identical name + size. */
  duplicateOf: string | null;
};

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/* ── Client-side pre-checks ─────────────────────────────────────────────── */

function precheck(file: File, existing: QueuedFile[]): string | null {
  if (!file.name.toLowerCase().endsWith(".csv")) {
    return "Not a .csv file. Only CSV uploads are accepted.";
  }
  if (file.size === 0) {
    return "File is empty (0 bytes).";
  }
  if (file.size > BATCH_LIMITS.max_file_bytes) {
    return `Exceeds the ${
      BATCH_LIMITS.max_file_bytes / (1024 * 1024)
    } MB per-file limit.`;
  }
  const total =
    existing.reduce((sum, q) => sum + q.file.size, 0) + file.size;
  if (total > BATCH_LIMITS.max_batch_bytes) {
    return `Would push the batch over the ${
      BATCH_LIMITS.max_batch_bytes / (1024 * 1024)
    } MB total limit.`;
  }
  return null;
}

async function sniffUtf16(file: File): Promise<boolean> {
  try {
    const head = new Uint8Array(await file.slice(0, 4).arrayBuffer());
    return (
      (head[0] === 0xff && head[1] === 0xfe) ||
      (head[0] === 0xfe && head[1] === 0xff)
    );
  } catch {
    return false;
  }
}

let keySeq = 0;

/** Add a batch of picked/dropped files, applying the pre-checks. */
export async function buildQueue(
  incoming: File[],
  existing: QueuedFile[],
): Promise<QueuedFile[]> {
  const next = [...existing];
  for (const file of incoming) {
    if (next.length >= BATCH_LIMITS.max_files) {
      next.push({
        key: `q${keySeq++}`,
        file,
        error: `Limit of ${BATCH_LIMITS.max_files} files per batch reached.`,
        encodingWarning: null,
        duplicateOf: null,
      });
      continue;
    }
    const error = precheck(file, next);
    const duplicate = next.find(
      (q) =>
        !q.error &&
        q.file.name === file.name &&
        q.file.size === file.size,
    );
    const isUtf16 = error ? false : await sniffUtf16(file);
    next.push({
      key: `q${keySeq++}`,
      file,
      error: isUtf16
        ? "UTF-16 encoded. Save it as UTF-8 (or CP1252) CSV and retry."
        : error,
      encodingWarning: null,
      duplicateOf: duplicate ? duplicate.file.name : null,
    });
  }
  return next;
}

/* ── Header reader (feeds the optional column-mapping table) ────────────── */

function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQuotes) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          cur += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        cur += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      out.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  out.push(cur);
  return out.map((s) => s.trim());
}

/** Read only the header line of a file (never the whole CSV). */
export async function readCsvHeader(file: File): Promise<string[]> {
  try {
    const text = await file.slice(0, 64 * 1024).text();
    const firstLine = text.split(/\r?\n/, 1)[0] || "";
    const cols = splitCsvLine(firstLine.replace(/^\ufeff/, ""));
    return cols.filter((c) => c.length > 0);
  } catch {
    return [];
  }
}

/* ── Dropzone ───────────────────────────────────────────────────────────── */

export function BatchDropzone({
  disabled,
  onAdd,
}: {
  disabled: boolean;
  onAdd: (files: File[]) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const { reduced } = useReducedMotion();

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragging(false);
      if (disabled) return;
      const dropped = Array.from(e.dataTransfer.files || []);
      if (dropped.length) onAdd(dropped);
    },
    [disabled, onAdd],
  );

  return (
    <div
      data-testid="batch-dropzone"
      data-dragging={dragging ? "true" : "false"}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`rounded-xl border-2 border-dashed transition-colors duration-200 px-4 py-8 sm:py-10 text-center ${
        dragging
          ? "border-cyan-400 bg-cyan-500/10"
          : "border-navy-700 bg-navy-950/60 hover:border-cyan-600/70"
      } ${disabled ? "opacity-60 pointer-events-none" : ""}`}
    >
      <motion.div
        initial={reduced ? false : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="flex flex-col items-center gap-3"
      >
        <span className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-cyan-500/10 border border-cyan-500/30">
          <Upload className="w-6 h-6 text-cyan-400" aria-hidden="true" />
        </span>
        <div>
          <p className="text-navy-100 font-medium">
            Drag &amp; drop CSV files here
          </p>
          <p className="text-navy-500 text-xs mt-1">
            Up to {BATCH_LIMITS.max_files} files ·{" "}
            {BATCH_LIMITS.max_file_bytes / (1024 * 1024)} MB each ·{" "}
            {BATCH_LIMITS.max_batch_bytes / (1024 * 1024)} MB total
          </p>
        </div>
        <button
          type="button"
          data-testid="batch-browse"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
          className="px-5 py-2.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-60 text-navy-950 text-sm font-medium transition-colors"
        >
          Choose CSV files
        </button>
        <input
          ref={inputRef}
          data-testid="batch-file-input"
          type="file"
          multiple
          accept=".csv,text/csv"
          className="sr-only"
          aria-label="Choose CSV files to upload"
          onChange={(e) => {
            const picked = Array.from(e.target.files || []);
            if (picked.length) onAdd(picked);
            e.target.value = "";
          }}
        />
      </motion.div>
    </div>
  );
}

/* ── Queued file rows ───────────────────────────────────────────────────── */

export function FileQueue({
  files,
  onRemove,
  onClear,
}: {
  files: QueuedFile[];
  onRemove: (key: string) => void;
  onClear: () => void;
}) {
  const { reduced } = useReducedMotion();
  const sendable = files.filter((f) => !f.error);
  const blocked = files.length - sendable.length;

  return (
    <div data-testid="batch-queue" className="mt-4">
      <div className="flex items-center justify-between gap-3 mb-3">
        <p
          data-testid="batch-queue-count"
          className="text-sm text-navy-300"
          aria-live="polite"
        >
          <span className="text-navy-100 font-medium">{files.length}</span>{" "}
          file{files.length === 1 ? "" : "s"} queued ·{" "}
          <span className="text-navy-100 font-medium">{sendable.length}</span>{" "}
          ready to send
          {blocked > 0 && (
            <span className="text-red-400"> · {blocked} blocked</span>
          )}
        </p>
        {files.length > 0 && (
          <button
            type="button"
            data-testid="batch-clear"
            onClick={onClear}
            className="text-xs text-navy-400 hover:text-navy-200 underline underline-offset-2"
          >
            Clear all
          </button>
        )}
      </div>

      <ul className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
        {files.map((q, index) => (
          <motion.li
            key={q.key}
            initial={reduced ? false : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, delay: Math.min(index * 0.02, 0.3) }}
            data-testid="batch-file-row"
            data-state={q.error ? "error" : "ready"}
            className="flex items-start gap-3 p-3 rounded-lg border bg-navy-950/70"
            style={{
              borderColor: q.error ? "rgba(239,68,68,.4)" : "rgba(30,41,59,.9)",
            }}
          >
            <span
              className={`mt-0.5 shrink-0 ${
                q.error ? "text-red-400" : "text-cyan-400"
              }`}
              aria-hidden="true"
            >
              {q.error ? (
                <AlertTriangle className="w-4 h-4" />
              ) : (
                <FileSpreadsheet className="w-4 h-4" />
              )}
            </span>

            <div className="flex-1 min-w-0">
              <p className="text-sm text-navy-100 truncate" title={q.file.name}>
                {q.file.name}
              </p>
              <p className="text-xs text-navy-500 mt-0.5">
                {formatBytes(q.file.size)}
                {!q.error && (
                  <>
                    {" · "}
                    <span className="text-green-400 inline-flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" aria-hidden="true" />
                      ready
                    </span>
                  </>
                )}
              </p>
              {q.error && (
                <p className="text-xs text-red-300 mt-1" role="alert">
                  {q.error}
                </p>
              )}
              {q.duplicateOf && (
                <p className="text-xs text-yellow-400/90 mt-1">
                  Possible duplicate of &ldquo;{q.duplicateOf}&rdquo; — both are
                  kept and reported by the server.
                </p>
              )}
            </div>

            <button
              type="button"
              data-testid="batch-file-remove"
              aria-label={`Remove ${q.file.name}`}
              onClick={() => onRemove(q.key)}
              className="shrink-0 p-2 rounded-lg text-navy-400 hover:text-red-300 hover:bg-red-500/10 transition-colors"
            >
              <X className="w-4 h-4" aria-hidden="true" />
            </button>
          </motion.li>
        ))}
      </ul>
    </div>
  );
}
