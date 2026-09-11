import React from 'react';
import { useSurveyStore } from '../../store/useSurveyStore';
import { ShieldAlert, AlertCircle, Waves, CheckCircle2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export const RefusalStrip: React.FC = () => {
  const navigate = useNavigate();
  const { detections, activeSurveyId } = useSurveyStore();

  const surveyDetections = detections.filter((d) => d.surveyId === activeSurveyId);

  // Three independent honesty axes (not merged!)
  const unlocatedCount = surveyDetections.filter((d) => d.position.kind === 'unlocated').length;
  const uncalibratedCount = surveyDetections.filter((d) => !d.calibrated).length;
  const lowQualityCount = surveyDetections.filter((d) => d.lowDataQuality).length;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs font-mono">
      {/* Left: Scientific Honesty Guarantee */}
      <div className="flex items-center gap-2 text-slate-400">
        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
        <span className="font-bold text-slate-200">SCIENTIFIC INTEGRITY INVARIANT:</span>
        <span className="hidden md:inline text-slate-500">
          Refuse rather than fabricate | No output without provenance
        </span>
      </div>

      {/* Right: Three Distinct Metric Counters */}
      <div className="flex items-center gap-4">
        {/* 1. Unlocated / Geolocation Refused */}
        <div
          title="Position Refusal Invariant (§10): Missing navigation metadata produces null coordinates, enforced by failing unit tests."
          className={`flex items-center gap-1.5 px-2 py-1 rounded border ${
            unlocatedCount > 0
              ? 'bg-rose-950/40 border-rose-500/40 text-rose-300'
              : 'bg-slate-900 border-slate-800 text-slate-400'
          }`}
        >
          <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
          <span>{unlocatedCount} UNLOCATED (REFUSED)</span>
        </div>

        {/* 2. Uncalibrated Logits */}
        <div
          onClick={() => navigate('/settings/calibration')}
          title="Calibration Discipline (§8.3): Checkpoints that haven't fit Platt scaling report calibrated:false unconditionally."
          className={`flex items-center gap-1.5 px-2 py-1 rounded border cursor-pointer hover:border-amber-400 transition-colors ${
            uncalibratedCount > 0
              ? 'bg-amber-950/40 border-amber-500/40 text-amber-300'
              : 'bg-slate-900 border-slate-800 text-slate-400'
          }`}
        >
          <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
          <span>{uncalibratedCount} UNCALIBRATED</span>
        </div>

        {/* 3. Sensor / Motion Data Quality Flag */}
        <div
          title="Motion Artifact / Dropout Handling (§9.2): Flags pings affected by severe vessel heave or acoustic dropouts."
          className={`flex items-center gap-1.5 px-2 py-1 rounded border ${
            lowQualityCount > 0
              ? 'bg-[#8A7B5C]/20 border-[#8A7B5C]/60 text-[#E6DCB8]'
              : 'bg-slate-900 border-slate-800 text-slate-400'
          }`}
        >
          <Waves className="w-3.5 h-3.5 text-[#E6DCB8]" />
          <span>{lowQualityCount} LOW DATA QUALITY</span>
        </div>
      </div>
    </div>
  );
};
