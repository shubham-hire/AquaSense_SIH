import React, { useState, useRef } from 'react';
import { Ruler, Crosshair, X } from 'lucide-react';
import { invertShadowHeight } from '../../utils/sonarMath';

interface CaliperMeasurement {
  startX: number;
  startY: number;
  endX: number;
  endY: number;
  lengthPx: number;
  shadowLengthM: number;
  slantRangeM: number;
  estimatedHeightM: number | null;
}

interface MeasurementCalipersProps {
  altitudeM?: number;
  swathRangeM?: number;
}

export const MeasurementCalipers: React.FC<MeasurementCalipersProps> = ({
  altitudeM = 8.4,
  swathRangeM = 50.0,
}) => {
  const [isActive, setIsActive] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [measurement, setMeasurement] = useState<CaliperMeasurement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isActive) return;
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;

    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    setDragStart({ x, y });
    setIsDragging(true);
    setMeasurement(null);
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDragging || !dragStart) return;
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;

    const currentX = e.clientX - rect.left;
    const currentY = e.clientY - rect.top;

    const dx = currentX - dragStart.x;
    const dy = currentY - dragStart.y;
    const lengthPx = Math.sqrt(dx * dx + dy * dy);

    // Scaling: assume width spans 2 * swathRangeM
    const pxPerMeter = rect.width / (2 * swathRangeM);
    const shadowLengthM = lengthPx / Math.max(1, pxPerMeter);
    const slantRangeM = Math.abs(currentX - rect.width / 2) / Math.max(1, pxPerMeter);

    const estimatedHeightM = invertShadowHeight(altitudeM, slantRangeM, shadowLengthM);

    setMeasurement({
      startX: dragStart.x,
      startY: dragStart.y,
      endX: currentX,
      endY: currentY,
      lengthPx: Math.round(lengthPx),
      shadowLengthM: Number(shadowLengthM.toFixed(2)),
      slantRangeM: Number(slantRangeM.toFixed(2)),
      estimatedHeightM,
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  return (
    <>
      {/* Top Toggle Bar */}
      <div className="absolute top-2 right-2 z-20 flex items-center gap-2">
        <button
          onClick={() => {
            setIsActive(!isActive);
            if (isActive) setMeasurement(null);
          }}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono font-medium shadow-md transition-all ${
            isActive
              ? 'bg-amber-500 text-slate-950 font-bold border border-amber-300'
              : 'bg-slate-900/80 text-slate-300 hover:text-white border border-slate-700'
          }`}
        >
          <Ruler className="w-3.5 h-3.5" />
          <span>{isActive ? 'CALIPERS ACTIVE' : 'CALIPERS'}</span>
        </button>

        {measurement && (
          <button
            onClick={() => setMeasurement(null)}
            className="p-1 bg-slate-900/80 text-slate-400 hover:text-white rounded border border-slate-700"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Measurement Caliper Canvas Overlay */}
      {isActive && (
        <div
          ref={containerRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          className="absolute inset-0 z-10 cursor-crosshair select-none"
        >
          {measurement && (
            <svg className="w-full h-full pointer-events-none">
              <line
                x1={measurement.startX}
                y1={measurement.startY}
                x2={measurement.endX}
                y2={measurement.endY}
                stroke="#F59E0B"
                strokeWidth={2}
                strokeDasharray="4 2"
              />
              <circle cx={measurement.startX} cy={measurement.startY} r={4} fill="#F59E0B" />
              <circle cx={measurement.endX} cy={measurement.endY} r={4} fill="#F59E0B" />
            </svg>
          )}
        </div>
      )}

      {/* Floating Measurement HUD */}
      {measurement && (
        <div className="absolute bottom-3 left-3 z-20 bg-slate-950/95 border border-amber-500/40 rounded-lg p-3 text-xs font-mono shadow-2xl backdrop-blur-md space-y-1">
          <div className="flex items-center gap-2 text-amber-400 font-bold border-b border-slate-800 pb-1">
            <Crosshair className="w-3.5 h-3.5" />
            <span>CALIPER ACOUSTIC TRIGONOMETRY</span>
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 pt-1 text-slate-300">
            <div>Shadow Length (L_shadow):</div>
            <div className="text-white font-semibold">{measurement.shadowLengthM} m</div>
            <div>Slant Range (R_slant):</div>
            <div className="text-white font-semibold">{measurement.slantRangeM} m</div>
            <div>Towfish Altitude (H_alt):</div>
            <div className="text-white font-semibold">{altitudeM} m</div>
            <div className="text-cyan-300 font-bold">Estimated Height (H_target):</div>
            <div className="text-cyan-300 font-bold text-sm">
              {measurement.estimatedHeightM !== null ? `${measurement.estimatedHeightM} m` : 'REFUSED (NULL)'}
            </div>
          </div>
          <div className="text-[10px] text-slate-400 pt-1 border-t border-slate-800/80">
            Formula: H = (H_alt × L_shad) / (R_slant + L_shad)
          </div>
        </div>
      )}
    </>
  );
};
