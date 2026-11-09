/*!
 * Next.js - AeroDelay AI Premium Frontend
 * Live Flight Tracking screen
 * 
 * Features:
   - Interactive flight path visualization
   - Real-time position indicators (demo data)
   - Filter controls
   - Reduced-motion support via dedicated hook
*/

import Link from "next/link";
import { MapPin, Truck, Search, X } from "lucide-react";
import { GlassPanel, StatusBadge, LoadingSkeleton, RiskGauge, SectionDivider } from "../components/ui";
import { useReducedMotion } from "../hooks/use-reduced-motion";

/* 
  Demo flight data for tracking - realistic positions
  Each flight has a simulated position along a route
*/
const demoTrackingFlights = [
  {
    id: "1",
    flightNumber: "AA 123",
    origin: "JFK",
    destination: "LAX",
    status: "On Time",
    riskScore: 0.08,
    altitude: 35000,
    groundSpeed: 480,
    heading: 270,
    latitude: 36.1625,
    longitude: -115.1398,
    lastUpdate: "Just now",
    aircraft: "B787-9",
    progress: 85, // percent along route
  },
  {
    id: "2",
    flightNumber: "DL 456",
    origin: "SFO",
    destination: "JFK",
    status: "Delayed",
    riskScore: 0.67,
    altitude: 28000,
    groundSpeed: 450,
    heading: 85,
    latitude: 37.6189,
    longitude: -122.3780,
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
    riskScore: 0.42,
    altitude: 31000,
    groundSpeed: 470,
    heading: 210,
    latitude: 41.9742,
    longitude: -110.6556,
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
    riskScore: 0.12,
    altitude: 38000,
    groundSpeed: 490,
    heading: 265,
    latitude: 33.9416,
    longitude: -118.4088,
    lastUpdate: "10 min ago",
    aircraft: "A320",
    progress: 20,
  },
];

/* 
  Route waypoints for path visualization
  Simulated flight paths between major airports
*/
const demoRoutes = [
  {
    id: "jfk-lax",
    name: "JFK → LAX",
    color: "cyan-500",
    waypoints: [
      { lat: 40.6413, lng: -73.7781 }, // JFK
      { lat: 36.1625, lng: -115.1398 }, // Over Arizona
      { lat: 33.9416, lng: -118.4088 }, // LGB area
      { lat: 33.9425, lng: -118.4084 }, // LAX
    ],
  },
  {
    id: "sfo-jfk",
    name: "SFO → JFK",
    color: "cyan-500",
    waypoints: [
      { lat: 37.6189, lng: -122.3780 }, // SFO
      { lat: 39.8283, lng: -98.5795 }, // Midwest
      { lat: 40.6413, lng: -73.7781 }, // JFK
    ],
  },
];

