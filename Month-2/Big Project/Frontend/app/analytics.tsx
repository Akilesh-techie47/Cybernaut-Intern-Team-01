/*!
 * Next.js - AeroDelay AI Premium Frontend
 * Flight and Route Analytics screen
 * 
 * Features:
   - Route performance analytics
   - Delay distribution charts
   - Airline comparison
   - Demo data visualizations
   - Reduced-motion support
*/

import Link from "next/link";
import { 
  BarChart3, Sun, CloudRain, Wind,
  MapPin, Loader2, Shield, Clock,
  TrendingUp, TrendingDown, Globe,
  LayoutGrid, Calendar, Search
} from "lucide-react";
import { GlassPanel, SectionDivider, RiskGauge, StatusBadge, LoadingSkeleton } from "../components/ui";
import { useReducedMotion } from "../hooks/use-reduced-motion";

/* 
  Demo analytics data - route performance summaries
  Simulated analytics from the BTS dataset
*/
const demoRoutesAnalytics = [
  {
    id: "jfk-lax",
    route: "JFK → LAX",
    onTimePct: 78,
    delayedPct: 15,
    cancelledPct: 2,
    averageDelay: 22,
    flightsThisMonth: 248,
    airlineBreakdown: [
      { airline: "AA", pctOnTime: 82, flights: 97 },
      { airline: "DL", pctOnTime: 74, flights: 65 },
      { airline: "UA", pctOnTime: 76, flights: 52 },
      { airline: "B6", pctOnTime: 88, flights: 34 },
    ],
  },
  {
    id: "sfo-jfk",
    route: "SFO → JFK",
    onTimePct: 65,
    delayedPct: 24,
    cancelledPct: 3,
    averageDelay: 35,
    flightsThisMonth: 183,
    airlineBreakdown: [
      { airline: "DL", pctOnTime: 68, flights: 78 },
      { airline: "UA", pctOnTime: 62, flights: 56 },
      { airline: "AA", pctOnTime: 66, flights: 34 },
      { airline: "AS", pctOnTime: 71, flights: 15 },
    ],
  },
  {
    id: "ord-sea",
    route: "ORD → SEA",
    onTimePct: 71,
    delayedPct: 21,
    cancelledPct: 1,
    averageDelay: 28,
    flightsThisMonth: 156,
    airlineBreakdown: [
      { airline: "AA", pctOnTime: 75, flights: 61 },
      { airline: "UA", pctOnTime: 68, flights: 52 },
      { airline: "F9", pctOnTime: 65, flights: 28 },
      { airline: "WN", pctOnTime: 73, flights: 15 },
    ],
  },
];

export default function AnalyticsPage() {
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
              placeholder="Search routes..." 
              className="bg-navy-900 border border-navy-700 rounded-lg px-4 py-2 focus:outline-none focus:border-cyan-500 text-sm"
              aria-label="Search routes"
            />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto p-4 sm:p-6">
        
        {/* Overview Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[
            { label: "Total Routes", value: "3", icon: "Globe", bg: "cyan-500" },
            { label: "Avg Delay", value: "28 min", icon: "Clock", bg: "yellow-500" },
            { label: "This Month", value: "587 flights", icon: "Calendar", bg: "cyan-400" },
            { label: "On-Time Rate", value: "71%", icon: "TrendingUp", bg: "green-500" },
          ].map((stat) => (
            <GlassPanel key={stat.label} minHeight="100" className="p-5 text-center">
              <div className="text-3xl font-display-bold text-{stat.bg} mb-2">{stat.value}</div>
              <p className="text-navy-500 text-xs uppercase tracking-wider">{stat.label}</p>
              <i className={`lucide-${stat.icon} w-6 h-6 text-navy-800 mx-auto mt-2`} />
            </GlassPanel>
          ))}
        </div>

        {/* Routes Comparison */}
        <SectionDivider label="Route Performance" />
        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {demoRoutesAnalytics.map((route) => (
            <GlassPanel 
              key={route.id} 
              minHeight="300"
              className="p-6 hover:bg-navy-900/80 transition-colors duration-300"
            >
              <h3 className="text-lg font-medium text-navy-100 mb-4">{route.route}</h3>
              
              {/* On-time status chips */}
              <div className="grid grid-cols-3 gap-3 mb-6">
                <div>
                  <StatusBadge status="On Time" size="sm" />
                  <p className="text-navy-500 text-xs mt-1">{route.onTimePct}% On Time</p>
                </div>
                <div>
                  <StatusBadge status="Delayed" size="sm" />
                  <p className="text-navy-500 text-xs mt-1">{route.delayedPct}% Delayed</p>
                </div>
                <div>
                  <StatusBadge status="Cancelled" size="sm" />
                  <p className="text-navy-500 text-xs mt-1">{route.cancelledPct}% Cancelled</p>
                </div>
              </div>

              {/* Average delay */}
              <div className="mb-6">
                <p className="text-navy-500 text-sm mb-1">Average Delay</p>
                <p className="text-navy-100 font-medium">{route.averageDelay} min</p>
              </div>

              {/* Airline breakdown */}
              <p className="text-navy-500 text-sm font-medium mb-2">Airline Performance</p>
              <div className="space-y-2">
                {route.airlineBreakdown.map((airline) => (
                  <div 
                    key={airline.airline}
                    className="flex items-center justify-between text-navy-400 text-sm"
                  >
                    <span>{airline.airline}</span>
                    <span className="font-medium">{airline.pctOnTime}% on time</span>
                  </div>
                ))}
              </div>
            </GlassPanel>
          ))}
        </div>

        {/* Delay Distribution Insights */}
        <SectionDivider label="Delay Distribution Insights" className="mt-8" />
        
        <GlassPanel minHeight="max-content" className="mt-8">
          <h2 className="text-2xl font-display-bold text-navy-100 mb-6">Delay Analysis</h2>
          
          {/* Key insights cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div>
              <p className="text-navy-500 text-sm mb-3">Primary Delay Factors</p>
              <ul className="space-y-2 text-navy-400 text-sm">
                <li>Weather conditions (42% of delays)</li>
                <li>ATC congestion (28% of delays)</li>
                <li>Aircraft maintenance (18% of delays)</li>
                <li>Airport operations (12% of delays)</li>
              </ul>
            </div>

            <div>
              <p className="text-navy-500 text-sm mb-3">On-Time Improvement</p>
              <ul className="space-y-2 text-navy-400 text-sm">
                <li>Optimized routing: +8% improvement</li>
                <li>Fleet modernization: +5% improvement</li>
                <li>ATC flow improvements: +6% improvement</li>
              </ul>
            </div>
          </div>

          {/* Reduced motion chart note */}
          {reduced && (
            <div className="mt-6 p-4 bg-navy-900/50 rounded-lg text-red-400">
              <p className="text-sm">
                <strong>Reduced motion mode.</strong> Static charts displayed. 
                Interactive charts would feature animated bar growth and color transitions.
              </p>
            </div>
          )}
        </GlassPanel>
      </div>
    </main>
  );
}