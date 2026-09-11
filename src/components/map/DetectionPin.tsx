import React from 'react';
import { Detection } from '../../types';
import { ShieldAlert, Sparkles, AlertCircle } from 'lucide-react';

interface DetectionPinProps {
  detection: Detection;
  isSelected?: boolean;
  onClick?: () => void;
}

export const DetectionPin: React.FC<DetectionPinProps> = ({
  detection,
  isSelected = false,
  onClick,
}) => {
  const isUnlocated = detection.position.kind === 'unlocated';

  const getMarkerColor = () => {
    if (isUnlocated) return '#64748B'; // Gray for refused
    switch (detection.threatLevel) {
      case 'CRITICAL':
        return '#B23A2E';
      case 'HIGH':
        return '#C97A1E';
      case 'MEDIUM':
        return '#C9A227';
      case 'LOW':
      default:
        return '#4C8C5B';
    }
  };

  const color = getMarkerColor();

  return (
    <div
      onClick={onClick}
      className={`relative cursor-pointer transition-transform duration-200 hover:scale-125 flex flex-col items-center ${
        isSelected ? 'scale-125 z-50' : 'z-20'
      }`}
    >
      {/* Sonar Ping Ring */}
      <div
        className="absolute -inset-2 rounded-full opacity-75 sonar-ping pointer-events-none"
        style={{ backgroundColor: color }}
      />

      {/* Center Marker Pin */}
      <div
        className={`w-6 h-6 rounded-full flex items-center justify-center border-2 shadow-lg transition-all ${
          isSelected ? 'border-white ring-4 ring-cyan-400/40' : 'border-slate-900'
        }`}
        style={{ backgroundColor: color }}
      >
        {isUnlocated ? (
          <ShieldAlert className="w-3.5 h-3.5 text-white" />
        ) : detection.classification === 'entangled_net' ? (
          <Sparkles className="w-3 h-3 text-white" />
        ) : (
          <span className="text-[9px] font-mono font-bold text-white">
            {detection.confidencePercent}%
          </span>
        )}
      </div>

      {/* Mini Label */}
      <div className="mt-1 px-1.5 py-0.5 rounded bg-slate-950/90 border border-slate-700/80 text-[10px] font-mono font-medium text-slate-200 whitespace-nowrap shadow-md">
        {detection.classification.replace('_', ' ')}
      </div>
    </div>
  );
};
