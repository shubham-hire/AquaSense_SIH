import React from 'react';
import { MODEL_CHECKPOINTS } from '../../data/ablationRecords';
import { ShieldAlert } from 'lucide-react';

export const CalibrationStatusPage: React.FC = () => {
  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-y-auto bg-[#111A2A]">
      {/* Header */}
      <div className="glass-panel p-4 rounded-xl border border-cyan-500/30 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono uppercase bg-amber-950/80 text-amber-300 border border-amber-500/40 px-2 py-0.5 rounded flex items-center gap-1">
              <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
              CALIBRATION DISCLOSURE
            </span>
            <span className="text-xs font-mono text-cyan-300">
              Confidence Calibration Discipline (PRD §8.3)
            </span>
          </div>
          <h2 className="text-xl font-heading font-extrabold text-white mt-1">
            Model Checkpoints & Calibration Verification
          </h2>
          <p className="text-xs text-slate-400 mt-0.5 font-sans max-w-2xl">
            The current production runtime does not apply a fitted Platt scaling curve. Its detections report <code className="text-amber-400 font-mono">calibrated: false</code>, and displayed confidence values must not be interpreted as calibrated probabilities. A checkpoint is marked calibrated only when a held-out calibration fit is actually available.
          </p>
        </div>

        <div className="bg-slate-900/90 border border-slate-700 p-3 rounded-lg text-xs font-mono text-slate-300">
          <div className="font-bold text-amber-300">CURRENT RUNTIME OUTPUT</div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            Uncalibrated score, displayed on a 0–100 scale
          </div>
        </div>
      </div>

      {/* Model Checkpoints Table */}
      <div className="glass-panel p-4 rounded-xl border border-slate-800">
        <h4 className="font-heading font-bold text-sm text-white mb-3">
          REGISTERED MODEL CHECKPOINTS & VERIFICATION STATUS
        </h4>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400">
                <th className="py-2 pr-4">CHECKPOINT ID</th>
                <th className="py-2 pr-4">ARCHITECTURE</th>
                <th className="py-2 pr-4">CALIBRATED?</th>
                <th className="py-2 pr-4">CALIBRATION EVIDENCE</th>
                <th className="py-2 pr-4">SPLIT PROTOCOL</th>
                <th className="py-2 pr-4">CROSS-SURVEY mAP50</th>
                <th className="py-2">STATUS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {MODEL_CHECKPOINTS.map((chk) => (
                <tr key={chk.id} className="hover:bg-slate-900/40 transition-colors">
                  <td className="py-3 pr-4 font-bold text-white">{chk.name}</td>
                  <td className="py-3 pr-4 text-slate-300">{chk.architecture}</td>
                  <td className="py-3 pr-4">
                    {chk.calibrated ? (
                      <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-500/40 text-[10px] font-bold">
                        CALIBRATED: TRUE
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-500/40 text-[10px] font-bold">
                        CALIBRATED: FALSE
                      </span>
                    )}
                  </td>
                  <td className="py-3 pr-4 text-slate-400 text-[11px]">{chk.plattScalingSplit}</td>
                  <td className="py-3 pr-4 text-cyan-300">{chk.splitProtocol}</td>
                  <td className="py-3 pr-4 font-bold text-white">{(chk.mAP50 * 100).toFixed(1)}%</td>
                  <td className="py-3">
                    <span className="text-[10px] bg-slate-900 px-2 py-1 rounded text-slate-300 border border-slate-700">
                      {chk.verifiedStatus}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
