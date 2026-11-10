/*!
 * AeroDelay AI - typed frontend API client.
 *
 * All backend communication goes through this module. The AviationStack
 * API key NEVER appears here: the browser only talks to the local FastAPI
 * backend (http://localhost:8000), which holds credentials server-side.
 */

/* Backend base URL. Override with NEXT_PUBLIC_API_BASE for other environments. */
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

/* ── Response types (mirror the FastAPI Pydantic models) ───────────────── */

export type ApiStatusResponse = {
  status: "healthy" | "degraded" | "unavailable";
  timestamp: number;
  services: Record<string, string>;
  version: string;
};

export type RiskLevel = "Low" | "Medium" | "High";

export type RiskPrediction = {
  flight_number: string;
  origin: string;
  destination: string;
  date: string;
  risk_score: number;
  risk_level: RiskLevel;
  confidence: number;
  factors: Array<{ name: string; impact: string }>;
  model_version: string;
  prediction_time_ms: number;
};

export type FlightLookupResult = {
  found: boolean;
  message?: string;
  flight_number?: string;
  airline?: string;
  flight_date?: string;
  departure?: {
    airport: string;
    iata: string;
    scheduled: string;
    actual: string;
  };
  arrival?: {
    airport: string;
    iata: string;
    scheduled: string;
    actual: string;
  };
  status?: string;
  gate?: string;
  equipment?: string;
};

export type RouteAnalytics = {
  route: string;
  on_time_pct: number;
  delayed_pct: number;
  cancelled_pct: number;
  average_delay: number;
  flights_this_month: number;
  airline_breakdown: Array<{
    airline: string;
    pct_on_time: number;
    flights: number;
  }>;
};

export type ModelInfo = {
  name: string;
  type: string;
  version: string;
  status: "healthy" | "degraded" | "unavailable";
  metrics: Record<string, number>;
  training_time_s: number;
  features: number;
  trained_on: number;
  last_checked: number;
};

export type ReferencesResponse = {
  airlines: Array<{ code: string; name: string; hub: string }>;
  airports: Array<{
    code: string;
    name: string;
    city: string;
    country: string;
  }>;
  total_airlines: number;
  total_airports: number;
};

/* ── Airport / airline search types ─────────────────────────────────────── */

export type AirportSearchResult = {
  iata: string;
  icao: string;
  name: string;
  city: string;
  country: string;
  latitude: number;
  longitude: number;
  timezone: string;
};

export type AirlineSearchResult = {
  code: string;
  name: string;
  iata: string;
  icao: string;
  country: string;
  hub: string;
};

export type AirportSearchResponse = {
  airports: AirportSearchResult[];
  total: number;
  query: string;
};

export type AirlineSearchResponse = {
  airlines: AirlineSearchResult[];
  total: number;
  query: string;
};

export type FlightLookupToPredictionResponse = {
  flight_info: FlightLookupResult;
  prediction: RiskPrediction | null;
  feature_compatibility: Record<string, unknown>;
  warnings: string[];
};

/* ── Batch prediction types ────────────────────────────────────────────── */

export type BatchFileError = { code: string; detail: string };

export type BatchRiskCounts = { Low: number; Medium: number; High: number };

export type BatchFileStats = {
  rows_predicted: number;
  rows_rejected: number;
  delayed: number;
  on_time: number;
  average_probability: number | null;
  risk_counts: BatchRiskCounts;
};

export type BatchFileStatus = {
  file_id: string;
  name: string;
  size_bytes: number;
  status:
    | "pending"
    | "validated"
    | "processing"
    | "completed"
    | "failed"
    | "rejected";
  encoding: string | null;
  rows_total: number | null;
  warnings: string[];
  error: BatchFileError | null;
  stats: BatchFileStats | null;
};

export type BatchProgress = {
  files_total: number;
  files_done: number;
  rows_total: number;
  rows_processed: number;
  percent: number;
};

export type BatchLimits = {
  max_files: number;
  max_file_bytes: number;
  max_batch_bytes: number;
  max_rows_per_file: number;
  max_total_rows: number;
  chunk_rows: number;
  job_ttl_seconds: number;
};

export type BatchSummary = {
  files_uploaded: number;
  files_rejected: number;
  files_succeeded: number;
  files_failed: number;
  rows_total: number;
  rows_predicted: number;
  rows_rejected: number;
  rows_failed: number;
  delayed: number;
  on_time: number;
  average_probability: number | null;
  risk_counts: BatchRiskCounts;
  class_threshold: number;
  risk_threshold_high: number;
  risk_threshold_medium: number;
  model_version: string;
};

