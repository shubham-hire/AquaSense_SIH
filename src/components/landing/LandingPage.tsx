import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useSurveyStore } from '../../store/useSurveyStore';
import { SurveyUploadCard } from './SurveyUploadCard';
import { Radar, Compass, ShieldCheck, Waves, ArrowRight, Layers, Target, CheckCircle2 } from 'lucide-react';

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const { surveys, setActiveSurveyId } = useSurveyStore();

  const handleSelectSurvey = (id: string) => {
    setActiveSurveyId(id);
    navigate(`/surveys/${id}/console`);
  };

  return (
    <div className="flex-1 min-h-0 flex flex-col p-6 gap-6 overflow-y-auto bg-[#111A2A]">
      {/* Hero Header */}
      <div className="page-title-sticky flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-mono uppercase bg-cyan-950 text-cyan-300 border border-cyan-500/40 px-2 py-0.5 rounded">
              SIH 2026 Problem Statement 26057
            </span>
            <span className="text-xs font-mono text-slate-400">
              MoES / NIOT Deep Ocean Mission (Samudrayaan)
            </span>
          </div>
          <h1 className="text-3xl font-heading font-black text-white tracking-tight">
            AQUA<span className="text-cyan-400">SENSE</span>
          </h1>
          <p className="text-sm text-slate-300 max-w-2xl mt-1 font-sans">
            AI-Powered Automated Underwater Marine Debris & Anomaly Detection System using Side-Scan Sonar Imagery. Scientifically verified false-positive suppression, hard refusal invariants, and real-time geospatial hazard mapping.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => handleSelectSurvey(surveys[0].id)}
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-[#065A82] to-[#1C7293] hover:border-cyan-300 border border-cyan-500/40 text-white font-heading font-bold text-xs shadow-[0_0_15px_rgba(34,211,238,0.2)] flex items-center gap-2 transition-all cursor-pointer"
          >
            <span>ENTER LIVE CONSOLE</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Grid: Upload Card + Active Missions */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left 7 Cols: Upload Ingestion Card */}
        <div className="lg:col-span-7">
          <SurveyUploadCard />
        </div>

        {/* Right 5 Cols: Registered Indian Ocean Sonar Missions */}
        <div className="lg:col-span-5 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h3 className="font-heading font-bold text-sm text-white">
              REGISTERED HYDROGRAPHIC MISSIONS
            </h3>
            <span className="text-xs font-mono text-slate-500">{surveys.length} Loaded</span>
          </div>

          <div className="space-y-3">
            {surveys.map((survey) => (
              <div
                key={survey.id}
                onClick={() => handleSelectSurvey(survey.id)}
                className="glass-panel p-4 rounded-xl border border-slate-800 hover:border-cyan-400/60 hover:bg-slate-900/80 transition-all cursor-pointer group flex flex-col gap-2"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="font-heading font-bold text-sm text-white group-hover:text-cyan-300 transition-colors">
                      {survey.name}
                    </div>
                    <div className="text-[11px] font-mono text-slate-400">
                      {survey.vesselName} | {survey.vehicleType}
                    </div>
                  </div>
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                    survey.status === 'Active'
                      ? 'bg-emerald-950/80 text-emerald-300 border-emerald-500/40'
                      : 'bg-slate-900 text-slate-400 border-slate-700'
                  }`}>
                    {survey.status}
                  </span>
                </div>

                <div className="flex items-center justify-between text-xs font-mono text-slate-400 pt-2 border-t border-slate-800/60">
                  <span>Area: <strong className="text-slate-200">{survey.areaSqKm} km²</strong></span>
                  <span>Swath: <strong className="text-slate-200">{survey.swathWidthMeters}m</strong></span>
                  <span className="text-cyan-300">{survey.summaryMetrics.verifiedCount} Hazards</span>
                </div>
              </div>
            ))}
          </div>

          {/* Quick Pillars */}
          <div className="glass-panel p-3 rounded-xl border border-slate-800 mt-2 space-y-2 text-xs font-mono text-slate-400">
            <div className="text-[11px] font-bold text-slate-300 uppercase">
              ARCHITECTURAL PILLARS (PRD v1.1)
            </div>
            <div className="flex items-center gap-2 text-emerald-300">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>10-Feature Learned Physical Verifier (+30.4% Precision)</span>
            </div>
            <div className="flex items-center gap-2 text-rose-300">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Structural Refusal Invariant (Lat/Lng: null on missing nav)</span>
            </div>
            <div className="flex items-center gap-2 text-cyan-300">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Dual-Mode Bounding Boxes + Polygon Net Masks</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
