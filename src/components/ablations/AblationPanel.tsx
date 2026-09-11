import React from 'react';
import { AblationComparisonChart } from './AblationComparisonChart';
import { AblationCaption } from './AblationCaption';
import { Flame, ShieldCheck } from 'lucide-react';

export const AblationPanel: React.FC = () => {
  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-y-auto bg-[#020712]">
      {/* Title & Integrity Guarantee */}
      <div className="glass-panel p-4 rounded-xl border border-cyan-500/30 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono uppercase bg-rose-950/80 text-rose-300 border border-rose-500/40 px-2 py-0.5 rounded flex items-center gap-1">
              <Flame className="w-3.5 h-3.5 text-rose-400" />
              WHAT WE TRIED AND KILLED
            </span>
            <span className="text-xs font-mono text-cyan-300">
              Honest Ablation & Transparency Audit (PRD §3 Item 5)
            </span>
          </div>
          <h2 className="text-xl font-heading font-extrabold text-white mt-1">
            Proven Negative Results & Scientific Ablations
          </h2>
          <p className="text-xs text-slate-400 mt-0.5 font-sans max-w-3xl">
            AquaSense directly displays every architecture, filter, and scoring technique that failed under empirical testing. Rather than hiding negative results or claiming unproven capabilities, every decision is substantiated with live, regenerable metrics.
          </p>
        </div>

        <div className="bg-slate-900/90 border border-slate-700 p-3 rounded-lg text-xs font-mono text-slate-300">
          <div className="font-bold text-emerald-400 flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4" />
            ZERO HARDCODED BENCHMARKS
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            Re-run cold: <code className="text-cyan-300">make verify</code>
          </div>
        </div>
      </div>

      {/* Recharts Bar Chart */}
      <AblationComparisonChart />

      {/* Decision Captions per Row */}
      <AblationCaption />
    </div>
  );
};
