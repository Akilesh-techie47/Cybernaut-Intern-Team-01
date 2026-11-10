/*!
 * Next.js - AeroDelay AI Premium Frontend
 * Model Information and Methodology screen
 * 
 * Features:
   - Model catalog and version info
   - Performance metrics comparison
   - Training data summary
   - Pipeline details
   - Reduced-motion support
*/

import Link from "next/link";
import { 
  Shield, Database, Loader2, 
  Clock, TrendingUp, TrendingDown,
  Folder, Layout, Settings,
  Zap, AlertCircle, Search
} from "lucide-react";
import { GlassPanel, SectionDivider, RiskGauge, StatusBadge } from "../components/ui";
import { useReducedMotion } from "../hooks/use-reduced-motion";

/* 
  Demo model metadata - Phase 2 experiment results
  Matches the experiment_results.json from the Phase 2 benchmarking
*/
const demoModels = [
  {
    id: "logistic",
    name: "Logistic Regression",
    type: "Linear Model",
    version: "Phase 2 Ensemble v2.1",
    status: "Active",
    color: "green",
    metrics: {
      accuracy: 0.7133,
      precision: 0.4008,
      recall: 0.4008,
      f1: 0.4008,
      rocAuc: 0.5579,
      prAuc: 0.3262,
    },
    trainingTime: 56.12,
    features: 654,
    trainedOn: 498870,
  },
  {
    id: "linearsvc",
    name: "Linear SVC",
    type: "Linear SVM",
    version: "Phase 2 Ensemble v2.1",
    status: "Active",
    color: "cyan",
    metrics: {
      accuracy: 0.7131,
      precision: 0.3943,
      recall: 0.3943,
      f1: 0.3943,
      rocAuc: 0, // Not natively supported
      prAuc: 0,
    },
    trainingTime: 23.85,
    features: 654,
    trainedOn: 498870,
  },
  {
    id: "randomforest",
    name: "Random Forest",
    type: "Ensemble Tree",
    version: "Phase 2",
    status: "Available",
    color: "purple",
    metrics: {
      accuracy: 0,
      precision: 0,
      recall: 0,
      f1: 0,
      rocAuc: 0,
      prAuc: 0,
    },
    trainingTime: 0,
    features: 654,
    trainedOn: 498870,
    note: "Exceeded time budget on 8GB RAM",
  },
  {
    id: "histgradient",
    name: "HistGradientBoosting",
    type: "Gradient boosting",
    version: "Phase 2",
    status: "Available",
    color: "amber",
    metrics: {
      accuracy: 0,
      precision: 0,
      recall: 0,
      f1: 0,
      rocAuc: 0,
      prAuc: 0,
    },
    trainingTime: 0,
    features: 654,
    trainedOn: 498870,
    note: "Exceeded time budget on 8GB RAM",
  },
];

