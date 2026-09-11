import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useSurveyStore } from '../../store/useSurveyStore';
import { DetectionThumbnail } from './DetectionThumbnail';
import { ExplainabilityFeatureTable } from './ExplainabilityFeatureTable';
import { ProvenanceChain } from './ProvenanceChain';
import { RejectedCropsGallery } from './RejectedCropsGallery';
import { PriorityBadge } from '../shared/PriorityBadge';
import { RefusalBadge } from '../shared/RefusalBadge';
import { ArrowLeft, Compass, ShieldCheck } from 'lucide-react';

export const DetectionDetailPage: React.FC = () => {
  const { id, d } = useParams<{ id: string; d: string }>();
  const navigate = useNavigate();
  const { detections, activeSurveyId } = useSurveyStore();

  const detection = detections.find((item) => item.id === d) || detections[0];

  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-y-auto bg-[#020712]">
      {/* Top Breadcrumb & Actions Bar */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(`/surveys/${activeSurveyId}/console`)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs font-mono text-slate-300 hover:text-white hover:border-slate-500 transition-all"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>BACK TO CONSOLE</span>
          </button>

          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-heading font-extrabold text-white">
                {detection.classNameLabel}
              </h2>
              <PriorityBadge priority={detection.threatLevel} />
              <span className="font-mono text-xs font-bold text-cyan-400">
                {detection.confidencePercent}% Platt Calibrated
              </span>
            </div>
            <div className="text-xs font-mono text-slate-400 mt-0.5">
              Contact ID: {detection.id} | Ping Index: #{detection.pingIndex} | Timestamp: {detection.pingTimestamp}
            </div>
          </div>
        </div>

        {/* Refusal / Status Tags */}
        <div className="flex items-center gap-2">
          {detection.position.kind === 'unlocated' ? (
            <RefusalBadge type="unlocated" label="GEOLOCATION REFUSED" />
          ) : (
            <div className="flex items-center gap-1.5 bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 px-2.5 py-1 rounded text-xs font-mono">
              <Compass className="w-3.5 h-3.5 text-emerald-400" />
              <span>{detection.position.lat.toFixed(5)}°N, {detection.position.lng.toFixed(5)}°E</span>
            </div>
          )}
          {!detection.calibrated && <RefusalBadge type="uncalibrated" />}
        </div>
      </div>

      {/* Main Grid: Image Crop + 10-Feature Verifier */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <DetectionThumbnail detection={detection} />
        <ProvenanceChain detection={detection} />
      </div>

      {/* Full 10-Feature Verifier Table */}
      <ExplainabilityFeatureTable detection={detection} />

      {/* Rejected Crops Audit Gallery */}
      <RejectedCropsGallery />
    </div>
  );
};