export type BatchJobStatus = {
  job_id: string;
  status:
    | "queued"
    | "processing"
    | "completed"
    | "completed_with_errors"
    | "failed"
    | "cancelled";
  created_at: number;
  expires_at: number;
  model_version: string;
  limits: BatchLimits;
  progress: BatchProgress;
  files: BatchFileStatus[];
  accepted_files: number;
  rejected_files: number;
  warnings: string[];
  summary: BatchSummary | null;
  error: BatchFileError | null;
};

export type BatchRow = {
  file_id: string;
  file_name: string;
  row_number: number;
  carrier: string;
  flight_number: string;
  origin: string;
  destination: string;
  date: string;
  predicted_class: number;
  predicted_label: "Delayed" | "On time";
  probability: number;
  risk_level: RiskLevel;
  model_version: string;
};

export type BatchFailure = {
  file_id: string;
  file_name: string;
  row_number: number;
  column: string;
  error_code: string;
  error_detail: string;
};

export type BatchResults = {
  job_id: string;
  status: BatchJobStatus["status"];
  summary: BatchSummary;
  files: BatchFileStatus[];
  rows: BatchRow[];
  rows_total: number;
  page: number;
  page_size: number;
  pages: number;
  failures: BatchFailure[];
  failures_total: number;
  failures_truncated: boolean;
};

/** 422 body returned when EVERY uploaded file failed validation. */
export type BatchAllRejectedResponse = {
  error: "all_files_rejected";
  detail: string;
  timestamp: number;
  files: Array<{
    file_id?: string;
    name: string;
    status?: string;
    error: BatchFileError | null;
  }>;
};

/* ── Error handling ─────────────────────────────────────────────────────── */

export class ApiRequestError extends Error {
  status: number;
  error: string;

  constructor(status: number, error: string, detail: string) {
    super(detail);
    this.name = "ApiRequestError";
    this.status = status;
    this.error = error;
  }
}

/** Human-readable, honest message for any API failure. */
export function describeApiError(err: unknown): string {
  if (err instanceof ApiRequestError) {
    if (err.status === 0) {
      return "Backend API is unreachable. Start it with: python start_backend.py";
    }
    if (err.status === 550 && err.error === "model_unavailable") {
      return (
        "Real ML model unavailable (model_unavailable). No fallback or " +
        "heuristic prediction was used."
      );
    }
    if (err.status === 552) {
      return "Flight data provider request failed. Live data is temporarily unavailable.";
    }
    if (err.status === 553) {
      return "Server configuration error: a required credential or artifact is missing.";
    }
    if (err.status === 429) {
      return "Rate limit exceeded. Please wait a moment and try again.";
    }
    if (err.status === 422) {
      return "Invalid input: please check the fields and try again.";
    }
    return err.message || `Request failed (${err.status}).`;
  }
  return "Unexpected error while contacting the backend.";
}

/* ── Core request helper ────────────────────────────────────────────────── */

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
    });
  } catch {
    throw new ApiRequestError(
      0,
      "api_unreachable",
      `Cannot reach backend at ${API_BASE}`,
    );
  }

  let body: any = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }

  if (!res.ok) {
    const error =
      (body && (body.error || body.detail)) || `HTTP ${res.status}`;
    const detail =
      (body && (body.detail || body.error)) || `HTTP ${res.status}`;
    throw new ApiRequestError(
      res.status,
      typeof error === "string" ? error : "error",
      typeof detail === "string" ? detail : `HTTP ${res.status}`,
    );
  }

  return body as T;
}

/* ── Endpoint wrappers ──────────────────────────────────────────────────── */

