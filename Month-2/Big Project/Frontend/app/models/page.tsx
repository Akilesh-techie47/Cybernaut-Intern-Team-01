"use client";

/*!
 * Next.js - AeroDelay AI Premium Frontend
 * Model Information and Methodology screen
 *
 * Phase 5.3: the live model card is fetched from the backend
 * (/api/v1/model/info -> model_metadata.json + loaded artifacts).
 * Phase 2 benchmark figures are historical and clearly labeled as such.
 */

import { useEffect, useState } from "react";
import {
  Shield,
  Database,
  Clock,
  TrendingUp,
  Cpu,
  AlertTriangle,
  Layers,
} from "lucide-react";
import {
  GlassPanel,
  SectionDivider,
  StatusBadge,
  LoadingSkeleton,
} from "../../components/ui";
import { api, describeApiError, type ModelInfo } from "../../lib/api";

/*
 * Phase 2 benchmark results - HISTORICAL values from experiment_results.json.
 * These describe the original benchmark run, not the live compatibility model.
 */
const phase2Benchmarks = [
  {
    id: "logistic",
    name: "Logistic Regression",
    type: "Linear Model",
    status: "Active",
    metrics: {
      accuracy: 0.7133,
      precision: 0.4008,
      recall: 0.4008,
      f1: 0.4008,
      rocAuc: 0.5579,
      prAuc: 0.3262,
    },
    trainingTime: 56.12,
  },
  {
    id: "linearsvc",
    name: "Linear SVC",
    type: "Linear SVM",
    status: "Available",
    metrics: {
      accuracy: 0.7131,
      precision: 0.3943,
      recall: 0.3943,
      f1: 0.3943,
      rocAuc: null as unknown as number,
      prAuc: null as unknown as number,
    },
    trainingTime: 23.85,
    note: "No native predict_proba",
  },
  {
    id: "randomforest",
    name: "Random Forest",
    type: "Ensemble Tree",
    status: "Available",
    metrics: {
      accuracy: null as unknown as number,
      precision: null as unknown as number,
      recall: null as unknown as number,
      f1: null as unknown as number,
      rocAuc: null as unknown as number,
      prAuc: null as unknown as number,
    },
    trainingTime: 0,
    note: "Exceeded time budget on 8GB RAM",
  },
  {
    id: "histgradient",
    name: "HistGradientBoosting",
    type: "Gradient boosting",
    status: "Available",
    metrics: {
      accuracy: null as unknown as number,
      precision: null as unknown as number,
      recall: null as unknown as number,
      f1: null as unknown as number,
      rocAuc: null as unknown as number,
      prAuc: null as unknown as number,
    },
    trainingTime: 0,
    note: "Exceeded time budget on 8GB RAM",
  },
];

function fmt(value: number | null | undefined): string {
  return typeof value === "number" ? value.toFixed(4) : "—";
}