export default function ModelsPage() {
  const { reduced } = useReducedMotion();

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
              placeholder="Search models..." 
              className="bg-navy-900 border border-navy-700 rounded-lg px-4 py-2 focus:outline-none focus:border-cyan-500 text-sm"
              aria-label="Search models"
            />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto p-4 sm:p-6">
        
        {/* Model Summary Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <GlassPanel minHeight="100" className="p-4 text-center">
            <div className="text-3xl font-display-bold text-cyan-500">4</div>
            <p className="text-navy-500 text-xs uppercase tracking-wider">Active Models</p>
            <i className="lucide-Shield w-6 h-6 text-navy-800 mx-auto mt-2" />
          </GlassPanel>
          <GlassPanel minHeight="100" className="p-4 text-center">
            <div className="text-3xl font-display-bold text-green-500">71%</div>
            <p className="text-navy-500 text-xs uppercase tracking-wider">Best Accuracy</p>
            <i className="lucide-TrendingUp w-6 h-6 text-navy-800 mx-auto mt-2" />
          </GlassPanel>
          <GlassPanel minHeight="100" className="p-4 text-center">
            <div className="text-3xl font-display-bold text-amber-500">654</div>
            <p className="text-navy-500 text-xs uppercase tracking-wider">Feature Count</p>
            <i className="lucide-Database w-6 h-6 text-navy-800 mx-auto mt-2" />
          </GlassPanel>
          <GlassPanel minHeight="100" className="p-4 text-center">
            <div className="text-3xl font-display-bold text-purple-500">2</div>
            <p className="text-navy-500 text-xs uppercase tracking-wider">Completed</p>
            <i className="lucide-Clock w-6 h-6 text-navy-800 mx-auto mt-2" />
          </GlassPanel>
        </div>

        {/* Model Comparison Table */}
        <SectionDivider label="Model Performance Comparison" />
        
        <GlassPanel minHeight="max-content" className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-navy-800/50">
                <th className="text-left text-navy-500 font-medium py-3 px-4">Model</th>
                <th className="text-left text-navy-500 font-medium py-3 px-4">Accuracy</th>
                <th className="text-left text-navy-500 font-medium py-3 px-4">Precision</th>
                <th className="text-left text-navy-500 font-medium py-3 px-4">Recall</th>
                <th className="text-left text-navy-500 font-medium py-3 px-4">F1 Score</th>
                <th className="text-left text-navy-500 font-medium py-3 px-4">ROC-AUC</th>
                <th className="text-left text-navy-500 font-medium py-3 px-4">Training</th>
              </tr>
            </thead>
            <tbody>
              {demoModels.map((model) => (
                <tr key={model.id} className="border-b border-navy-800/50 hover:bg-navy-900/50 transition-colors duration-200">
                  <td className="py-3 px-4 font-medium text-navy-100">
                    <Link 
                      href={`/model/${model.id}`}
                      className="underline underline-offset-2 hover:text-cyan-400 transition-colors"
                    >
                      {model.name}
                    </Link>
                  </td>
                  <td className="py-3 px-4 text-navy-400">{model.metrics.accuracy.toFixed(4)}</td>
                  <td className="py-3 px-4 text-navy-400">{model.metrics.precision.toFixed(4)}</td>
                  <td className="py-3 px-4 text-navy-400">{model.metrics.recall.toFixed(4)}</td>
                  <td className="py-3 px-4 text-navy-400">{model.metrics.f1.toFixed(4)}</td>
                  <td className="py-3 px-4 text-navy-400">{model.metrics.rocAuc.toFixed(4)}</td>
                  <td className="py-3 px-4 text-navy-400">
                    {model.trainingTime > 0 ? (
                      <span className="text-navy-500">{model.trainingTime}s</span>
                    ) : (
                      <span className="text-navy-500 text-xs">TB</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </GlassPanel>

        {/* Detailed Model Views */}
        <SectionDivider label="Model Details" className="mt-8" />
        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {demoModels.map((model) => (
            <GlassPanel 
              key={model.id} 
              minHeight="280"
              className="p-6"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-xl font-medium text-navy-100">{model.name}</h3>
                  <p className="text-navy-500 text-sm">{model.type}</p>
                </div>
                <RiskGauge score={0.5} size="sm" />
              </div>
              
              <div className="grid grid-cols-2 gap-4 text-navy-400 text-sm">
                <div>
                  <p className="font-medium">Version</p>
                  <p>{model.version}</p>
                </div>
                <div>
                  <p className="font-medium">Status</p>
                  <StatusBadge status={model.status} size="sm" />
                </div>
                <div>
                  <p className="font-medium">Features</p>
                  <p>{model.features}</p>
                </div>
                <div>
                  <p className="font-medium">Trained On</p>
                  <p>{model.trainedOn.toLocaleString()} records</p>
                </div>
              </div>
              
              {model.note && (
                <p className="mt-4 text-navy-500 text-xs italic">
                  {model.note}
                </p>
              )}
            </GlassPanel>
          ))}
        </div>

        {/* Methodology Accordion / Details */}
        <SectionDivider label="Full Methodology" className="mt-8" />
        
        <GlassPanel minHeight="max-content" className="mt-8">
          <h2 className="text-2xl font-display-bold text-navy-100 mb-6">Experiment Methodology</h2>
          
          <div className="space-y-4 text-navy-400">
            <div>
              <p className="font-medium mb-2">Datasets Used</p>
              <p>BTS On-Time Performance (primary), with Kaggle 2024 (CC0) for external validation</p>
            </div>
            <div>
              <p className="font-medium mb-2">Feature Compatibility</p>
              <p>Identical feature definitions across all datasets for fair comparison</p>
            </div>
            <div>
              <p className="font-medium mb-2">Temporal Validation</p>
              <p>Training on earlier period, validation on later period, test on holdout</p>
            </div>
            <div>
              <p className="font-medium mb-2">Preprocessing Integrity</p>
              <p>Fitted only on training data; no data leakage into validation/test</p>
            </div>
            <div>
              <p className="font-medium mb-2">Class Imbalance Handling</p>
              <p>Delayed class: ~28.6% of test data; metrics reported with imbalance awareness</p>
            </div>
            <div>
              <p className="font-medium mb-2">Evaluation Metrics</p>
              <p>Accuracy, Precision, Recall, F1, ROC-AUC, PR-AUC, Confusion Matrices, Calibration</p>
            </div>
            <div>
              <p className="font-medium mb-2">Resource Constraints</p>
              <p>Experiments constrained to 8GB RAM; Random Forest and HistGradientBoosting 
              exceeded time budget but showed promise in preliminary runs</p>
            </div>
          </div>

          {reduced && (
            <div className="mt-6 p-4 bg-navy-900/50 rounded-lg text-red-400">
              <p className="text-sm">
                <strong>Reduced motion mode.</strong> Static content displayed. 
                Animated charts and would feature smooth transitions and progressive updates.
              </p>
            </div>
          )}
        </GlassPanel>
      </div>
    </main>
  );
}

/* 
  Helper to convert number to locale string
*/
function trainedToLocaleString(count: number): string {
  return count.toLocaleString();
}