export const api = {
  status: () => request<ApiStatusResponse>("/api/v1/status"),

  predict: (payload: {
    flight_number: string;
    origin: string;
    destination: string;
    date: string;
  }) =>
    request<RiskPrediction>("/api/v1/predict", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  lookup: (flightNumber: string, origin?: string) => {
    const params = new URLSearchParams({ flight_number: flightNumber });
    if (origin) params.set("origin", origin);
    return request<FlightLookupResult>(
      `/api/v1/flights/lookup?${params.toString()}`,
    );
  },

  searchAirports: (q: string, limit = 20) => {
    const params = new URLSearchParams({ q, limit: String(limit) });
    return request<AirportSearchResponse>(
      `/api/v1/airports/search?${params.toString()}`,
    );
  },

  searchAirlines: (q: string, limit = 20) => {
    const params = new URLSearchParams({ q, limit: String(limit) });
    return request<AirlineSearchResponse>(
      `/api/v1/airlines/search?${params.toString()}`,
    );
  },

  lookupAndPredict: (flightNumber: string, date: string) => {
    return request<FlightLookupToPredictionResponse>(
      `/api/v1/flights/lookup-and-predict`,
      {
        method: "POST",
        body: JSON.stringify({ flight_number: flightNumber, date }),
      },
    );
  },

  analytics: () => request<RouteAnalytics[]>("/api/v1/routes/analytics"),

  modelInfo: () => request<ModelInfo>("/api/v1/model/info"),

  references: () => request<ReferencesResponse>("/api/v1/airlines/references"),

  /* ── Batch prediction ──────────────────────────────────────────────────
   * These three use FormData/blobs, so they bypass `request()` (which
   * forces application/json) and set no Content-Type at all — the browser
   * must generate the multipart boundary itself.
   */

  batchCreate: async (
    files: File[],
    mapping?: Record<string, string>,
  ): Promise<BatchJobStatus> => {
    const form = new FormData();
    for (const file of files) form.append("files", file, file.name);
    if (mapping && Object.keys(mapping).length > 0) {
      form.append("mapping", JSON.stringify(mapping));
    }
    let res: Response;
    try {
      res = await fetch(`${API_BASE}/api/v1/predict/batch`, {
        method: "POST",
        cache: "no-store",
        body: form,
      });
    } catch {
      throw new ApiRequestError(
        0,
        "api_unreachable",
        `Cannot reach backend at ${API_BASE}`,
      );
    }
    const body = await res.json().catch(() => null);
    if (!res.ok) {
      // Keep the per-file list: the UI shows exactly which CSVs failed.
      const err = new ApiRequestError(
        res.status,
        (body && (body.error || "error")) || `HTTP ${res.status}`,
        (body && (body.detail || body.error)) || `HTTP ${res.status}`,
      );
      Object.assign(err, {
        files: (body && body.files) as BatchAllRejectedResponse["files"],
      });
      throw err;
    }
    return body as BatchJobStatus;
  },

  batchStatus: (jobId: string) =>
    request<BatchJobStatus>(`/api/v1/predict/batch/${jobId}`),

  batchResults: (jobId: string, page = 1, pageSize = 100) =>
    request<BatchResults>(
      `/api/v1/predict/batch/${jobId}/results?page=${page}&page_size=${pageSize}`,
    ),

  /** DELETE the job and remove its temp files. */
  batchDelete: (jobId: string) =>
    request<{ job_id: string; status: string }>(
      `/api/v1/predict/batch/${jobId}`,
      { method: "DELETE" },
    ),

  /**
   * Download a batch CSV (combined | summary | failures | file id) as a
   * Blob plus the server-suggested filename from Content-Disposition.
   */
  batchDownload: async (
    jobId: string,
    file: string,
  ): Promise<{ blob: Blob; filename: string }> => {
    let res: Response;
    try {
      res = await fetch(
        `${API_BASE}/api/v1/predict/batch/${jobId}/download?file=${encodeURIComponent(file)}`,
        { cache: "no-store" },
      );
    } catch {
      throw new ApiRequestError(
        0,
        "api_unreachable",
        `Cannot reach backend at ${API_BASE}`,
      );
    }
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new ApiRequestError(
        res.status,
        (body && (body.error || "error")) || `HTTP ${res.status}`,
        (body && (body.detail || body.error)) || `HTTP ${res.status}`,
      );
    }
    const disposition = res.headers.get("content-disposition") || "";
    const match = /filename="?([^";]+)"?/i.exec(disposition);
    const filename = match?.[1] || `aerodelay_${file}.csv`;
    return { blob: await res.blob(), filename };
  },

  /** CSV template (canonical or bts). */
  batchTemplate: async (
    style: "canonical" | "bts" = "canonical",
  ): Promise<{ blob: Blob; filename: string }> => {
    let res: Response;
    try {
      res = await fetch(
        `${API_BASE}/api/v1/predict/batch/template?style=${style}`,
        { cache: "no-store" },
      );
    } catch {
      throw new ApiRequestError(
        0,
        "api_unreachable",
        `Cannot reach backend at ${API_BASE}`,
      );
    }
    if (!res.ok) {
      throw new ApiRequestError(res.status, "template_failed", "Template download failed.");
    }
    const disposition = res.headers.get("content-disposition") || "";
    const match = /filename="?([^";]+)"?/i.exec(disposition);
    return {
      blob: await res.blob(),
      filename: match?.[1] || "aerodelay_batch_template.csv",
    };
  },
};
