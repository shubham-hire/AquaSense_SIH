import React from 'react';
import { useSurveyStore } from '../../store/useSurveyStore';
import { Sliders, Filter, ShieldAlert } from 'lucide-react';
import { PriorityLevel } from '../../types';

export const ThresholdControls: React.FC = () => {
  const {
    confidenceThreshold,
    setConfidenceThreshold,
    filterClass,
    setFilterClass,
    filterPriority,
    setFilterPriority,
    showOnlyRefused,
    setShowOnlyRefused,
  } = useSurveyStore();

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-slate-950/80 border border-slate-800 rounded-xl text-xs font-mono">
      {/* Confidence Threshold Slider */}
      <div className="flex items-center gap-2 min-w-[220px]">
        <Sliders className="w-3.5 h-3.5 text-cyan-400" />
        <span className="text-slate-400">CONFIDENCE:</span>
        <input
          type="range"
          min="10"
          max="95"
          value={confidenceThreshold}
          onChange={(e) => setConfidenceThreshold(Number(e.target.value))}
          className="w-28 accent-cyan-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
        />
        <span className="text-cyan-300 font-bold min-w-[32px]">{confidenceThreshold}%</span>
      </div>

      {/* Class Filter Dropdown */}
      <div className="flex items-center gap-2">
        <Filter className="w-3.5 h-3.5 text-slate-400" />
        <span className="text-slate-400">CLASS:</span>
        <select
          value={filterClass}
          onChange={(e) => setFilterClass(e.target.value)}
          className="bg-slate-900 border border-slate-700 text-slate-200 rounded px-2 py-1 text-xs focus:outline-none focus:border-cyan-400"
        >
          <option value="ALL">All Hazard Classes (8)</option>
          <option value="entangled_net">Entangled Net (Ghost Gear)</option>
          <option value="shipwreck">Shipwreck / Hull</option>
          <option value="cylinder_drum">Chemical Cylinder / Drum</option>
          <option value="pipeline_anomaly">Pipeline Anomaly</option>
          <option value="unexploded_ordnance">Unexploded Ordnance (UXO)</option>
          <option value="marine_debris">Marine Debris</option>
          <option value="subsea_cable">Subsea Cable</option>
        </select>
      </div>

      {/* Priority Filter */}
      <div className="flex items-center gap-2">
        <span className="text-slate-400">PRIORITY:</span>
        <select
          value={filterPriority}
          onChange={(e) => setFilterPriority(e.target.value as PriorityLevel | 'ALL')}
          className="bg-slate-900 border border-slate-700 text-slate-200 rounded px-2 py-1 text-xs focus:outline-none focus:border-cyan-400"
        >
          <option value="ALL">All Priorities</option>
          <option value="CRITICAL">Critical</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
        </select>
      </div>

      {/* Show Only Refused Toggle */}
      <button
        onClick={() => setShowOnlyRefused(!showOnlyRefused)}
        className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs transition-all border ${
          showOnlyRefused
            ? 'bg-rose-950/60 text-rose-300 border-rose-500/60 font-semibold shadow-[0_0_8px_rgba(244,63,94,0.25)]'
            : 'bg-slate-900/60 text-slate-400 border-slate-700 hover:text-slate-200'
        }`}
      >
        <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
        <span>REFUSED ONLY</span>
      </button>
    </div>
  );
};
