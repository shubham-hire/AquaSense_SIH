import React from 'react';
import { Detection } from '../../types';
import { ShieldCheck, ShieldAlert, Waves, Compass, Activity } from 'lucide-react';

interface ProvenanceChainProps {
  detection: Detection;
}

export const ProvenanceChain: React.FC<ProvenanceChainProps> = ({ detection }) => {
  return (
    <div className="glass-panel p-4 rounded-xl flex flex-col gap-3 font-mono text-xs">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-cyan-400" />
          <h4 className="font-heading font-bold text-sm text-white">PROVENANCE & ERROR BUDGET</h4>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Left: Metadata & Flags */}
        <div className="space-y-2 bg-slate-900/60 p-3 rounded-lg border border-slate-800">
          <div className="text-[11px] font-bold text-slate-400 border-b border-slate-800 pb-1">
            DETECTION PROVENANCE METRICS
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Detection ID:</span>
            <span className="text-white">{detection.id}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Model Version:</span>
            <span className="text-cyan-300">YOLO26n-seg-v1.0 (NMS-Free)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Platt Calibrated:</span>
            <span className={detection.calibrated ? 'text-emerald-400 font-bold' : 'text-amber-400'}>
              {detection.calibrated ? 'TRUE (Platt Scaled)' : 'FALSE (Raw Logit)'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Raw Detector Logit:</span>
            <span className="text-white">{detection.rawDetectorLogit}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">DSP Filter in Detector:</span>
            <span className="text-emerald-400">DISABLED (Ablation E06 Proven)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Data Quality Flag:</span>
            <span className={detection.lowDataQuality ? 'text-amber-400' : 'text-slate-300'}>
              {detection.lowDataQuality ? 'LOW_DATA_QUALITY (Motion/Heave)' : 'NOMINAL QUALITY'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Position Fix Status:</span>
            <span className={detection.position.kind === 'located' ? 'text-emerald-400' : 'text-rose-400 font-bold'}>
              {detection.position.kind === 'located' ? 'GPS_FIX VALID' : 'REFUSED (NAV DROPOUT)'}
            </span>
          </div>
        </div>

        {/* Right: Quadrature Error Budget Display */}
        <div className="space-y-2 bg-slate-900/60 p-3 rounded-lg border border-slate-800">
          <div className="text-[11px] font-bold text-cyan-300 border-b border-slate-800 pb-1 flex items-center justify-between">
            <span>QUADRATURE ERROR BUDGET</span>
            <Compass className="w-3.5 h-3.5" />
          </div>

          {detection.errorBudget ? (
            <div className="space-y-1.5 pt-1">
              <div className="flex justify-between text-slate-300">
                <span>σ_GPS (DGPS uncertainty):</span>
                <span className="text-white font-semibold">±{detection.errorBudget.sigmaGps} m</span>
              </div>
              <div className="flex justify-between text-slate-300">
                <span>σ_cross-track (R_ground · sin σ_h):</span>
                <span className="text-white font-semibold">±{detection.errorBudget.sigmaCrossTrack} m</span>
              </div>
              <div className="flex justify-between text-slate-300">
                <span>σ_range (0.03 · R_slant + 0.2):</span>
                <span className="text-white font-semibold">±{detection.errorBudget.sigmaRange} m</span>
              </div>
              <div className="flex justify-between text-slate-300">
                <span>σ_altitude:</span>
                <span className="text-white font-semibold">±{detection.errorBudget.sigmaAltitude} m</span>
              </div>

              <div className="pt-2 border-t border-slate-800 flex justify-between items-center text-sm font-bold text-cyan-300">
                <span>Total 1-σ Position Budget:</span>
                <span className="text-base text-cyan-200">±{detection.errorBudget.sigmaPosTotal} meters</span>
              </div>

              <div className="text-[10px] text-slate-400 pt-1">
                Formula: σ_pos = √(σ_GPS² + σ_cross² + σ_range² + σ_alt²)
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center p-4 text-center space-y-1 text-rose-300">
              <ShieldAlert className="w-6 h-6 text-rose-400" />
              <span className="font-bold">Error Budget Refused</span>
              <span className="text-[10px] text-slate-400">
                No nav packet was received for Ping #{detection.pingIndex}. The system refuses to fabricate coordinates or error estimates.
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
