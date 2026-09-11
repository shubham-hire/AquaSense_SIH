import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { ABLATION_RECORDS } from '../../data/ablationRecords';

export const AblationComparisonChart: React.FC = () => {
  const chartData = ABLATION_RECORDS.map((rec) => ({
    name: rec.id,
    component: rec.component,
    Baseline: rec.baselineValue,
    Tested: rec.testedValue,
    delta: rec.deltaPercent,
    metric: rec.baselineMetric,
  }));

  return (
    <div className="w-full h-80 bg-slate-950/80 p-4 rounded-xl border border-slate-800">
      <div className="text-xs font-mono text-slate-400 mb-3 flex items-center justify-between">
        <span>MEASURED PERFORMANCE DELTAS (SCRIPT-REGENERABLE)</span>
        <span className="text-cyan-400">Baseline vs Tested Value</span>
      </div>

      <ResponsiveContainer width="100%" height="85%">
        <BarChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 25 }}>
          <XAxis
            dataKey="name"
            stroke="#64748B"
            tick={{ fill: '#94A3B8', fontSize: 11, fontFamily: 'monospace' }}
          />
          <YAxis
            stroke="#64748B"
            tick={{ fill: '#94A3B8', fontSize: 11, fontFamily: 'monospace' }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#030A17',
              borderColor: '#1C7293',
              borderRadius: '0.5rem',
              fontFamily: 'monospace',
              fontSize: '11px',
            }}
          />
          <Legend
            wrapperStyle={{
              fontSize: '11px',
              fontFamily: 'monospace',
              paddingTop: '10px',
            }}
          />
          <Bar dataKey="Baseline" fill="#1C7293" name="Baseline Configuration" radius={[4, 4, 0, 0]} />
          <Bar dataKey="Tested" fill="#B23A2E" name="Tested / Alternative Configuration" radius={[4, 4, 0, 0]}>
            {chartData.map((entry, index) => {
              // Color green if adopted improvement, red if degraded
              const color = entry.delta > 0 ? '#10B981' : '#B23A2E';
              return <Cell key={`cell-${index}`} fill={color} />;
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};
