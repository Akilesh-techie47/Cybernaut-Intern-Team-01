"use client";

/*!
 * Next.js - AeroDelay AI Premium Frontend
 * Home / Flight Search screen
 *
 * Phase 5.4: unified flight search + delay-risk prediction workflow.
 *  - Searchable airport/airline selectors (autocomplete from backend)
 *  - Unified flight number + date search via /api/v1/flights/lookup-and-predict
 *  - Model feature compatibility check before prediction
 *  - Clear separation of provider status vs ML prediction
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Search,
  Plane,
  Loader2,
  AlertTriangle,
  Radio,
  ChevronRight,
  X,
  Clock,
  Info,
} from "lucide-react";
import {
  GlassPanel,
  StatusBadge,
  SectionDivider,
  LoadingSkeleton,
} from "../components/ui";
import {
  api,
  describeApiError,
  type ApiStatusResponse,
  type FlightLookupResult,
} from "../lib/api";

/* ------------------------------------------------------------------ */
/* Local types                                                        */
/* ------------------------------------------------------------------ */

type SearchableOption = {
  label: string;
  value: string;
  [key: string]: unknown;
};

type ViewState = "search" | "results" | "prediction";

/* ------------------------------------------------------------------ */
/* HomePage                                                           */
/* ------------------------------------------------------------------ */

export default function HomePage() {
  /* Backend health */
  const [status, setStatus] = useState<ApiStatusResponse | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);

  /* Search form state */
  const [flightNumber, setFlightNumber] = useState("");
  const [flightDate, setFlightDate] = useState("");
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");

  /* Airport/airline autocomplete */
  const [airportQuery, setAirportQuery] = useState("");
  const [airlineQuery, setAirlineQuery] = useState("");
  const [originOptions, setOriginOptions] = useState<SearchableOption[]>([]);
  const [destinationOptions, setDestinationOptions] = useState<
    SearchableOption[]
  >([]);
  const [airlineOptions, setAirlineOptions] = useState<SearchableOption[]>([]);
  const [originDropdownOpen, setOriginDropdownOpen] = useState(false);
  const [destinationDropdownOpen, setDestinationDropdownOpen] = useState(false);
  const [airlineDropdownOpen, setAirlineDropdownOpen] = useState(false);
  const originInputRef = useRef<HTMLInputElement>(null);
  const destInputRef = useRef<HTMLInputElement>(null);
  const airlineInputRef = useRef<HTMLInputElement>(null);

  /* Lookup / prediction state */
  const [view, setView] = useState<ViewState>("search");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<FlightLookupResult | null>(null);
  const [prediction, setPrediction] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [compatibility, setCompatibility] = useState<Record<string, unknown> | null>(null);

  /* Backend health on mount */
  useEffect(() => {
    let cancelled = false;
    api
      .status()
      .then((s) => !cancelled && setStatus(s))
      .catch((e) => !cancelled && setStatusError(describeApiError(e)));
    return () => {
      cancelled = true;
    };
  }, []);

  /* ------------------------------------------------------------------ */
  /* Autocomplete debounce helpers                                      */
  /* ------------------------------------------------------------------ */

  const searchAirports = useCallback(
    async (query: string, setOptions: (o: SearchableOption[]) => void) => {
      if (!query.trim()) {
        setOptions([]);
        return;
      }
      try {
        const res = await api.searchAirports(query.trim(), 15);
        setOptions(
          res.airports.map((a) => ({
            label: `${a.iata} - ${a.name}, ${a.city}`,
            value: a.iata,
            ...a,
          }))
        );
      } catch {
        setOptions([]);
      }
    },
    []
  );

  const searchAirlines = useCallback(
    async (query: string, setOptions: (o: SearchableOption[]) => void) => {
      if (!query.trim()) {
        setOptions([]);
        return;
      }
      try {
        const res = await api.searchAirlines(query.trim(), 15);
        setOptions(
          res.airlines.map((a) => ({
            label: `${a.code} - ${a.name}`,
            value: a.code,
            ...a,
          }))
        );
      } catch {
        setOptions([]);
      }
    },
    []
  );

  /* ------------------------------------------------------------------ */
  /* Search form submission                                             */
  /* ------------------------------------------------------------------ */

  async function onSearch(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setWarnings([]);
    setResult(null);
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
    setView("search");
    try {
      const res = await api.lookupAndPredict(flightNumber.trim(), flightDate);
      setWarnings(res.warnings || []);

      if (!res.flight_info.found) {
        setResult(res.flight_info);
        setView("results");
        return;
      }

      setResult(res.flight_info);
      setCompatibility(res.feature_compatibility || null);

      if (res.prediction) {
        setPrediction(res.prediction);
        setView("prediction");
      } else {
        setView("results");
      }
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setLoading(false);
    }
  }

  /* ------------------------------------------------------------------ */
  /* Predict from retrieved flight (lookup → prediction workflow)       */
  /* ------------------------------------------------------------------ */

  async function onPredictFromRetrieved() {
    if (!result?.flight_number || !result?.flight_date) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.lookupAndPredict(
        result.flight_number,
        result.flight_date
      );
      setWarnings(res.warnings || []);
      setCompatibility(res.feature_compatibility || null);
      if (res.prediction) {
        setPrediction(res.prediction);
        setView("prediction");
      } else {
        setError(
          "Delay-risk prediction is not available for this flight. " +
            (res.warnings?.join(" ") || "Model does not support this route.")
        );
      }
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setLoading(false);
    }
  }

  /* ------------------------------------------------------------------ */
  /* Render helpers                                                     */
