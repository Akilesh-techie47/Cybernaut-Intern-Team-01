"use client";

/*!
 * Next.js - AeroDelay AI Premium Frontend
 * Flight and Route Analytics screen
 *
 * Phase 5.3: route analytics are fetched from the backend
 * (/api/v1/routes/analytics) with loading, error and empty states.
 */

import { useEffect, useState } from "react";
import {
  BarChart3,
  Globe,
  Clock,
  Calendar,
  TrendingUp,
  AlertTriangle,
} from "lucide-react";
import {
  GlassPanel,
  SectionDivider,
  StatusBadge,
  LoadingSkeleton,
} from "../../components/ui";
import { api, describeApiError, type RouteAnalytics } from "../../lib/api";

export default function AnalyticsPage() {
  const [routes, setRoutes] = useState<RouteAnalytics[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .analytics()
      .then((data) => {
        if (!cancelled) setRoutes(data);
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

  /* Derived overview stats - computed from real backend responses only */
  const totalRoutes = routes?.length ?? 0;
  const totalFlights =
    routes?.reduce((sum, r) => sum + r.flights_this_month, 0) ?? 0;
  const avgDelay = totalRoutes
    ? Math.round(
        routes!.reduce((sum, r) => sum + r.average_delay, 0) / totalRoutes,
      )
    : 0;
  const onTimeRate = totalRoutes
    ? Math.round(
        routes!.reduce((sum, r) => sum + r.on_time_pct, 0) / totalRoutes,
      )
    : 0;

  const stats = [
    { label: "Total Routes", value: String(totalRoutes), icon: Globe },
    { label: "Avg Delay", value: `${avgDelay} min`, icon: Clock },
    { label: "This Month", value: `${totalFlights} flights`, icon: Calendar },
    { label: "On-Time Rate", value: `${onTimeRate}%`, icon: TrendingUp },
  ];

  return (
    <div className="flex-1 px-4 py-8">
      <div className="max-w-7xl mx-auto">
        {/* Heading */}
        <div className="mb-6">
          <h1 className="text-2xl md:text-3xl font-display-bold text-navy-100">
            Route Analytics
          </h1>
          <p className="text-navy-400 text-sm mt-1">
            Performance summaries served by{" "}
            <code className="text-cyan-400">/api/v1/routes/analytics</code>.
          </p>
        </div>

        {/* Loading */}
        {loading && (
          <div data-testid="analytics-loading" className="mb-8">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              {[0, 1, 2, 3].map((i) => (
                <GlassPanel key={i} className="p-5">
                  <LoadingSkeleton rows={2} />
                </GlassPanel>
              ))}
            </div>
            <LoadingSkeleton rows={4} />
          </div>
        )}

        {/* Error */}
        {error && !loading && (
          <div
            data-testid="analytics-error"
            className="flex items-start gap-3 p-4 rounded-lg bg-red-500/10 border border-red-500/40 text-red-300 text-sm mb-8"
          >
            <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        {/* Content */}
        {routes && !loading && (
          <>
            {/* Overview stats */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              {stats.map((stat) => {
                const Icon = stat.icon;
                return (
                  <GlassPanel key={stat.label} className="p-5 text-center">
                    <Icon
                      className="w-6 h-6 text-cyan-500 mx-auto mb-2"
                      aria-hidden="true"
                    />
                    <div className="text-2xl md:text-3xl font-display-bold text-navy-100 mb-1">
                      {stat.value}
                    </div>
                    <p className="text-navy-500 text-xs uppercase tracking-wider">
                      {stat.label}
                    </p>
                  </GlassPanel>
                );
              })}
            </div>

            {/* Routes comparison */}
            <SectionDivider label="Route Performance" />

            <div
              data-testid="analytics-routes"
              className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6"
            >
              {routes.map((route) => (
                <GlassPanel
                  key={route.route}
                  className="p-6 hover:border-navy-700 transition-colors duration-300"
                >
                  <h3 className="text-lg font-medium text-navy-100 mb-4">
                    {route.route}
                  </h3>

                  <div className="grid grid-cols-3 gap-3 mb-5">
                    <div>
                      <StatusBadge status="On Time" />
                      <p className="text-navy-500 text-xs mt-1.5">
                        {route.on_time_pct}% On Time
                      </p>
                    </div>
                    <div>
                      <StatusBadge status="Delayed" />
                      <p className="text-navy-500 text-xs mt-1.5">
                        {route.delayed_pct}% Delayed
                      </p>
                    </div>
                    <div>
                      <StatusBadge status="Cancelled" />
                      <p className="text-navy-500 text-xs mt-1.5">
                        {route.cancelled_pct}% Cancelled
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 text-sm mb-5">
                    <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800/60">
                      <p className="text-navy-500 text-xs">Average delay</p>
                      <p className="text-navy-100 font-medium">
                        {route.average_delay} min
                      </p>
                    </div>
                    <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800/60">
                      <p className="text-navy-500 text-xs">Flights / month</p>
                      <p className="text-navy-100 font-medium">
                        {route.flights_this_month}
                      </p>
                    </div>
                  </div>

                  <p className="text-navy-500 text-sm font-medium mb-2">
                    Airline performance
                  </p>
                  <div className="space-y-2">
                    {route.airline_breakdown.map((airline) => (
                      <div
                        key={airline.airline}
                        className="flex items-center justify-between text-navy-400 text-sm"
                      >
                        <span>{airline.airline}</span>
                        <div className="flex items-center gap-2">
                          <div className="w-20 h-1.5 bg-navy-900 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-cyan-500 rounded-full"
                              style={{
                                width: `${airline.pct_on_time}%`,
                              }}
                            />
                          </div>
                          <span className="font-medium text-navy-300 text-xs">
                            {airline.pct_on_time}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </GlassPanel>
              ))}
            </div>
          </>
        )}

        {/* Insights */}
        <SectionDivider label="Delay Distribution Insights" className="mt-10" />

        <GlassPanel>
          <div className="flex flex-col items-start gap-3 mb-5">
            <h2 className="text-xl md:text-2xl font-display-bold text-navy-100">
              Delay Analysis
            </h2>
            <span className="text-xs uppercase tracking-widest px-3 py-1 rounded-full bg-yellow-500/15 text-yellow-400 border border-yellow-500/30">
              Illustrative content · not derived from live data
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div>
              <p className="text-navy-500 text-sm mb-3">
                Common delay factors (industry typical)
              </p>
              <ul className="space-y-2 text-navy-400 text-sm list-disc pl-5">
                <li>Weather conditions</li>
                <li>Air traffic control congestion</li>
                <li>Aircraft maintenance</li>
                <li>Airport operations</li>
              </ul>
            </div>
            <div>
              <p className="text-navy-500 text-sm mb-3">Reading the charts</p>
              <ul className="space-y-2 text-navy-400 text-sm list-disc pl-5">
                <li>
                  Percentages above come directly from the backend analytics
                  payload
                </li>
                <li>
                  Airline breakdowns describe the routes served by the API
                </li>
                <li>
                  This screen does not invent numbers - unavailable data shows
                  an error state instead
                </li>
              </ul>
            </div>
          </div>

          <div className="mt-6 pt-5 border-t border-navy-800/60 flex items-center gap-2 text-navy-500 text-xs">
            <BarChart3 className="w-4 h-4" aria-hidden="true" />
            Data source: FastAPI backend (Phase 4) - static route analytics
            derived from Phase 2 benchmark patterns.
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}
