/*!
 * Next.js - AeroDelay AI Premium Frontend
 * Flight Delay-Risk Prediction screen
 * 
 * Features:
 *   - Flight delay risk prediction using ML model (real inference)
 *   - Interactive risk score display
 *   - Factor analysis
 *   - Model limitations and compatibility info
 *   - Reduced-motion support
 */

import Link from "next/link";
import { 
  Truck, Search, Airplay, Circle, 
  CheckSquare, XSquare, RefreshCw,
  Loader2, Sun, CloudRain, Wind,
  Map, Shield, AlertTriangle, Info
} from "lucide-react";
import { GlassPanel, StatusBadge, LoadingSkeleton, RiskGauge, SectionDivider, FlightInfoCard } from "../components/ui";
import { useReducedMotion } from "../hooks/use-reduced-motion";
import { useEffect, useState } from "react";
import { api, describeApiError, type RiskPrediction } from "../lib/api";

export default function PredictionPage() {
  const { reduced } = useReducedMotion();

  const [flightNumber, setFlightNumber] = useState("");
  const [flightDate, setFlightDate] = useState("");
  const [loading, setLoading] = useState(false);
  const [prediction, setPrediction] = useState<RiskPrediction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);

  async function onPredict(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setWarnings([]);
    setPrediction(null);

    if (!flightNumber.trim()) {
      setError("Please enter a flight number (e.g. AA100).");
      return;
    }

    if (!flightDate) {
      setError("Please select a flight date.");
      return;
    }

    setLoading(true);
    try {
      const res = await api.lookupAndPredict(flightNumber.trim(), flightDate);
      setWarnings(res.warnings || []);

      if (res.prediction) {
        setPrediction(res.prediction);
      } else {
        setError(
          res.warnings?.join(" ") || 
          "Delay-risk prediction is not available for this flight."
        );
      }
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setLoading(false);
    }
  }

  const riskColor = prediction?.risk_level === "High" ? "red" 
    : prediction?.risk_level === "Medium" ? "yellow" : "green";

  const showLimitations = useEffect && typeof prediction !== "undefined" ? (
    <div className="mt-6 p-4 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-sm">
      <h4 className="font-semibold text-amber-200 mb-2 flex items-center gap-2">
        <AlertTriangle className="w-4 h-4" /> Model Limitations
      </h4>
      <ul className="list-disc list-inside space-y-1 text-xs">
        <li>
          Trained on BTS On-Time Performance data (Dec 2022). Predictions for
          routes outside this training scope may be less reliable.
        </li>
        <li>
          ML score is a probability estimate, not a guarantee of actual delay.
          Always check with the airline for current flight status.
        </li>
      </ul>
    </div>
  ) : null;

  return (
    <main className="min-h-screen bg-navy-950 text-navy-50">
      {/* Header */}
      <header className="py-6 px-4 max-w-7xl mx-auto border-b border-navy-800/50">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <Link 
            href="/"
            className="font-display-bold text-2xl text-cyan-500 hover:text-navy-100 transition-colors"
          >
            <i className="lucide-Airplane text-xl mr-2" /> AeroDelay AI
          </Link>
          
          <div className="flex items-center gap-3">
            <Search className="w-5 h-5 text-navy-400" />
            <input 
              type="text" 
              placeholder="Flight number or route..." 
              className="bg-navy-900 border border-navy-700 rounded-lg px-4 py-2 focus:outline-none focus:border-cyan-500 text-sm"
              aria-label="Search flight"
            />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto p-4 sm:p-6">
        
        {/* Prediction Form */}
        <GlassPanel minHeight="max-content" className="mb-8">
          <h2 className="text-2xl font-display-bold text-navy-100 mb-6">Delay Risk Prediction</h2>
          
          {error && (
            <div className="mb-6 flex items-start gap-3 p-4 rounded-lg bg-red-500/10 border border-red-500/40 text-red-300 text-sm" role="alert">
              <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" aria-hidden="true" />
              <span>{error}</span>
            </div>
          )}

          {warnings.length > 0 && (
            <div className="mb-6 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
              <span className="ml-2">{warnings.join(" · ")}</span>
            </div>
          )}

          <form onSubmit={onPredict} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="pred-flight-number" className="block text-sm font-medium text-navy-400 mb-2">
                  Flight number
                </label>
                <input
                  id="pred-flight-number"
                  type="text"
                  required
                  maxLength={10}
                  placeholder="e.g. AA100"
                  value={flightNumber}
                  onChange={(e) => setFlightNumber(e.target.value.toUpperCase())}
                  className="w-full bg-navy-900 border border-navy-700 rounded-lg px-4 py-3 text-navy-100 placeholder-navy-500 focus:outline-none focus:border-cyan-500 transition-colors"
                />
              </div>

              <div>
                <label htmlFor="pred-flight-date" className="block text-sm font-medium text-navy-400 mb-2">
                  Flight date
                </label>
                <input
                  id="pred-flight-date"
                  type="date"
                  required
                  value={flightDate}
                  onChange={(e) => setFlightDate(e.target.value)}
                  className="w-full bg-navy-900 border border-navy-700 rounded-lg px-4 py-3 text-navy-100 focus:outline-none focus:border-cyan-500 transition-colors"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-cyan-600 hover:bg-cyan-500 disabled:opacity-60 text-navy-950 font-medium py-3 px-6 rounded-lg transition-all duration-200 shadow-lg shadow-cyan-500/20 flex items-center justify-center gap-2"
            >
              {loading && (
                <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
              )}
              {loading ? "Predicting…" : "Get Delay-Risk Score"}
            </button>
          </form>
        </GlassPanel>

        {/* Prediction Results */}
        {prediction && (
          <GlassPanel minHeight="max-content">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-display-bold text-navy-100">Prediction Result</h2>
              <span className="text-xs text-navy-500 bg-navy-900 px-2 py-1 rounded">
                Model: {prediction.model_version}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
              <div>
                <p className="text-navy-500 text-xs uppercase tracking-wider mb-1">Risk Score</p>
                <div className="text-3xl font-mono font-bold text-navy-100">
                  {(prediction.risk_score * 100).toFixed(1)}%
                </div>
                <p className="text-navy-500 text-xs mt-2">
                  Probability of departure delay ≥ 15 minutes
                </p>
              </div>
              <div>
                <p className="text-navy-500 text-xs uppercase tracking-wider mb-1">Risk Category</p>
                <div className="flex items-center gap-2">
                  <StatusBadge status={prediction.risk_level} size="md" />
                  <span className="text-navy-300 text-sm">
                    {(prediction.confidence * 100).toFixed(0)}% confidence
                  </span>
                </div>
                <p className="text-navy-500 text-xs mt-2">
                  Statistical estimate — not a certainty
                </p>
              </div>
              <div>
                <p className="text-navy-500 text-xs uppercase tracking-wider mb-1">Model Version</p>
                <p className="text-navy-300 text-sm font-mono">
                  {prediction.model_version}
                </p>
              </div>
            </div>

            <div className="mb-6">
              <p className="text-navy-500 text-xs uppercase tracking-wider mb-2">What the score means</p>
              <p className="text-navy-300 text-sm mb-3">
                The ML model estimates the probability that this flight will 
                depart 15 or more minutes after its scheduled time. A score of 
                0.70+ indicates high delay risk, 0.40–0.70 medium, and below 
                0.40 low. This is a statistical estimate based on historical 
                patterns — not a guarantee of actual performance.
              </p>
            </div>

            {prediction.factors && prediction.factors.length > 0 && (
              <div className="mb-6">
                <p className="text-navy-500 text-xs uppercase tracking-wider mb-2">Contributing Factors</p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {prediction.factors.map((f, i) => (
                    <div key={i} className="p-3 rounded bg-navy-900/50 border border-navy-800/50">
                      <p className="text-navy-400 text-xs font-medium mb-1">{f.name}</p>
                      <p className="text-navy-300 text-sm">{f.impact}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="mt-6 p-4 rounded-lg bg-navy-900/50 border border-navy-800/50 text-navy-400 text-sm">
              <p className="font-medium text-navy-200 mb-2">Prediction Limitations</p>
              <ul className="list-disc list-inside space-y-1 text-xs">
                <li>Only routes with carrier, origin, and destination in the model's training vocabulary can be predicted.</li>
                <li>No heuristic, dummy, or synthetic predictions are ever substituted.</li>
                <li>If the model cannot support a retrieved airline or airport, no prediction is returned.</li>
              </ul>
            </div>
          </GlassPanel>
        )}

        {/* Model Methodology Section */}
        <SectionDivider label="Model Methodology" />
        <GlassPanel minHeight="max-content" className="mt-8">
          <h2 className="text-2xl font-display-bold text-navy-100 mb-6">Methodology</h2>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div>
              <h3 className="text-xl font-medium text-navy-100 mb-4">Model</h3>
              <ul className="space-y-3 text-navy-400 text-sm">
                <li>Logistic Regression (Real BTS)</li>
                <li>Target: DepDelay15 (departure delay ≥ 15 minutes)</li>
                <li>Training data: BTS On-Time Performance (Dec 2022)</li>
                <li>Training samples: 498,870 records</li>
                <li>Test accuracy: 49.6%</li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium text-navy-100 mb-4">Feature Pipeline</h3>
              <ul className="space-y-3 text-navy-400 text-sm">
                <li>654 features: 14 carrier OHE, 318 origin OHE, 318 dest OHE, 4 numerical</li>
                <li>One-Hot Encoding for categorical carriers/airports</li>
                <li>Timestamp features (month normalized)</li>
                <li>Preprocessing fitted only on training data</li>
              </ul>
            </div>
          </div>

          <div className="mt-8 pt-8 border-t border-navy-800/20">
            <h3 className="text-xl font-medium text-navy-100 mb-4">Threshold Advisory</h3>
            <p className="text-navy-400 text-sm">
              Risk bands: Low (&lt;0.40), Medium (0.40–0.70), High (≥0.70). Class 
              decision threshold: 0.50. The delayed class represents ~28.6% of 
              test data.
            </p>
          </div>
        </GlassPanel>
      </div>
    </main>
  );
}