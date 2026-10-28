import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const COLORS = {
  positive: '#10b981',
  neutral: '#f59e0b',
  negative: '#ef4444',
};

export default function SentimentTrendChart({ data }) {
  if (!data || data.length === 0) {
    return (
      <div className="chart-container empty">
        <p className="empty-message">No trend data available</p>
      </div>
    );
  }

  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="date"
            stroke="var(--text-secondary)"
            fontSize={12}
            tickFormatter={(value) => value}
            interval="preserveStartEnd"
          />
          <YAxis
            stroke="var(--text-secondary)"
            fontSize={12}
            domain={[0, 'dataMax + 10']}
            tickFormatter={(value) => `${value}%`}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              boxShadow: 'var(--shadow-lg)',
            }}
            formatter={(value, name) => [value, name]}
            labelFormatter={(date) => `Date: ${date}`}
          />
          <Legend wrapperStyle={{ paddingTop: '1rem' }} />
          <Line
            type="monotone"
            dataKey="positive_pct"
            stroke={COLORS.positive}
            strokeWidth={2}
            dot={{ r: 4 }}
            name="Positive %"
            activeDot={{ r: 6 }}
          />
          <Line
            type="monotone"
            dataKey="neutral_pct"
            stroke={COLORS.neutral}
            strokeWidth={2}
            dot={{ r: 4 }}
            name="Neutral %"
            activeDot={{ r: 6 }}
          />
          <Line
            type="monotone"
            dataKey="negative_pct"
            stroke={COLORS.negative}
            strokeWidth={2}
            dot={{ r: 4 }}
            name="Negative %"
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}