import React from 'react';
import { useSurveyStore } from '../../store/useSurveyStore';
import { PriorityBadge } from '../shared/PriorityBadge';
import { RefusalBadge } from '../shared/RefusalBadge';
import { DataQualityBadge } from '../shared/DataQualityBadge';
import { MaskOrBoxOutline } from '../shared/MaskOrBoxOutline';
import { ListFilter, ChevronRight, Eye } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export const DetectionQueue: React.FC = () => {
  const navigate = useNavigate();
  const {
    detections,
    activeSurveyId,
    selectedDetectionId,
    setSelectedDetectionId,
    confidenceThreshold,
    filterClass,
    filterPriority,
    showOnlyRefused,
  } = useSurveyStore();

  const filtered = detections.filter((d) => {
    if (d.surveyId !== activeSurveyId) return false;
    if (d.confidencePercent < confidenceThreshold) return false;
    if (filterClass !== 'ALL' && d.classification !== filterClass) return false;
    if (filterPriority !== 'ALL' && d.threatLevel !== filterPriority) return false;
    if (showOnlyRefused && d.position.kind !== 'unlocated') return false;
    return true;
  });

  return (
    <div className="flex flex-col glass-panel rounded-xl p-3 gap-2 overflow-hidden h-full">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2">
          <ListFilter className="w-4 h-4 text-cyan-400" />
          <h3 className="font-heading font-bold text-sm text-white tracking-wide">
            DETECTION QUEUE
          </h3>
          <span className="text-[10px] font-mono text-cyan-300 bg-cyan-950 border border-cyan-500/40 px-1.5 py-0.5 rounded">
            {filtered.length} ACTIVE
          </span>
        </div>
      </div>

      {/* Scrollable Detection List */}
      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {filtered.map((detection) => {
          const isSelected = selectedDetectionId === detection.id;
          const isUnlocated = detection.position.kind === 'unlocated';

          return (
            <div
              key={detection.id}
              onClick={() => setSelectedDetectionId(detection.id)}
              className={`p-3 rounded-lg border transition-all cursor-pointer ${
                isSelected
                  ? 'bg-cyan-950/40 border-cyan-400/80 shadow-[0_0_15px_rgba(34,211,238,0.2)]'
                  : 'bg-slate-900/60 border-slate-800 hover:border-slate-700 hover:bg-slate-900/90'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <PriorityBadge priority={detection.threatLevel} size="sm" />
                  <span className="font-mono text-xs font-bold text-cyan-300">
                    {detection.confidencePercent}%
                  </span>
                  {!detection.calibrated && (
                    <RefusalBadge type="uncalibrated" size="sm" />
                  )}
                  {detection.experimental && (
                    <RefusalBadge type="experimental" label="SYNTHETIC" size="sm" />
                  )}
                </div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    navigate(`/surveys/${activeSurveyId}/detections/${detection.id}`);
                  }}
                  title="Inspect Provenance & 10-Feature Verifier"
                  className="p-1 rounded text-slate-400 hover:text-cyan-300 hover:bg-slate-800 transition-colors"
                >
                  <Eye className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Title & Geometry Preview */}
              <div className="flex items-center justify-between mt-2">
                <div>
                  <div className="font-heading font-semibold text-xs text-white">
                    {detection.classNameLabel}
                  </div>
                  <div className="text-[11px] font-mono text-slate-400 mt-0.5">
                    {detection.boundingBox.widthM}m × {detection.boundingBox.heightM}m
                    {detection.acousticShadow?.estimatedHeightMeters !== undefined && (
                      <span className="text-cyan-400 ml-2">
                        H: {detection.acousticShadow.estimatedHeightMeters !== null
                          ? `${detection.acousticShadow.estimatedHeightMeters}m`
                          : 'REFUSED'}
                      </span>
                    )}
                  </div>
                </div>

                {/* Mask or Box SVG thumbnail */}
                <div className="w-12 h-10 bg-black/40 border border-slate-800 rounded flex items-center justify-center shrink-0">
                  <MaskOrBoxOutline detection={detection} width={44} height={34} />
                </div>
              </div>

              {/* Status and Refusal Footnote */}
              <div className="mt-2 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] font-mono">
                {detection.position.kind === 'unlocated' ? (
                  <RefusalBadge type="unlocated" label="REFUSED: NO NAV" size="sm" />
                ) : (
                  <span className="text-slate-400">
                    {detection.position.lat.toFixed(4)}°N, {detection.position.lng.toFixed(4)}°E
                  </span>
                )}

                {detection.lowDataQuality && (
                  <DataQualityBadge type="low_data_quality" size="sm" />
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
