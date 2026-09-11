import React from 'react';
import { ABLATION_RECORDS } from '../../data/ablationRecords';
import { Flame, XCircle, CheckCircle2, AlertTriangle } from 'lucide-react';

export const AblationCaption: React.FC = () => {
  return (
    <div className="space-y-3">
      {ABLATION_RECORDS.map((rec) => {
        const isKilled = rec.decision === 'KILLED_FOR_DETECTION';
        const isAdopted = rec.decision === 'ADOPTED';

        return (
          <div
            key={rec.id}
            className="p-4 rounded-xl glass-panel border border-slate-800 space-y-2 text-xs font-mono"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-bold text-white text-sm">{rec.id}: {rec.component}</span>
                <span className="text-[10px] text-slate-400 bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">
                  {rec.category}
                </span>
              </div>

              <span
                className={`px-2 py-0.5 rounded text-[11px] font-bold border ${
                  isKilled
                    ? 'bg-rose-950/60 text-rose-300 border-rose-500/50'
                    : isAdopted
                    ? 'bg-emerald-950/60 text-emerald-300 border-emerald-500/50'
                    : 'bg-amber-950/60 text-amber-300 border-amber-500/50'
                }`}
              >
                {rec.decision.replace(/_/g, ' ')}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-[11px] text-slate-300 bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/80">
              <div>
                <span className="text-slate-500">Baseline: </span>
                {rec.baselineConfig} ({rec.baselineMetric}: {rec.baselineValue})
              </div>
              <div>
                <span className="text-slate-500">Tested: </span>
                {rec.testedConfig} ({rec.testedMetric}: {rec.testedValue})
              </div>
              <div>
                <span className="text-slate-500">Impact Delta: </span>
                <span className={rec.deltaPercent > 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                  {rec.deltaPercent > 0 ? `+${rec.deltaPercent}%` : `${rec.deltaPercent}%`}
                </span>
              </div>
            </div>

            <p className="text-xs text-slate-300 font-sans italic border-l-2 border-cyan-500/60 pl-3 py-0.5">
              "{rec.caption}"
            </p>
          </div>
        );
      })}
    </div>
  );
};
