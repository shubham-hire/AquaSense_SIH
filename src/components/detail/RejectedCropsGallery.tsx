import React from 'react';
import { XCircle, CheckCircle2, AlertOctagon } from 'lucide-react';

interface RejectedCrop {
  id: string;
  detectorConfidence: number;
  verifierStatus: 'REJECTED';
  rejectionReason: string;
  failingFeature: string;
  failingValue: string;
  expectedThreshold: string;
}

const MOCK_REJECTED_CROPS: RejectedCrop[] = [
  {
    id: 'REJ-FP-081',
    detectorConfidence: 68,
    verifierStatus: 'REJECTED',
    rejectionReason: 'Acoustic Shadow Side Inconsistent',
    failingFeature: 'shadow_side_consistent',
    failingValue: 'FALSE (Falls up-range of nadir)',
    expectedThreshold: 'Must fall down-range',
  },
  {
    id: 'REJ-FP-082',
    detectorConfidence: 54,
    verifierStatus: 'REJECTED',
    rejectionReason: 'Target Contrast Insufficient',
    failingFeature: 'target_contrast',
    failingValue: '1.24',
    expectedThreshold: '> 2.0 above reverberation',
  },
  {
    id: 'REJ-FP-083',
    detectorConfidence: 71,
    verifierStatus: 'REJECTED',
    rejectionReason: 'Natural Sand Ripple Formation',
    failingFeature: 'texture_homogeneity',
    failingValue: '0.18',
    expectedThreshold: '> 0.35 for solid structure',
  },
];

export const RejectedCropsGallery: React.FC = () => {
  return (
    <div className="glass-panel p-4 rounded-xl flex flex-col gap-3">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2">
          <AlertOctagon className="w-4 h-4 text-rose-400" />
          <h4 className="font-heading font-bold text-sm text-white">
            REJECTED FALSE-POSITIVE AUDIT GALLERY
          </h4>
        </div>
        <span className="text-xs font-mono text-slate-400">
          Showing 3 of 28 Filtered Candidates (+30.4% Precision Payoff)
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {MOCK_REJECTED_CROPS.map((crop) => (
          <div
            key={crop.id}
            className="bg-slate-900/80 border border-slate-800 rounded-lg p-3 flex flex-col justify-between text-xs font-mono space-y-2"
          >
            <div className="flex items-center justify-between">
              <span className="text-slate-400">{crop.id}</span>
              <span className="px-1.5 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-500/40 text-[10px]">
                REJECTED
              </span>
            </div>

            {/* Simulated False Alarm Crop Display */}
            <div className="w-full h-24 rounded bg-black/60 border border-slate-800 relative overflow-hidden flex items-center justify-center">
              <div className="text-slate-600 text-[10px]">ACOUSTIC RIPPLE CROP</div>
              <div className="absolute top-1 right-1 bg-slate-950/80 px-1 text-[9px] text-amber-300">
                Raw Conf: {crop.detectorConfidence}%
              </div>
            </div>

            <div className="space-y-1 text-[11px] pt-1 border-t border-slate-800/80">
              <div className="text-rose-300 font-semibold">{crop.rejectionReason}</div>
              <div className="text-slate-400 text-[10px]">
                Failing Metric: <span className="text-slate-200">{crop.failingFeature}</span>
              </div>
              <div className="text-slate-400 text-[10px]">
                Measured: <span className="text-rose-400 font-bold">{crop.failingValue}</span> (Threshold: {crop.expectedThreshold})
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
