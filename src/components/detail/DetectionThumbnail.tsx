import React, { useState } from 'react';
import { Detection } from '../../types';
import { MaskOrBoxOutline } from '../shared/MaskOrBoxOutline';
import { Eye, Layers, ShieldCheck } from 'lucide-react';

interface DetectionThumbnailProps {
  detection: Detection;
}

export const DetectionThumbnail: React.FC<DetectionThumbnailProps> = ({ detection }) => {
  const [showMask, setShowMask] = useState(true);
  const [showBox, setShowBox] = useState(true);

  return (
    <div className="glass-panel p-4 rounded-xl flex flex-col gap-3">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2">
          <Eye className="w-4 h-4 text-cyan-400" />
          <h4 className="font-heading font-bold text-sm text-white">ACOUSTIC IMAGE INSPECTOR</h4>
        </div>

        {/* Mask vs Box Layer Toggles */}
        <div className="flex items-center gap-2 text-xs font-mono">
          <button
            onClick={() => setShowMask(!showMask)}
            className={`px-2 py-1 rounded border text-[11px] transition-all ${
              showMask ? 'bg-cyan-950 text-cyan-300 border-cyan-500/50' : 'bg-slate-900 text-slate-500 border-slate-800'
            }`}
          >
            MASK LAYER: {showMask ? 'ON' : 'OFF'}
          </button>
          <button
            onClick={() => setShowBox(!showBox)}
            className={`px-2 py-1 rounded border text-[11px] transition-all ${
              showBox ? 'bg-amber-950 text-amber-300 border-amber-500/50' : 'bg-slate-900 text-slate-500 border-slate-800'
            }`}
          >
            BBOX LAYER: {showBox ? 'ON' : 'OFF'}
          </button>
        </div>
      </div>

      {/* Simulated Sonar Crop Display with SVG Overlays */}
      <div className="relative w-full h-64 rounded-lg overflow-hidden border border-slate-800 bg-slate-950 flex items-center justify-center">
        {/* Synthetic Acoustic Background Texture */}
        <div className="absolute inset-0 bg-gradient-to-r from-amber-950/30 via-slate-900 to-amber-950/20" />

        {/* Specular Highlight Representation */}
        <div className="absolute w-32 h-16 bg-amber-400/20 rounded-full blur-sm border border-amber-400/40" />

        {/* Acoustic Shadow Representation */}
        <div className="absolute w-40 h-20 bg-black/80 -right-8 rounded-lg blur-[1px] border border-slate-800/40" />

        {/* Dual Mode Overlay: Polygon Mask or Bounding Box */}
        {showMask && (
          <div className="absolute inset-0 flex items-center justify-center">
            <MaskOrBoxOutline detection={detection} width={280} height={180} strokeWidth={2.5} />
          </div>
        )}

        {/* Telemetry Stamp */}
        <div className="absolute bottom-2 left-2 z-10 bg-slate-950/90 border border-slate-800 rounded px-2 py-1 text-[10px] font-mono text-slate-400 space-y-0.5">
          <div>Pixel Coordinates: [{detection.boundingBox.x}, {detection.boundingBox.y}]</div>
          <div>Swath Resolution: 0.05m / px (Normalized)</div>
          {detection.segmentationMask && (
            <div className="text-emerald-400">Polygon Contour: {detection.segmentationMask.data.length} Vertices</div>
          )}
        </div>
      </div>
    </div>
  );
};
