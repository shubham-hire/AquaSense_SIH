import React from 'react';
import { SurveyUploadCard } from './SurveyUploadCard';
import { CheckCircle2 } from 'lucide-react';

export const LandingPage: React.FC = () => {
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
      </div>

      {/* Main Grid: Upload Card + Info Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Upload Ingestion Card */}
        <div className="lg:col-span-7">
          <SurveyUploadCard />
        </div>

        {/* Right: System Architecture Info */}
        <div className="lg:col-span-5 flex flex-col gap-3">
          {/* Quick Pillars */}
          <div className="glass-panel p-4 rounded-xl border border-slate-800 space-y-3">
            <div className="text-[12px] font-bold text-slate-200 uppercase tracking-wider">
              SYSTEM CAPABILITIES
            </div>
            <div className="flex items-start gap-2 text-emerald-300">
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              <span className="text-xs font-mono">10-Feature Learned Physical Verifier (+30.4% Precision)</span>
            </div>
            <div className="flex items-start gap-2 text-rose-300">
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              <span className="text-xs font-mono">Structural Refusal Invariant — Lat/Lng: null on missing nav</span>
            </div>
            <div className="flex items-start gap-2 text-cyan-300">
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              <span className="text-xs font-mono">Dual-Mode Bounding Boxes + Polygon Net Masks</span>
            </div>
            <div className="flex items-start gap-2 text-amber-300">
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              <span className="text-xs font-mono">Platt Calibration — calibrated: false propagated everywhere</span>
            </div>
            <div className="flex items-start gap-2 text-violet-300">
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              <span className="text-xs font-mono">Cross-Survey Train/Test Split — no data leakage</span>
            </div>
            <div className="flex items-start gap-2 text-slate-300">
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              <span className="text-xs font-mono">JSON, CSV, GeoJSON, PDF export — full provenance traceability</span>
            </div>
          </div>

          <div className="glass-panel p-4 rounded-xl border border-slate-800 space-y-2">
            <div className="text-[12px] font-bold text-slate-200 uppercase tracking-wider">
              SUPPORTED FILE FORMATS
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
              {[
                { fmt: '.XTF', desc: 'Triton side-scan sonar' },
                { fmt: '.JSF', desc: 'EdgeTech sonar format' },
                { fmt: '.SL2', desc: 'Lowrance sonar log' },
                { fmt: 'GeoTIFF', desc: 'Georeferenced imagery' },
                { fmt: 'PNG / JPG', desc: 'Image upload & detect' },
              ].map(({ fmt, desc }) => (
                <div key={fmt} className="flex flex-col bg-slate-900/60 rounded-lg p-2 border border-slate-800">
                  <span className="text-cyan-300 font-bold">{fmt}</span>
                  <span className="text-slate-400 text-[10px]">{desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
