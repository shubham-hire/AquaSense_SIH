import React from 'react';
import { useSurveyStore } from '../../store/useSurveyStore';
import { ShieldCheck, Target, Award, ShieldAlert, Sparkles, Navigation } from 'lucide-react';

export const PriorityStatCards: React.FC = () => {
  const { detections, surveys, activeSurveyId } = useSurveyStore();
  const activeSurvey = surveys.find((s) => s.id === activeSurveyId) || surveys[0];
  const surveyDetections = detections.filter((d) => d.surveyId === activeSurveyId);

  const criticalCount = surveyDetections.filter((d) => d.threatLevel === 'CRITICAL').length;
  const highCount = surveyDetections.filter((d) => d.threatLevel === 'HIGH').length;
  const medCount = surveyDetections.filter((d) => d.threatLevel === 'MEDIUM').length;
  const lowCount = surveyDetections.filter((d) => d.threatLevel === 'LOW').length;
  const unlocatedCount = surveyDetections.filter((d) => d.position.kind === 'unlocated').length;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      {/* 1. Verified Anomaly Contacts */}
      <div className="glass-panel p-4 rounded-xl flex items-center justify-between">
        <div>
          <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
            VERIFIED HAZARD TARGETS
          </div>
          <div className="text-2xl font-heading font-extrabold text-white mt-1">
            {surveyDetections.length}
          </div>
          <div className="flex items-center gap-2 mt-2 text-[10px] font-mono">
            <span className="text-[#FF6B6B] font-bold">{criticalCount} Crit</span>
            <span className="text-slate-600">|</span>
            <span className="text-[#FFA94D] font-bold">{highCount} High</span>
            <span className="text-slate-600">|</span>
            <span className="text-[#FFE066] font-bold">{medCount} Med</span>
          </div>
        </div>
        <div className="w-11 h-11 rounded-lg bg-cyan-500/15 border border-cyan-400/30 flex items-center justify-center text-cyan-300">
          <Target className="w-6 h-6" />
        </div>
      </div>

      {/* 2. Verifier Precision Payoff */}
      <div className="glass-panel p-4 rounded-xl flex items-center justify-between">
        <div>
          <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
            10-FEATURE PRECISION GAIN
          </div>
          <div className="text-2xl font-heading font-extrabold text-emerald-400 mt-1">
            +{activeSurvey.summaryMetrics.precisionGainPercent}%
          </div>
          <div className="text-[11px] text-slate-400 mt-2 font-mono">
            {activeSurvey.summaryMetrics.rejectedCount} False Positives Caught
          </div>
        </div>
        <div className="w-11 h-11 rounded-lg bg-emerald-500/15 border border-emerald-400/30 flex items-center justify-center text-emerald-300">
          <Award className="w-6 h-6" />
        </div>
      </div>

      {/* 3. Refusal Discipline Cleanliness */}
      <div className="glass-panel p-4 rounded-xl flex items-center justify-between">
        <div>
          <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
            REFUSAL DISCIPLINE
          </div>
          <div className="text-2xl font-heading font-extrabold text-cyan-300 mt-1">
            100%
          </div>
          <div className="text-[11px] text-rose-300/90 mt-2 font-mono flex items-center gap-1">
            <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
            <span>{unlocatedCount} Missing Nav Safely Refused</span>
          </div>
        </div>
        <div className="w-11 h-11 rounded-lg bg-rose-500/15 border border-rose-400/30 flex items-center justify-center text-rose-300">
          <ShieldCheck className="w-6 h-6" />
        </div>
      </div>

      {/* 4. Survey Coverage Corridor */}
      <div className="glass-panel p-4 rounded-xl flex items-center justify-between">
        <div>
          <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
            HYDROGRAPHIC SWATH
          </div>
          <div className="text-2xl font-heading font-extrabold text-white mt-1">
            {activeSurvey.areaSqKm} km²
          </div>
          <div className="text-[11px] text-slate-400 mt-2 font-mono">
            Swath: {activeSurvey.swathWidthMeters}m | {activeSurvey.summaryMetrics.totalPings} Pings
          </div>
        </div>
        <div className="w-11 h-11 rounded-lg bg-blue-500/15 border border-blue-400/30 flex items-center justify-center text-blue-300">
          <Navigation className="w-6 h-6" />
        </div>
      </div>
    </div>
  );
};
