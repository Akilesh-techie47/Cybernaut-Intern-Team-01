import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

export default function KeywordsChart({ keywords }) {
  if (!keywords || keywords.length === 0) {
    return (
      <div className="chart-container empty">
        <p className="empty-message">No keywords available</p>
      </div>
    );
  }

  const chartData = keywords.map((word, index) => ({
    word,
    count: keywords.length - index,
  })).reverse();

  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis type="number" stroke="var(--text-secondary)" fontSize={12} />
          <YAxis
            type="category"
            dataKey="word"
            width={100}
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
            formatter={(value) => [value, 'Frequency']}
          />
          <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={30}>
            {chartData.map((_, index) => (
              <Cell key={`cell-${index}`} fill="var(--primary)" />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}