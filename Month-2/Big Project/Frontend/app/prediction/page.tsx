"use client";

/*!
 * Next.js - AeroDelay AI Premium Frontend
 * Flight Delay-Risk Prediction screen
 *
 * Phase 5.3: predictions come from the real ML model served by the
 * backend (/api/v1/predict -> logistic_regression_new.joblib). If the model
 * cannot run, the backend returns HTTP 550 model_unavailable and this UI
 * shows that explicitly - NO fallback/heuristic score is ever displayed.
 */

import { useState } from "react";
import {
  Loader2,
  AlertTriangle,
  ShieldCheck,
  Cpu,
  Timer,
} from "lucide-react";
import {
  GlassPanel,
  SectionDivider,
  RiskGauge,
  LoadingSkeleton,
} from "../../components/ui";
import { api, describeApiError, type RiskPrediction } from "../../lib/api";

/* Demo predictions - simulated model outputs, clearly labeled.
   These are NOT real model results. */
const demoPredictions = [
  {
    id: "1",
    flightNumber: "AA 123",
    route: "JFK → LAX",
    riskScore: 0.08,
    riskLevel: "Low",
    note: "illustrative",
  },
  {
    id: "2",
    flightNumber: "DL 456",
    route: "SFO → JFK",
    riskScore: 0.67,
    riskLevel: "High",
    note: "illustrative",
  },
  {
    id: "3",
    flightNumber: "UA 789",
    route: "ORD → SEA",
    riskScore: 0.42,
    riskLevel: "Medium",
    note: "illustrative",
  },
];