/* ------------------------------------------------------------------ */

  const showModelLimitations = useMemo(() => {
    if (!prediction) return null;
    const compat = compatibility || {};
    return (
      <div className="mt-6 p-4 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-sm">
        <h4 className="font-semibold text-amber-200 mb-2 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" /> Model Limitations
        </h4>
        <ul className="list-disc list-inside space-y-1 text-xs">
          {(compat as { unsupported_features?: string[] })?.unsupported_features?.length ? (
            (compat as { unsupported_features?: string[] })?.unsupported_features?.map((f: string, i: number) => (
              <li key={i}>
                <strong>{f}</strong> is not supported by the model.
              </li>
            ))
          ) : (
            <li>All required model features are available for this route.</li>
          )}
          <li>
            Trained on BTS On-Time Performance data (Dec 2022). Predictions
            for routes outside this training scope may be less reliable.
          </li>
          <li>
            ML score is a probability estimate, not a guarantee of actual
            delay. Always check with the airline for current flight status.
          </li>
        </ul>
      </div>
    );
  }, [prediction, result]);

  /* Autocomplete dropdown render */
  const renderDropdown = (
    isOpen: boolean,
    options: SearchableOption[],
    onSelect: (o: SearchableOption) => void,
    placeholder: string,
    inputRef: React.RefObject<HTMLInputElement>
  ) => {
    if (!isOpen || options.length === 0) return null;
    return (
      <div
        className="absolute z-50 w-full bg-navy-900 border border-navy-700 rounded-lg shadow-lg max-h-64 overflow-y-auto"
        ref={inputRef}
      >
        {options.map((opt, i) => (
          <div
            key={i}
            onClick={() => {
              onSelect(opt);
              if (opt.value) {
                if (opt.iata) setOrigin(opt.value);
                if (opt.dest) setDestination(opt.value);
              }
              if (opt.code) {
                /* airline selection handled separately */
              }
            }}
            className="px-4 py-2 text-sm text-navy-100 hover:bg-navy-800 cursor-pointer"
          >
            {opt.label}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="flex-1">
      {/* Hero Section */}
      <section className="home-hero-bg py-12 md:py-16 px-4">
        <div className="max-w-5xl mx-auto text-center">
          <h1 className="text-4xl sm:text-5xl md:text-6xl font-display-bold text-navy-50 mb-4 leading-tight">
            AeroDelay AI
          </h1>
          <p className="text-navy-400 text-base md:text-xl max-w-2xl mx-auto mb-8">
            Premium aviation intelligence platform for delay risk prediction
            and flight analytics
          </p>

          {/* Backend status */}
          <div
            data-testid="home-status"
            data-state={
              statusError ? "offline" : status ? "online" : "loading"
            }
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-navy-800 bg-navy-950/70 text-sm text-navy-300 mb-8"
          >
            <Radio className="w-4 h-4 text-cyan-500" aria-hidden="true" />
            {statusError
              ? `Backend offline - ${statusError}`
              : status
                ? `Backend online - model: ${status.services?.model ?? "unknown"}`
                : "Checking backend…"}
          </div>

          {/* Flight Search Form */}
          <GlassPanel className="max-w-3xl mx-auto text-left">
            <h2 className="text-xl font-semibold text-navy-100 mb-6 flex items-center gap-2">
              <Search className="w-5 h-5 text-cyan-500" aria-hidden="true" />
              Flight Search &amp; Delay-Risk Prediction
            </h2>

            <form data-testid="lookup-form" onSubmit={onSearch} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label
                    htmlFor="flight-number"
                    className="block text-sm font-medium text-navy-400 mb-2"
                  >
                    Flight number
                  </label>
                  <input
                    id="flight-number"
                    data-testid="lookup-flight-input"
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
                  <label htmlFor="flight-date" className="block text-sm font-medium text-navy-400 mb-2">
                    Flight date
                  </label>
                  <input
                    id="flight-date"
                    type="date"
                    required
                    value={flightDate}
                    onChange={(e) => setFlightDate(e.target.value)}
                    className="w-full bg-navy-900 border border-navy-700 rounded-lg px-4 py-3 text-navy-100 focus:outline-none focus:border-cyan-500 transition-colors"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="bg-cyan-600 hover:bg-cyan-500 disabled:opacity-60 text-navy-950 font-medium py-3 px-6 rounded-lg transition-all duration-200 shadow-lg shadow-cyan-500/20 flex items-center justify-center gap-2"
                >
                  {loading && (
                    <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                  )}
                  {loading ? "Searching…" : "Search & Predict"}
                </button>
              </div>

              {/* Origin + Destination selectors (optional pre-fill) */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-navy-800/40">
                <div className="relative">
                  <label
                    htmlFor="origin"
                    className="block text-sm font-medium text-navy-400 mb-2"
                  >
                    Origin Airport
                  </label>
                  <div className="relative">
                    <input
                      id="origin"
                      ref={originInputRef}
                      placeholder="Search airport code, city, or name"
                      value={origin}
                      onChange={(e) => {
                        setOrigin(e.target.value);
                        setOriginDropdownOpen(true);
                        const q = e.target.value;
                        if (q.length >= 1) {
                          searchAirports(q, setOriginOptions);
                        } else {
                          setOriginOptions([]);
                        }
                      }}
                      onFocus={() => setOriginDropdownOpen(true)}
                      onBlur={() => setTimeout(() => setOriginDropdownOpen(false), 200)}
                      className="w-full bg-navy-900 border border-navy-700 rounded-lg px-4 py-3 text-navy-100 focus:outline-none focus:border-cyan-500 transition-colors pr-12"
                    />
                    <Search className="absolute right-3 top-3 w-4 h-4 text-navy-500" aria-hidden="true" />
                    {renderDropdown(
                      originDropdownOpen,
                      originOptions,
                      (opt) => {
                        setOrigin(opt.label);
                        setOriginOptions([]);
                        setOriginDropdownOpen(false);
                      },
                      "Origin",
                      originInputRef
                    )}
                  </div>
                </div>

                <div className="relative">
                  <label
                    htmlFor="destination"
                    className="block text-sm font-medium text-navy-400 mb-2"
                  >
                    Destination Airport
                  </label>
                  <div className="relative">
                    <input
                      id="destination"
                      ref={destInputRef}
                      placeholder="Search airport code, city, or name"
                      value={destination}
                      onChange={(e) => {
                        setDestination(e.target.value);
                        setDestinationDropdownOpen(true);
                        const q = e.target.value;
                        if (q.length >= 1) {
                          searchAirports(q, setDestinationOptions);
                        } else {
                          setDestinationOptions([]);
                        }
                      }}
                      onFocus={() => setDestinationDropdownOpen(true)}
                      onBlur={() => setTimeout(() => setDestinationDropdownOpen(false), 200)}
                      className="w-full bg-navy-900 border border-navy-700 rounded-lg px-4 py-3 text-navy-100 focus:outline-none focus:border-cyan-500 transition-colors pr-12"
                    />
                    <Search className="absolute right-3 top-3 w-4 h-4 text-navy-500" aria-hidden="true" />
                    {renderDropdown(
                      destinationDropdownOpen,
                      destinationOptions,
                      (opt) => {
                        setDestination(opt.label);
                        setDestinationOptions([]);
                        setDestinationDropdownOpen(false);
                      },
                      "Destination",
                      destInputRef
                    )}
                  </div>
                </div>
              </div>

              {/* Error / result states */}
              {error && (
                <div
                  data-testid="lookup-error"
                  className="flex items-start gap-3 p-4 rounded-lg bg-red-500/10 border border-red-500/40 text-red-300 text-sm"
                >
                  <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" aria-hidden="true" />
                  <span>{error}</span>
                </div>
              )}

              {warnings.length > 0 && (
                <div
                  data-testid="lookup-warnings"
                  className="mb-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs"
                >
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
                  <span className="ml-2">{warnings.join(" · ")}</span>
                </div>
              )}
            </form>
          </GlassPanel>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      /* Search results / Prediction view                                   */
      {/* ------------------------------------------------------------------ */}

      {(view === "results" || view === "prediction") && result && (
        <section
          data-testid="lookup-result"
          className="py-10 px-4"
        >
          <div className="max-w-5xl mx-auto">
            <div className="flex items-center justify-between mb-6">
              <button
                onClick={() => setView("search")}
                className="inline-flex items-center gap-2 text-navy-400 hover:text-navy-200 text-sm font-medium transition-colors"
              >
                <X className="w-4 h-4" aria-hidden="true" /> New search
              </button>
              <span className="text-xs text-navy-500">
                Live provider data · {result.status ?? "status unknown"}
              </span>
            </div>

            {/* Flight info card */}
            <GlassPanel>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                <div>
                  <p className="text-navy-500 text-xs uppercase tracking-wider mb-1">
                    Flight
                  </p>
                  <p className="text-xl font-mono font-bold text-navy-100">
                    {result.flight_number}
                  </p>
                </div>
                <div>
                  <p className="text-navy-500 text-xs uppercase tracking-wider mb-1">
                    Airline
                  </p>
                  <p className="text-lg text-navy-100">{result.airline ?? "—"}</p>
                </div>
                <div>
                  <p className="text-navy-500 text-xs uppercase tracking-wider mb-1">
                    Date
                  </p>
                  <p className="text-lg text-navy-100">{result.flight_date ?? "—"}</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                <div>
                  <p className="text-navy-500 text-xs uppercase tracking-wider mb-1">
                    Origin
                  </p>
                  <div className="flex items-center gap-2">
                    <span className="bg-navy-800 px-2 py-1 rounded text-xs font-mono text-cyan-400">
                      {result.departure?.iata ?? "—"}
                    </span>
                    <span className="text-navy-300 text-sm">
                      {result.departure?.airport ?? "—"}
                    </span>
                  </div>
                  {result.departure?.scheduled && (
                    <p className="mt-1 text-navy-500 text-xs">
                      Scheduled:{" "}
                      <span className="text-navy-100">
                        {new Date(result.departure.scheduled).toLocaleTimeString(
                          [],
                          { hour: "2-digit", minute: "2-digit" }
                        )}
                      </span>
                    </p>
                  )}
                  {result.departure?.actual && (
                    <p className="text-navy-500 text-xs">
                      Actual:{" "}
                      <span className="text-navy-100">
                        {new Date(result.departure.actual).toLocaleTimeString(
                          [],
                          { hour: "2-digit", minute: "2-digit" }
                        )}
                      </span>
                    </p>
                  )}
                </div>
                <div>
                  <p className="text-navy-500 text-xs uppercase tracking-wider mb-1">
                    Destination
                  </p>
                  <div className="flex items-center gap-2">
                    <span className="bg-navy-800 px-2 py-1 rounded text-xs font-mono text-cyan-400">
                      {result.arrival?.iata ?? "—"}
                    </span>
                    <span className="text-navy-300 text-sm">
                      {result.arrival?.airport ?? "—"}
                    </span>
                  </div>
                  {result.arrival?.scheduled && (
                    <p className="mt-1 text-navy-500 text-xs">
                      Scheduled:{" "}
                      <span className="text-navy-100">
                        {new Date(result.arrival.scheduled).toLocaleTimeString(
                          [],
                          { hour: "2-digit", minute: "2-digit" }
                        )}
                      </span>
                    </p>
                  )}
                  {result.arrival?.actual && (
                    <p className="text-navy-500 text-xs">
                      Actual:{" "}
                      <span className="text-navy-100">
                        {new Date(result.arrival.actual).toLocaleTimeString(
                          [],
                          { hour: "2-digit", minute: "2-digit" }
                        )}
                      </span>
                    </p>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-4 mb-6">
                <StatusBadge
                  status={
                    {
                      scheduled: "scheduled",
                      active: "active",
                      landed: "landed",
                      cancelled: "cancelled",
                      diverted: "diverted",
                      delayed: "delayed",
                    }[result.status?.toLowerCase() ?? "unknown"] ?? "unknown"
                  }
                  size="md"
                />
                <span className="text-navy-400 text-sm">
                  Provider-reported status
                </span>
              </div>

              {result.gate && (
                <p className="text-navy-400 text-sm mb-6">
                  Gate: {result.gate}
                  {result.equipment ? ` · Aircraft: ${result.equipment}` : ""}
                </p>
              )}

              {!result.found && (
                <div
                  data-testid="lookup-empty"
                  className="p-4 rounded-lg bg-navy-900/50 border border-navy-700 text-navy-300 text-sm"
                >
                  {result.message ||
                    `No flight found for ${result.flight_number}.`}
                </div>
              )}

              {/* Prediction section */}
              {view === "prediction" && prediction && (
                <div className="mt-8">
                  <GlassPanel>
                    <div className="flex items-center justify-between mb-6">
                      <h3 className="text-xl font-semibold text-navy-100">
                        Delay-Risk Prediction
                      </h3>
                      <span className="text-xs text-navy-500 bg-navy-900 px-2 py-1 rounded">
                        Model: {prediction.model_version ?? "Phase 2"}
                      </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                      <div>
                        <p className="text-navy-500 text-xs uppercase tracking-wider mb-1">
                          Risk Score
                        </p>
                        <div className="text-3xl font-mono font-bold text-navy-100">
                          {(prediction.risk_score * 100).toFixed(1)}%
                        </div>
                        <p className="text-navy-500 text-xs mt-2">
                          Probability of departure delay ≥ 15 minutes
                        </p>
                      </div>
                      <div>
                        <p className="text-navy-500 text-xs uppercase tracking-wider mb-1">
                          Risk Category
                        </p>
                        <div className="flex items-center gap-2">
                          <StatusBadge
                            status={prediction.risk_level}
                            size="md"
                          />
                          <span className="text-navy-300 text-sm">
                            {(prediction.confidence * 100).toFixed(0)}% confidence
                          </span>
                        </div>
                        <p className="text-navy-500 text-xs mt-2">
                          Not a guarantee — see limitations below
                        </p>
                      </div>
                      <div>
                        <p className="text-navy-500 text-xs uppercase tracking-wider mb-1">
                          Model Version
                        </p>
                        <p className="text-navy-300 text-sm font-mono">
                          {prediction.model_version ?? "Phase 2 Ensemble v2.1"}
                        </p>
                      </div>
                    </div>

                    <div className="mb-6">
                      <p className="text-navy-500 text-xs uppercase tracking-wider mb-2">
                        What the score means
                      </p>
                      <p className="text-navy-300 text-sm mb-3">
                        The ML model estimates the probability that this flight
                        will depart 15 or more minutes after its scheduled time.
                        A score of 0.70+ indicates high delay risk, 0.40-0.70
                        medium, and below 0.40 low. This is a statistical
                        estimate based on historical patterns — not a certainty.
                      </p>
                    </div>

                    {prediction.factors && prediction.factors.length > 0 && (
                      <div className="mb-6">
                        <p className="text-navy-500 text-xs uppercase tracking-wider mb-2">
                          Contributing Factors
                        </p>
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                          {prediction.factors.map((f: { name: string; impact: string }, i: number) => (
                            <div key={i} className="p-3 rounded bg-navy-900/50 border border-navy-800/50">
                              <p className="text-navy-400 text-xs font-medium mb-1">{f.name}</p>
                              <p className="text-navy-300 text-sm">{f.impact}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {showModelLimitations}
                  </GlassPanel>
                </div>
              )}

              {view === "results" && !prediction && (
                <div className="mt-8">
                  <GlassPanel className="border-amber-500/30 bg-amber-500/5">
                    <div className="flex items-start gap-3">
                      <Info className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                      <div>
                        <h4 className="text-navy-100 font-medium mb-1">
                          Prediction not available for this route
                        </h4>
                        <p className="text-navy-400 text-sm">
                          The ML model does not support one or more categories
                          for this flight (carrier, origin, or destination).
                          No heuristic or synthetic prediction is provided.
                        </p>
                        {warnings.length > 0 && (
                          <ul className="mt-2 list-disc list-inside text-xs text-amber-300">
                            {warnings.map((w, i) => (
                              <li key={i}>{w}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                  </GlassPanel>
                </div>
              )}
            </GlassPanel>
          </div>
        </section>
      )}

      {/* Loading state */}
      {loading && view === "search" && (
        <div className="py-10 px-4">
          <div className="max-w-md mx-auto">
            <LoadingSkeleton rows={4} />
          </div>
        </div>
      )}

      {/* Featured Flights Section */}
      <section className="py-10 px-4">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col items-center gap-2 mb-8 text-center">
            <h2 className="text-2xl md:text-3xl font-display-bold text-navy-100">
              Featured Flights
            </h2>
            <span className="text-xs uppercase tracking-widest px-3 py-1 rounded-full bg-yellow-500/15 text-yellow-400 border border-yellow-500/30">
              Demo data · not live results
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              {
                id: "1",
                flightNumber: "AA 123",
                origin: "JFK",
                destination: "LAX",
                status: "On Time",
                scheduledDeparture: "08:15",
                aircraft: "B787-9",
                delayMinutes: 0,
              },
              {
                id: "2",
                flightNumber: "DL 456",
                origin: "SFO",
                destination: "JFK",
                status: "Delayed",
                scheduledDeparture: "13:40",
                aircraft: "A321",
                delayMinutes: 25,
              },
              {
                id: "3",
                flightNumber: "UA 789",
                origin: "ORD",
                destination: "SEA",
                status: "At Risk",
                scheduledDeparture: "16:30",
                aircraft: "737-8",
                delayMinutes: 18,
              },
            ].map((flight) => (
              <article
                key={flight.id}
                className="bg-navy-950/50 backdrop-blur-sm border border-navy-800/50 rounded-2xl p-6 hover:bg-navy-900/80 transition-colors duration-300"
                aria-label={`Demo flight ${flight.flightNumber} details`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-medium text-navy-100 mb-1">
                      {flight.flightNumber}
                    </h3>
                    <p className="text-navy-400 text-sm">
                      {flight.origin} → {flight.destination}
                    </p>
                  </div>
                  <StatusBadge status={flight.status} />
                </div>
                <div className="mt-4 flex items-center justify-between gap-3 text-sm">
                  <div className="flex items-center gap-3 text-navy-400">
                    <Plane className="w-4 h-4 text-navy-500" aria-hidden="true" />
                    <span>Dep {flight.scheduledDeparture}</span>
                    <span className="text-navy-500">{flight.aircraft}</span>
                  </div>
                  {flight.delayMinutes > 0 ? (
                    <span className="text-red-400 font-medium">
                      {flight.delayMinutes} min delay
                    </span>
                  ) : (
                    <span className="text-green-400 font-medium">On time</span>
                  )}
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <SectionDivider label="Delay Risk Preview" />

      <section className="pb-12 px-4">
        <div className="max-w-3xl mx-auto text-center">
          <p className="text-navy-400 text-sm md:text-base">
            Search any flight by number and date to get a real ML delay-risk
            score for supported routes.
          </p>
          <a
            href="/prediction"
            className="inline-block mt-5 bg-cyan-600 hover:bg-cyan-500 text-navy-950 font-medium py-3 px-8 rounded-lg transition-all duration-200 shadow-lg shadow-cyan-500/20"
          >
            Open Delay-Risk Prediction
          </a>
        </div>
      </section>
    </div>
  );
}