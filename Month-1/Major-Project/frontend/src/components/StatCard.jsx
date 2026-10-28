const COLOR_MAP = {
  indigo: { bg: 'rgba(99,102,241,0.12)', color: '#818cf8', glow: 'rgba(99,102,241,0.2)' },
  blue:   { bg: 'rgba(59,130,246,0.12)',  color: '#60a5fa', glow: 'rgba(59,130,246,0.2)' },
  green:  { bg: 'rgba(16,185,129,0.12)',  color: '#34d399', glow: 'rgba(16,185,129,0.2)' },
  red:    { bg: 'rgba(239,68,68,0.12)',   color: '#f87171', glow: 'rgba(239,68,68,0.2)' },
  yellow: { bg: 'rgba(245,158,11,0.12)', color: '#fbbf24', glow: 'rgba(245,158,11,0.2)' },
};

export default function StatCard({ title, value, icon, color = 'indigo', trend, trendUp = true }) {
  const c = COLOR_MAP[color] || COLOR_MAP.indigo;

  return (
    <div
      className="stat-card card"
      style={{ borderColor: c.glow, boxShadow: `0 0 20px ${c.glow}` }}
    >
      <div className="stat-header">
        <span className="stat-icon" style={{ background: c.bg, color: c.color }}>
          {icon}
        </span>
        <h3 className="stat-title">{title}</h3>
      </div>
      <div className="stat-value" style={{ color: c.color }}>
        {value}
      </div>
      {trend && (
        <div
          className={`stat-trend ${trendUp ? 'up' : 'down'}`}
          style={{ color: trendUp ? '#34d399' : '#f87171' }}
        >
          {trendUp ? '↑' : '↓'} {trend}
        </div>
      )}
    </div>
  );
}