export default function PredictionPage() {
  const [flightNumber, setFlightNumber] = useState("");
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [date, setDate] = useState("");

  const [loading, setLoading] = useState(false);
  const [prediction, setPrediction] = useState<RiskPrediction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isModelError, setIsModelError] = useState(false);

  async function onPredict(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPrediction(null);
    setIsModelError(false);

    /* Client-side validation mirrors the backend schema */
    if (!flightNumber.trim() || !origin || !destination || !date) {
      setError("All fields are required: flight number, origin, destination and date.");
      setIsModelError(false);
      return;
    }
    if (origin === destination) {
      setError("Origin and destination must be different airports.");
      return;
    }

    setLoading(true);
    try {
      const res = await api.predict({
        flight_number: flightNumber.trim().toUpperCase(),
        origin,
        destination,
        date,
      });
      setPrediction(res);
    } catch (err) {
      /* Surface model_unavailable (HTTP 550) distinctly from other errors */
      const isModelIssue =
        typeof err === "object" &&
        err !== null &&
        (err as { status?: number }).status === 550;
      setIsModelError(Boolean(isModelIssue));
      setError(describeApiError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex-1 px-4 py-8">
      <div className="max-w-7xl mx-auto">
        {/* Heading */}
        <div className="mb-6">
          <h1 className="text-2xl md:text-3xl font-display-bold text-navy-100">
            Delay Risk Prediction
          </h1>
          <p className="text-navy-400 text-sm mt-1">
            Real inference from the Phase 2 Logistic Regression model (654
            features) served by the backend.
          </p>
        </div>

        {/* Prediction form */}
        <GlassPanel className="mb-8">
          <form
            data-testid="predict-form"
            onSubmit={onPredict}
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end"
          >
            <div>
              <label
                htmlFor="pred-flight-number"
                className="block text-sm font-medium text-navy-400 mb-2"
              >
                Flight number
              </label>
              <input
                id="pred-flight-number"
                data-testid="predict-flight-input"
                type="text"
                required
                maxLength={10}
                placeholder="e.g. AA123"
                value={flightNumber}
                onChange={(e) => setFlightNumber(e.target.value.toUpperCase())}
                className="w-full bg-navy-900 border border-navy-700 rounded-lg px-4 py-3 text-navy-100 placeholder-navy-500 focus:outline-none focus:border-cyan-500 transition-colors"
              />
            </div>
            <div>
              <label
                htmlFor="pred-origin"
                className="block text-sm font-medium text-navy-400 mb-2"
              >
                Origin
              </label>
              <select
                id="pred-origin"
                data-testid="predict-origin"
                required
                value={origin}
                onChange={(e) => setOrigin(e.target.value)}
                className="w-full bg-navy-900 border border-navy-700 rounded-lg px-4 py-3 text-navy-100 focus:outline-none focus:border-cyan-500 transition-colors"
              >
                <option value="">Select…</option>
                <option value="JFK">JFK</option>
                <option value="LAX">LAX</option>
                <option value="SFO">SFO</option>
                <option value="ORD">ORD</option>
                <option value="SEA">SEA</option>
              </select>
            </div>
            <div>
              <label
                htmlFor="pred-destination"
                className="block text-sm font-medium text-navy-400 mb-2"
              >
                Destination
              </label>
              <select
                id="pred-destination"
                data-testid="predict-destination"
                required
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                className="w-full bg-navy-900 border border-navy-700 rounded-lg px-4 py-3 text-navy-100 focus:outline-none focus:border-cyan-500 transition-colors"
              >
                <option value="">Select…</option>
                <option value="JFK">JFK</option>
                <option value="LAX">LAX</option>
                <option value="SFO">SFO</option>
                <option value="ORD">ORD</option>
                <option value="SEA">SEA</option>
              </select>
            </div>
            <div>
              <label
                htmlFor="pred-date"
                className="block text-sm font-medium text-navy-400 mb-2"
              >
                Date
              </label>
              <input
                id="pred-date"
                data-testid="predict-date"
                type="date"
                required
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="w-full bg-navy-900 border border-navy-700 rounded-lg px-4 py-3 text-navy-100 focus:outline-none focus:border-cyan-500 transition-colors"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              data-testid="predict-submit"
              className="sm:col-span-2 lg:col-span-4 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-60 text-navy-950 font-medium py-3 px-6 rounded-lg transition-all duration-200 shadow-lg shadow-cyan-500/20 flex items-center justify-center gap-2"
            >
              {loading && (
                <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
              )}
              {loading ? "Running model…" : "Predict Delay Risk"}
            </button>
          </form>

          {/* Result states */}
          <div className="mt-6" aria-live="polite">
            {loading && (
              <div data-testid="predict-loading">
                <LoadingSkeleton rows={3} />
              </div>
            )}

            {error && (
              <div
                data-testid="predict-error"
                data-model-unavailable={isModelError ? "true" : "false"}
                className={`flex items-start gap-3 p-4 rounded-lg border text-sm ${
                  isModelError
                    ? "bg-yellow-500/10 border-yellow-500/40 text-yellow-300"
                    : "bg-red-500/10 border-red-500/40 text-red-300"
                }`}
              >
                <AlertTriangle
                  className="w-5 h-5 shrink-0 mt-0.5"
                  aria-hidden="true"
                />
                <span>
                  {isModelError ? (
                    <>
                      <strong className="font-semibold">
                        model_unavailable:
                      </strong>{" "}
                      the real ML model could not run, so no prediction was
                      returned. A fallback or heuristic score is never shown
                      as a real prediction.
                    </>
                  ) : (
                    error
                  )}
                </span>
              </div>
            )}

            {prediction && (
              <div
                data-testid="predict-result"
                className="p-5 rounded-lg bg-navy-900/70 border border-cyan-500/30"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-5">
                  <div>
                    <h3 className="text-xl font-semibold text-navy-100">
                      {prediction.flight_number}
                    </h3>
                    <p className="text-navy-400 text-sm">
                      {prediction.origin} → {prediction.destination} ·{" "}
                      {prediction.date}
                    </p>
                    <p className="text-cyan-400 text-xs mt-1 flex items-center gap-1">
                      <ShieldCheck className="w-3.5 h-3.5" aria-hidden="true" />
                      Real ML inference · {prediction.model_version}
                    </p>
                  </div>
                  <RiskGauge score={prediction.risk_score} size="md" />
                </div>

                {/* Risk bar */}
                <div className="mb-5">
                  <div className="flex items-center justify-between text-sm mb-2">
                    <span className="text-navy-500">Risk score</span>
                    <span className="text-navy-100 font-medium">
                      {prediction.risk_level} ·{" "}
                      {(prediction.risk_score * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="h-3 bg-navy-950 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        prediction.risk_score >= 0.7
                          ? "bg-red-500"
                          : prediction.risk_score >= 0.4
                            ? "bg-yellow-500"
                            : "bg-green-500"
                      }`}
                      style={{
                        width: `${Math.round(prediction.risk_score * 100)}%`,
                      }}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm mb-5">
                  <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800/60">
                    <p className="text-navy-500 text-xs flex items-center gap-1">
                      <ShieldCheck className="w-3.5 h-3.5" aria-hidden="true" />
                      Confidence
                    </p>
                    <p className="text-navy-100 font-medium mt-1">
                      {Math.round(prediction.confidence * 100)}%
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800/60">
                    <p className="text-navy-500 text-xs flex items-center gap-1">
                      <Timer className="w-3.5 h-3.5" aria-hidden="true" />
                      Inference time
                    </p>
                    <p className="text-navy-100 font-medium mt-1">
                      {prediction.prediction_time_ms.toFixed(1)} ms
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800/60 col-span-2 sm:col-span-1">
                    <p className="text-navy-500 text-xs flex items-center gap-1">
                      <Cpu className="w-3.5 h-3.5" aria-hidden="true" />
                      Model
                    </p>
                    <p className="text-navy-100 font-medium mt-1 text-xs sm:text-sm">
                      {prediction.model_version}
                    </p>
                  </div>
                </div>

                {/* Factors */}
                <p className="text-navy-500 text-sm font-medium mb-2">
                  Model factors
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {prediction.factors.map((factor, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between gap-2 px-3 py-2 rounded bg-navy-950/60 border border-navy-800/60 text-xs"
                    >
                      <span className="text-navy-400">{factor.name}</span>
                      <span className="text-navy-200 font-medium">
                        {factor.impact}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </GlassPanel>

        {/* Demo examples */}
        <div className="flex flex-col items-center gap-2 mb-6 text-center">
          <h2 className="text-xl md:text-2xl font-display-bold text-navy-100">
            Example Outputs
          </h2>
          <span className="text-xs uppercase tracking-widest px-3 py-1 rounded-full bg-yellow-500/15 text-yellow-400 border border-yellow-500/30">
            Demo data · illustrative, not real model results
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {demoPredictions.map((p) => (
            <article
              key={p.id}
              className="bg-navy-950/50 backdrop-blur-sm border border-navy-800/50 rounded-2xl p-6"
              aria-label={`Example risk for ${p.flightNumber}`}
            >
              <div className="flex items-start justify-between gap-3 mb-4">
                <div>
                  <h3 className="text-lg font-medium text-navy-100">
                    {p.flightNumber}
                  </h3>
                  <p className="text-navy-500 text-sm">{p.route}</p>
                </div>
                <RiskGauge score={p.riskScore} size="sm" />
              </div>
              <div className="h-2 bg-navy-900 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    p.riskScore >= 0.7
                      ? "bg-red-500"
                      : p.riskScore >= 0.4
                        ? "bg-yellow-500"
                        : "bg-green-500"
                  }`}
                  style={{ width: `${p.riskScore * 100}%` }}
                />
              </div>
              <p className="text-navy-500 text-xs mt-2">
                {p.riskLevel} · {Math.round(p.riskScore * 100)}%
              </p>
            </article>
          ))}
        </div>

        <SectionDivider label="Model Methodology" className="mt-10" />

        <GlassPanel>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div>
              <h3 className="text-lg font-medium text-navy-100 mb-3">
                Inference pipeline
              </h3>
              <ul className="space-y-2 text-navy-400 text-sm list-disc pl-5">
                <li>
                  654-feature vector built from carrier, origin, destination
                  and date inputs
                </li>
                <li>
                  Compatible preprocessor (preprocessor_compatible.joblib)
                </li>
                <li>
                  Logistic Regression model (logistic_regression_new.joblib)
                </li>
                <li>Server-side inference - no model weights ship to browser</li>
              </ul>
            </div>
            <div>
              <h3 className="text-lg font-medium text-navy-100 mb-3">
                Honest failure modes
              </h3>
              <ul className="space-y-2 text-navy-400 text-sm list-disc pl-5">
                <li>
                  If artifacts fail to load, the API returns HTTP 550 with{" "}
                  <code className="text-yellow-400">model_unavailable</code>
                </li>
                <li>No heuristic or dummy score is ever substituted</li>
                <li>
                  The retrained compatibility model uses synthetic training
                  data - its metrics differ from the original Phase 2
                  benchmark (shown on the Models screen)
                </li>
              </ul>
            </div>
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}
