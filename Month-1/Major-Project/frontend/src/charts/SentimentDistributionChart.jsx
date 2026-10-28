import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const COLORS = {
  positive: '#10b981',
  neutral: '#f59e0b',
  negative: '#ef4444',
};

export default function SentimentDistributionChart({ data }) {
  const positive = data?.positive_count ?? data?.positive ?? 0;
  const neutral = data?.neutral_count ?? data?.neutral ?? 0;
  const negative = data?.negative_count ?? data?.negative ?? 0;

  const chartData = [
    { name: 'Positive', value: positive, color: COLORS.positive },
    { name: 'Neutral', value: neutral, color: COLORS.neutral },
    { name: 'Negative', value: negative, color: COLORS.negative },
  ].filter((d) => d.value > 0);

  const total = chartData.reduce((sum, d) => sum + d.value, 0);

  if (total === 0) {
    return (
      <div className="chart-container empty">
        <p className="empty-message">No sentiment data available</p>
      </div>
    );
  }

  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={100}
            paddingAngle={2}
            dataKey="value"
            nameKey="name"
            label={({ name, value, percent }) => `${name}: ${(percent * 100).toFixed(1)}%`}
            labelLine={false}
          >
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value, name) => [value, name]}
            labelFormatter={(name) => name}
            contentStyle={{
              background: '#1f293d',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '12px',
              boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
              color: '#f8fafc',
            }}
            itemStyle={{ color: '#f8fafc' }}
          />
          <Legend
            wrapperStyle={{ paddingTop: '1rem' }}
            formatter={(value) => {
              const item = chartData.find((d) => d.name === value);
              return item ? `${value} (${((item.value / total) * 100).toFixed(1)}%)` : value;
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}