import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

export default function RatingDistributionChart({ data }) {
  const chartData = [5, 4, 3, 2, 1].map((star) => ({
    star: `${star}★`,
    count: data?.[String(star)] || 0,
  }));

  const total = chartData.reduce((sum, d) => sum + d.count, 0);
  const maxCount = Math.max(...chartData.map((d) => d.count), 1);

  if (total === 0) {
    return (
      <div className="chart-container empty">
        <p className="empty-message">No rating data available</p>
      </div>
    );
  }

  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis type="number" stroke="var(--text-secondary)" fontSize={12} />
          <YAxis
            type="category"
            dataKey="star"
            width={50}
            stroke="var(--text-secondary)"
            fontSize={12}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              boxShadow: 'var(--shadow-lg)',
            }}
            formatter={(value, name) => [value, name]}
            labelFormatter={(star) => star}
          />
          <Bar
            dataKey="count"
            radius={[0, 4, 4, 0]}
            maxBarSize={40}
          >
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={`hsl(${120 - (entry.star.charCodeAt(0) - 49) * 30}, 70%, 45%)`}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}