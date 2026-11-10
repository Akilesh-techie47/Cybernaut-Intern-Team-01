"use client";

/*!
 * Next.js - AeroDelay AI Premium Frontend
 * Live Flight Tracking screen
 *
 * Phase 5.3: flight lookup is served by the FastAPI backend
 * (/api/v1/flights/lookup -> AviationStack, credentials server-side).
 * Simulated positions remain clearly labeled as demo data.
 */

import { useState } from "react";
import { Search, Loader2, AlertTriangle, MapPin, Plane } from "lucide-react";
import {
  GlassPanel,
  StatusBadge,
  SectionDivider,
  LoadingSkeleton,
} from "../../components/ui";
import { api, describeApiError, type FlightLookupResult } from "../../lib/api";

/* Demo flight positions - simulated, clearly labeled as demo */
const demoTrackingFlights = [
  {
    id: "1",
    flightNumber: "AA 123",
    origin: "JFK",
    destination: "LAX",
    status: "On Time",
    altitude: 35000,
    groundSpeed: 480,
    lastUpdate: "Just now",
    aircraft: "B787-9",
    progress: 85,
  },
  {
    id: "2",
    flightNumber: "DL 456",
    origin: "SFO",
    destination: "JFK",
    status: "Delayed",
    altitude: 28000,
    groundSpeed: 450,
    lastUpdate: "2 min ago",
    aircraft: "A321",
    progress: 55,
  },
  {
    id: "3",
    flightNumber: "UA 789",
    origin: "ORD",
    destination: "SEA",
    status: "At Risk",
    altitude: 31000,
    groundSpeed: 470,
    lastUpdate: "5 min ago",
    aircraft: "737-8",
    progress: 35,
  },
  {
    id: "4",
    flightNumber: "B6 180",
    origin: "LGB",
    destination: "SEA",
    status: "On Time",
    altitude: 38000,
    groundSpeed: 490,
    lastUpdate: "10 min ago",
    aircraft: "A320",
    progress: 20,
  },
];

