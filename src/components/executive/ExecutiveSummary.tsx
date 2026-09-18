import React from 'react';
import { useNavigate } from 'react-router-dom';
import { PriorityStatCards } from './PriorityStatCards';
import { LiveMapPanel } from '../map/LiveMapPanel';
import { ExportBar } from './ExportBar';
import { useSurveyStore } from '../../store/useSurveyStore';
import { Anchor, CheckCircle2, FileBarChart2, UploadCloud } from 'lucide-react';
import { PriorityBadge } from '../shared/PriorityBadge';
import { RefusalBadge } from '../shared/RefusalBadge';

export const ExecutiveSummary: React.FC = () => {
  const navigate = useNavigate();
  const { surveys, activeSurveyId, detections } = useSurveyStore();
  const activeSurvey = surveys.find((s) => s.id === activeSurveyId) || surveys[0];
  const surveyDetections = detections.filter((d) => d.surveyId === activeSurveyId);

  // A fresh session has no mission until the operator uploads a file.  The
  // summary must remain navigable in that state instead of dereferencing an
  // absent survey and crashing the route.
  if (!activeSurvey) {
    return (
      <section className="flex-1 min-h-0 overflow-y-auto bg-[#111A2A] p-4" aria-labelledby="executive-summary-title">
        <div className="glass-panel mx-auto flex min-h-[420px] max-w-3xl flex-col items-center justify-center rounded-xl border border-cyan-500/30 p-8 text-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl border border-cyan-400/30 bg-cyan-500/10">
            <FileBarChart2 className="h-7 w-7 text-cyan-300" aria-hidden="true" />
          </div>
          <p className="mb-2 text-xs font-mono uppercase tracking-widest text-cyan-300">Executive Summary</p>
          <h1 id="executive-summary-title" className="text-xl font-heading font-extrabold text-white">
            No mission is ready for briefing
          </h1>
          <p className="mt-2 max-w-md text-sm leading-6 text-slate-400">
            Upload and process a survey image or sonar file to populate verified hazards, map coverage, and exportable mission metrics.
          </p>
          <button
            type="button"
            onClick={() => navigate('/ingest')}
            className="mt-6 inline-flex min-h-11 items-center gap-2 rounded-lg border border-cyan-400/50 bg-cyan-500/15 px-4 py-2 text-sm font-semibold text-cyan-100 transition-colors hover:bg-cyan-500/25 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-300"
          >
            <UploadCloud className="h-4 w-4" aria-hidden="true" />
            Upload a mission
          </button>
        </div>
      </section>
    );
  }

  return (
    <div className="flex-1 min-h-0 flex flex-col p-4 gap-4 overflow-y-auto bg-[#111A2A]">
      {/* Executive Briefing Banner */}
      <div className="page-title-sticky glass-panel p-4 rounded-xl border border-cyan-500/30 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono uppercase bg-cyan-950 text-cyan-300 border border-cyan-500/40 px-2 py-0.5 rounded">
              EXECUTIVE AUDIT BRIEF
            </span>
            <span className="text-xs font-mono text-emerald-400 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              100% Script-Regenerable Metrics
            </span>
          </div>
          <h2 className="text-xl font-heading font-extrabold text-white mt-1">
            {activeSurvey.name}
          </h2>
          <p className="text-xs text-slate-400 mt-0.5 font-sans">
            Vessel: {activeSurvey.vesselName} | Vehicle: {activeSurvey.vehicleType} | Swath: {activeSurvey.swathWidthMeters}m
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono bg-slate-900/90 border border-slate-700 px-3 py-2 rounded-lg">
          <Anchor className="w-4 h-4 text-cyan-400" />
          <span className="text-slate-300">{activeSurvey.locationName}</span>
        </div>
      </div>

      {/* KPI Cards */}
      <PriorityStatCards />

      {/* Map and Breakdown Split */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-[420px]">
        {/* Left 2 Cols: 2D Geospatial Map */}
        <div className="lg:col-span-2 min-h-[400px]">
          <LiveMapPanel isReadOnly={true} className="h-full" />
        </div>

        {/* Right Col: Verified Hazard Registry */}
        <div className="glass-panel rounded-xl p-3 flex flex-col overflow-hidden min-h-[400px]">
          <h4 className="font-heading font-bold text-sm text-white border-b border-slate-800 pb-2 flex items-center justify-between">
            <span>HAZARD LOG REGISTRY</span>
            <span className="text-xs font-mono text-slate-400">{surveyDetections.length} Contacts</span>
          </h4>

          <div className="flex-1 overflow-y-auto space-y-2 mt-2 pr-1">
            {surveyDetections.map((d) => (
              <div
                key={d.id}
                className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 text-xs font-sans space-y-1"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-white">{d.classNameLabel}</span>
                  <PriorityBadge priority={d.threatLevel} size="sm" />
                </div>
                <div className="text-[11px] font-mono text-slate-400 flex items-center justify-between">
                  <span>Confidence: <strong className="text-cyan-300">{d.confidencePercent}%</strong></span>
                  <span>Dim: {d.boundingBox.widthM}m × {d.boundingBox.heightM}m</span>
                </div>
                <div className="pt-1 flex items-center justify-between text-[10px] font-mono">
                  {d.position.kind === 'located' ? (
                    <span className="text-slate-400">
                      {d.position.lat.toFixed(4)}°N, {d.position.lng.toFixed(4)}°E
                    </span>
                  ) : (
                    <RefusalBadge type="unlocated" label="REFUSED" size="sm" />
                  )}
                  {d.segmentationMask && (
                    <span className="text-emerald-400 font-mono">MASK GENERATED</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Export Bar */}
      <ExportBar />
    </div>
  );
};