export default function TrackingPage() {
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
              placeholder="Flight number or route..." 
              className="bg-navy-900 border border-navy-700 rounded-lg px-4 py-2 focus:outline-none focus:border-cyan-500 text-sm"
              aria-label="Search flight"
            />
            <X className="w-5 h-5 cursor-pointer hover:text-red-400" aria-label="Close search" />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto p-4 sm:p-6">
        
        {/* Filters Section */}
        <SectionDivider label="Filters" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-navy-400 mb-2">Route</label>
            <select className="w-full bg-navy-900 border border-navy-700 rounded-lg px-3 py-2 focus:outline-none focus:border-cyan-500 transition-colors">
              <option>All Routes</option>
              <option>JFK → LAX</option>
              <option>SFO → JFK</option>
              <option>ORD → SEA</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-navy-400 mb-2">Status</label>
            <select className="w-full bg-navy-900 border border-navy-700 rounded-lg px-3 py-2 focus:outline-none focus:border-cyan-500 transition-colors">
              <option>All Statuses</option>
              <option>On Time</option>
              <option>Delayed</option>
              <option>At Risk</option>
              <option>Cancelled</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-navy-400 mb-2">Risk Threshold</label>
            <select className="w-full bg-navy-900 border border-navy-700 rounded-lg px-3 py-2 focus:outline-none focus:border-cyan-500 transition-colors">
              <option>All Levels</option>
              <option>Low (0-0.3)</option>
              <option>Medium (0.3-0.7)</option>
              <option>High (0.7+)</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-navy-400 mb-2">Aircraft</label>
            <select className="w-full bg-navy-900 border border-navy-700 rounded-lg px-3 py-2 focus:outline-none focus:border-cyan-500 transition-colors">
              <option>All Aircraft</option>
              <option>B787</option>
              <option>A321</option>
              <option>737-8</option>
              <option>A320</option>
            </select>
          </div>
        </div>

        {/* Flights List with Tracking Info */}
        <GlassPanel minHeight="max-content">
          <h2 className="text-2xl font-display-bold text-navy-100 mb-6">Live Flight Tracking</h2>
          
          {/* Reduced motion warning */}
          {reduced && (
            <div className="bg-red-100/30 border-l-4 border-red-500 rounded-tl-2x rounded-br-2x p-4 mb-6 text-red-400">
              <p className="text-sm">
                <strong>Reduced motion mode enabled.</strong> Animations have been 
                simplified for accessibility. Path movements will be static.
              </p>
            </div>
          )}

          {/* Flights Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {demoTrackingFlights.map((flight) => (
              <article 
                key={flight.id}
                className="bg-navy-950/50 backdrop-blur-sm border border-navy-800/50 rounded-2xl p-6 hover:bg-navy-900/80 transition-colors duration-300 cursor-pointer"
                aria-label={`Tracking for ${flight.flightNumber}`}
              >
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <span className="text-2xl font-bold text-navy-100">{flight.flightNumber}</span>
                    <StatusBadge status={flight.status} size="sm" />
                  </div>
                  
                  <RiskGauge score={flight.riskScore} size="sm" />
                </div>

                <div className="grid grid-cols-2 gap-4 text-navy-400 text-sm mb-6">
                  <div>
                    <p className="font-medium">Origin</p>
                    <p>{flight.origin}</p>
                  </div>
                  <div>
                    <p className="font-medium">Destination</p>
                    <p>{flight.destination}</p>
                  </div>
                  <div>
                    <p className="font-medium">Altitude</p>
                    <p>{flight.altitude},000 ft</p>
                  </div>
                  <div>
                    <p className="font-medium">Ground Speed</p>
                    <p>{flight.groundSpeed} kt</p>
                  </div>
                </div>

                <div className="mb-6">
                  <p className="text-navy-500 text-sm font-medium mb-2">Route Progress</p>
                  <div className="h-2 bg-navy-900 rounded-full overflow-hidden">
                    <div 
                      className={`h-full bg-cyan-600 rounded-full transition-width duration-750 ${flight.progress > 50 ? 'transition-delay-2000' : ''}`}
                      style={{ width: `${flight.progress}%` }}
                    />
                  </div>
                  <p className="text-navy-500 text-xs mt-2">{flight.progress}% en route</p>
                </div>

                <div className="flex items-center gap-3 pt-4 border-t border-navy-800/20">
                  <div className="w-8 h-8 rounded-full bg-navy-800 flex items-center justify-center flex-shrink-0">
                    <i className={`lucide-Truck w-4 h-4 text-cyan-400`} />
                  </div>
                  <div>
                    <p className="text-navy-500 text-sm">Last update: {flight.lastUpdate}</p>
                    <p className="text-navy-400 text-xs">Projected arrival: {(flight.progress / 100 * 3 + 1).toFixed(0)}h</p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </GlassPanel>

        {/* Map Area - simplified 2.5D representation */}
        <GlassPanel minHeight="384" className="mt-8">
          <h2 className="text-xl font-medium text-navy-400 mb-4">Flight Paths</h2>
          
          {/* Simplified canvas-based path visualization */}
          <div className="relative h-full">
            {/* Route paths - simple lines */}
            <svg className="absolute inset-0 w-full h-full" aria-hidden="true">
              {demoRoutes.map((route) => (
                <path
                  key={route.id}
                  d={route.waypoints.map((wp, i) => i === 0 ? `M${wp.lat * 0.0001} ${wp.lng * 0.0001}` : `L${wp.lat * 0.0001} ${wp.lng * 0.0001}`).join(" ")}
                  stroke={route.color}
                  strokeWidth={2}
                  fill="none"
                  opacity={0.6}
                />
              ))}
            </svg>
            
            {/* Flight position markers */}
            <g className="absolute inset-0">
              {demoTrackingFlights.map((flight) => (
                <circle
                  key={flight.id}
                  cx={flight.latitude * 0.0001}
                  cy={flight.longitude * 0.0001}
                  r={flight.progress > 50 ? 4 : 3}
                  fill={flight.riskScore > 0.5 ? "red" : flight.riskScore > 0.3 ? "orange" : "cyan"}
                  opacity={0.8}
                />
              ))}
            </g>
          </div>
          
          {/* Legend */}
          <div className="absolute bottom-4 left-4 flex gap-2">
            <div className="flex items-center gap-1 text-xs">
              <span className="w-2 h-2 rounded bg-cyan-500" />
              <span>Low risk</span>
            </div>
            <div className="flex items-center gap-1 text-xs">
              <span className="w-2 h-2 rounded bg-yellow-500" />
              <span>Medium risk</span>
            </div>
            <div className="flex items-center gap-1 text-xs">
              <span className="w-2 h-2 rounded bg-red-500" />
              <span>High risk</span>
            </div>
          </div>
        </GlassPanel>
      </div>
    </main>
  );
}