export default function TrackingPage() {
  const [flightNumber, setFlightNumber] = useState("");
  const [origin, setOrigin] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<FlightLookupResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onLookup(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);

    if (!flightNumber.trim()) {
      setError("Please enter a flight number to track.");
      return;
    }

    setLoading(true);
    try {
      const res = await api.lookup(flightNumber.trim(), origin || undefined);
      setResult(res);
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex-1 px-4 py-8">
      <div className="max-w-7xl mx-auto">
        {/* Page heading */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl md:text-3xl font-display-bold text-navy-100">
              Live Flight Tracking
            </h1>
            <p className="text-navy-400 text-sm mt-1">
              Look up live status from the backend flight service.
            </p>
          </div>
        </div>

        {/* Lookup form */}
        <GlassPanel className="mb-8">
          <form
            data-testid="tracking-form"
            onSubmit={onLookup}
            className="grid grid-cols-1 sm:grid-cols-[1fr_160px_auto] gap-4 items-end"
          >
            <div>
              <label
                htmlFor="track-flight-number"
                className="block text-sm font-medium text-navy-400 mb-2"
              >
                Flight number
              </label>
              <input
                id="track-flight-number"
                data-testid="tracking-flight-input"
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
              <label
                htmlFor="track-origin"
                className="block text-sm font-medium text-navy-400 mb-2"
              >
                Origin
              </label>
              <select
                id="track-origin"
                value={origin}
                onChange={(e) => setOrigin(e.target.value)}
                className="w-full bg-navy-900 border border-navy-700 rounded-lg px-4 py-3 text-navy-100 focus:outline-none focus:border-cyan-500 transition-colors"
              >
                <option value="">Any</option>
                <option value="JFK">JFK</option>
                <option value="LAX">LAX</option>
                <option value="SFO">SFO</option>
                <option value="ORD">ORD</option>
                <option value="SEA">SEA</option>
              </select>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="bg-cyan-600 hover:bg-cyan-500 disabled:opacity-60 text-navy-950 font-medium py-3 px-6 rounded-lg transition-all duration-200 flex items-center justify-center gap-2"
            >
              {loading && (
                <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
              )}
              <Search className="w-4 h-4" aria-hidden="true" />
              {loading ? "Tracking…" : "Track Flight"}
            </button>
          </form>

          {/* Result states */}
          <div className="mt-6" aria-live="polite">
            {loading && (
              <div data-testid="tracking-loading">
                <LoadingSkeleton rows={3} />
              </div>
            )}

            {error && (
              <div
                data-testid="tracking-error"
                className="flex items-start gap-3 p-4 rounded-lg bg-red-500/10 border border-red-500/40 text-red-300 text-sm"
              >
                <AlertTriangle
                  className="w-5 h-5 shrink-0 mt-0.5"
                  aria-hidden="true"
                />
                <span>{error}</span>
              </div>
            )}

            {result && result.found && (
              <div
                data-testid="tracking-result"
                className="p-5 rounded-lg bg-navy-900/70 border border-cyan-500/30"
              >
                <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                  <div className="flex items-center gap-3">
                    <Plane className="w-5 h-5 text-cyan-500" aria-hidden="true" />
                    <span className="text-xl font-semibold text-navy-100">
                      {result.flight_number}
                    </span>
                    <span className="text-navy-400 text-sm">
                      {result.airline}
                    </span>
                  </div>
                  <StatusBadge status={result.status || "unknown"} size="md" />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
                  <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800/60">
                    <p className="text-navy-500 text-xs mb-1">Departure</p>
                    <p className="text-navy-100 font-medium">
                      {result.departure?.iata || "—"}
                    </p>
                    <p className="text-navy-400 text-xs">
                      {result.departure?.airport || ""}
                    </p>
                    <p className="text-navy-500 text-xs mt-1">
                      {result.departure?.scheduled || "—"}
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800/60">
                    <p className="text-navy-500 text-xs mb-1">Arrival</p>
                    <p className="text-navy-100 font-medium">
                      {result.arrival?.iata || "—"}
                    </p>
                    <p className="text-navy-400 text-xs">
                      {result.arrival?.airport || ""}
                    </p>
                    <p className="text-navy-500 text-xs mt-1">
                      {result.arrival?.scheduled || "—"}
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800/60">
                    <p className="text-navy-500 text-xs mb-1">Gate</p>
                    <p className="text-navy-100 font-medium">
                      {result.gate || "—"}
                    </p>
                    <p className="text-navy-500 text-xs mt-1">
                      {result.equipment || "Aircraft n/a"}
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800/60">
                    <p className="text-navy-500 text-xs mb-1">Flight date</p>
                    <p className="text-navy-100 font-medium">
                      {result.flight_date || "—"}
                    </p>
                    <p className="text-cyan-400 text-xs mt-1">
                      Live provider data
                    </p>
                  </div>
                </div>
              </div>
            )}

            {result && !result.found && (
              <div
                data-testid="tracking-empty"
                className="p-4 rounded-lg bg-navy-900/70 border border-navy-700 text-navy-300 text-sm"
              >
                {result.message ||
                  "No matching flight found. Try an airline code + number (e.g. AA100)."}
              </div>
            )}
          </div>
        </GlassPanel>

        {/* Demo tracking list */}
        <div className="flex flex-col items-center gap-2 mb-6 text-center">
          <h2 className="text-xl md:text-2xl font-display-bold text-navy-100">
            Tracked Flights
          </h2>
          <span className="text-xs uppercase tracking-widest px-3 py-1 rounded-full bg-yellow-500/15 text-yellow-400 border border-yellow-500/30">
            Demo positions · simulated, not live telemetry
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {demoTrackingFlights.map((flight) => (
            <article
              key={flight.id}
              className="bg-navy-950/50 backdrop-blur-sm border border-navy-800/50 rounded-2xl p-6 hover:bg-navy-900/80 transition-colors duration-300"
              aria-label={`Demo tracking for ${flight.flightNumber}`}
            >
              <div className="flex items-center justify-between gap-3 mb-4">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="text-xl font-bold text-navy-100 truncate">
                    {flight.flightNumber}
                  </span>
                  <StatusBadge status={flight.status} />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-navy-400 text-sm mb-5">
                <div>
                  <p className="font-medium text-navy-500 text-xs">Origin</p>
                  <p>{flight.origin}</p>
                </div>
                <div>
                  <p className="font-medium text-navy-500 text-xs">Destination</p>
                  <p>{flight.destination}</p>
                </div>
                <div>
                  <p className="font-medium text-navy-500 text-xs">Altitude</p>
                  <p>{flight.altitude.toLocaleString()} ft</p>
                </div>
                <div>
                  <p className="font-medium text-navy-500 text-xs">Ground Speed</p>
                  <p>{flight.groundSpeed} kt</p>
                </div>
              </div>

              <div className="mb-4">
                <div className="flex items-center justify-between text-xs text-navy-500 mb-1">
                  <span>Route progress</span>
                  <span>{flight.progress}%</span>
                </div>
                <div className="h-2 bg-navy-900 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-cyan-500 rounded-full"
                    style={{ width: `${flight.progress}%` }}
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 pt-4 border-t border-navy-800/40 text-navy-500 text-xs">
                <MapPin className="w-3.5 h-3.5" aria-hidden="true" />
                Last update: {flight.lastUpdate} · {flight.aircraft}
              </div>
            </article>
          ))}
        </div>

        <SectionDivider label="Tracking Notes" className="mt-10" />

        <GlassPanel>
          <p className="text-navy-400 text-sm">
            Live lookups query the backend{" "}
            <code className="text-cyan-400">/api/v1/flights/lookup</code>{" "}
            endpoint, which calls AviationStack from the server. API
            credentials are never exposed to the browser. The cards above are
            static demo content used to illustrate the tracking layout.
          </p>
        </GlassPanel>
      </div>
    </div>
  );
}