export default function ModelsPage() {
  const [model, setModel] = useState<ModelInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .modelInfo()
      .then((data) => {
        if (!cancelled) setModel(data);
      })
      .catch((err) => {
        if (!cancelled) setError(describeApiError(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex-1 px-4 py-8">
      <div className="max-w-7xl mx-auto">
        {/* Heading */}
        <div className="mb-6">
          <h1 className="text-2xl md:text-3xl font-display-bold text-navy-100">
            Model Information
          </h1>
          <p className="text-navy-400 text-sm mt-1">
            Live model metadata from{" "}
            <code className="text-cyan-400">/api/v1/model/info</code> plus the
            historical Phase 2 benchmark results.
          </p>
        </div>

        {/* Live model card */}
        {loading && (
          <div data-testid="model-loading" className="mb-8">
            <GlassPanel>
              <LoadingSkeleton rows={4} />
            </GlassPanel>
          </div>
        )}

        {error && !loading && (
          <div
            data-testid="model-error"
            className="flex items-start gap-3 p-4 rounded-lg bg-red-500/10 border border-red-500/40 text-red-300 text-sm mb-8"
          >
            <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        {model && !loading && (
          <div data-testid="model-info" className="mb-8">
            <GlassPanel>
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-6">
                <div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <h2 className="text-xl md:text-2xl font-display-bold text-navy-100">
                      {model.name}
                    </h2>
                    <StatusBadge status={model.status} size="md" />
                  </div>
                  <p className="text-navy-400 text-sm mt-1">
                    {model.type} · {model.version}
                  </p>
                  <p className="text-cyan-400 text-xs mt-1 flex items-center gap-1">
                    <Cpu className="w-3.5 h-3.5" aria-hidden="true" />
                    Loaded from logistic_regression_new.joblib (654 features)
                  </p>
                </div>
                <div className="text-sm text-navy-400 space-y-1 sm:text-right">
                  <p>
                    <span className="text-navy-500">Features:</span>{" "}
                    <span className="text-navy-100 font-medium">
                      {model.features}
                    </span>
                  </p>
                  <p>
                    <span className="text-navy-500">Trained samples:</span>{" "}
                    <span className="text-navy-100 font-medium">
                      {model.trained_on.toLocaleString()}
                    </span>
                  </p>
                  <p>
                    <span className="text-navy-500">API version:</span>{" "}
                    <span className="text-navy-100 font-medium">
                      {model.version}
                    </span>
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                {Object.entries(model.metrics).map(([key, value]) => (
                  <div
                    key={key}
                    className="p-3 rounded-lg bg-navy-950/60 border border-navy-800/60 text-center"
                  >
                    <p className="text-navy-500 text-[11px] uppercase tracking-wider">
                      {key.replace(/_/g, " ")}
                    </p>
                    <p className="text-navy-100 font-semibold mt-1">
                      {typeof value === "number" ? value.toFixed(4) : "—"}
                    </p>
                  </div>
                ))}
              </div>

              <p className="text-navy-500 text-xs mt-4">
                Note: this is the Phase 5.1 compatibility model retrained in
                the current Python environment (synthetic data for
                serialization verification). Its metrics differ from the
                original Phase 2 benchmark below - both are reported honestly.
              </p>
            </GlassPanel>
          </div>
        )}

        {/* Phase 2 benchmark table */}
        <SectionDivider label="Phase 2 Benchmark Results (historical)" />

        <GlassPanel className="overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr className="border-b border-navy-800">
                <th className="text-left text-navy-500 font-medium py-3 px-4">
                  Model
                </th>
                <th className="text-left text-navy-500 font-medium py-3 px-4">
                  Accuracy
                </th>
                <th className="text-left text-navy-500 font-medium py-3 px-4">
                  Precision
                </th>
                <th className="text-left text-navy-500 font-medium py-3 px-4">
                  Recall
                </th>
                <th className="text-left text-navy-500 font-medium py-3 px-4">
                  F1 Score
                </th>
                <th className="text-left text-navy-500 font-medium py-3 px-4">
                  ROC-AUC
                </th>
                <th className="text-left text-navy-500 font-medium py-3 px-4">
                  Training
                </th>
              </tr>
            </thead>
            <tbody>
              {phase2Benchmarks.map((m) => (
                <tr
                  key={m.id}
                  className="border-b border-navy-800/60 hover:bg-navy-900/50 transition-colors duration-200"
                >
                  <td className="py-3 px-4 font-medium text-navy-100">
                    {m.name}
                    {m.note && (
                      <span className="block text-navy-500 text-xs font-normal">
                        {m.note}
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-navy-300">
                    {fmt(m.metrics.accuracy)}
                  </td>
                  <td className="py-3 px-4 text-navy-300">
                    {fmt(m.metrics.precision)}
                  </td>
                  <td className="py-3 px-4 text-navy-300">
                    {fmt(m.metrics.recall)}
                  </td>
                  <td className="py-3 px-4 text-navy-300">
                    {fmt(m.metrics.f1)}
                  </td>
                  <td className="py-3 px-4 text-navy-300">
                    {fmt(m.metrics.rocAuc)}
                  </td>
                  <td className="py-3 px-4 text-navy-400">
                    {m.trainingTime > 0 ? `${m.trainingTime}s` : "TB"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-navy-500 text-xs mt-4">
            Source: experiment_results.json (Phase 2, BTS On-Time Performance,
            498,870 records). TB = time budget exceeded.
          </p>
        </GlassPanel>

        {/* Pipeline summary */}
        <SectionDivider label="Artifact & Pipeline Details" className="mt-10" />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          <GlassPanel className="p-6">
            <Shield className="w-6 h-6 text-cyan-500 mb-3" aria-hidden="true" />
            <h3 className="text-lg font-medium text-navy-100 mb-2">
              Serialization fix
            </h3>
            <p className="text-navy-400 text-sm">
              Original Phase 2 pickles referenced <code>__main__</code> classes
              and cannot load in Python 3.13. Phase 5.1 produced compatible
              artifacts; the originals are preserved untouched.
            </p>
          </GlassPanel>
          <GlassPanel className="p-6">
            <Database className="w-6 h-6 text-cyan-500 mb-3" aria-hidden="true" />
            <h3 className="text-lg font-medium text-navy-100 mb-2">
              Feature schema
            </h3>
            <p className="text-navy-400 text-sm">
              654 features: carrier (7), origin (5), destination (5), normalized
              month (1) and 637 remaining engineered features.
            </p>
          </GlassPanel>
          <GlassPanel className="p-6">
            <Layers className="w-6 h-6 text-cyan-500 mb-3" aria-hidden="true" />
            <h3 className="text-lg font-medium text-navy-100 mb-2">
              Failure behavior
            </h3>
            <p className="text-navy-400 text-sm">
              If artifacts cannot load, the API returns HTTP 550{" "}
              <code className="text-yellow-400">model_unavailable</code> instead
              of substituting a heuristic prediction.
            </p>
          </GlassPanel>
        </div>

        {/* Methodology */}
        <SectionDivider label="Full Methodology" className="mt-10" />

        <GlassPanel>
          <h2 className="text-xl md:text-2xl font-display-bold text-navy-100 mb-5">
            Experiment Methodology
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-4 text-navy-400 text-sm">
            <div>
              <p className="font-medium text-navy-200 mb-1">Datasets</p>
              <p>BTS On-Time Performance (primary), Kaggle 2024 (CC0) validation</p>
            </div>
            <div>
              <p className="font-medium text-navy-200 mb-1">Temporal split</p>
              <p>Earlier period train, later period validation, holdout test</p>
            </div>
            <div>
              <p className="font-medium text-navy-200 mb-1">Preprocessing</p>
              <p>Fitted only on training data; no leakage into test sets</p>
            </div>
            <div>
              <p className="font-medium text-navy-200 mb-1">Class imbalance</p>
              <p>Delayed class ≈28.6% of test data; metrics reported accordingly</p>
            </div>
            <div>
              <p className="font-medium text-navy-200 mb-1">Metrics</p>
              <p>Accuracy, precision, recall, F1, ROC-AUC, PR-AUC</p>
            </div>
            <div>
              <p className="font-medium text-navy-200 mb-1">Constraints</p>
              <p>8GB RAM budget; RF and HistGradientBoosting exceeded time budget</p>
            </div>
          </div>

          <div className="mt-6 pt-5 border-t border-navy-800/60 flex items-center gap-2 text-navy-500 text-xs">
            <TrendingUp className="w-4 h-4" aria-hidden="true" />
            <Clock className="w-4 h-4" aria-hidden="true" />
            Metrics shown live above come from model_metadata.json via the
            backend; table values are the original Phase 2 benchmark record.
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}
