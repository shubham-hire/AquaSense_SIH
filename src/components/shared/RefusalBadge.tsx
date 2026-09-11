import React from 'react';
import { ShieldAlert, AlertCircle, Sparkles } from 'lucide-react';

interface RefusalBadgeProps {
  type: 'unlocated' | 'uncalibrated' | 'experimental';
  label?: string;
  size?: 'sm' | 'md';
}

export const RefusalBadge: React.FC<RefusalBadgeProps> = ({
  type,
  label,
  size = 'md',
}) => {
  const sizeClasses = size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-1 text-xs';

  if (type === 'unlocated') {
    return (
      <span
        title="Refusal Invariant Enforced: Coordinates null due to missing navigation metadata"
        className={`inline-flex items-center gap-1 font-mono font-medium rounded-md border border-rose-500/50 bg-rose-950/40 text-rose-300 shadow-[0_0_8px_rgba(244,63,94,0.25)] ${sizeClasses}`}
      >
        <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
        {label || 'REFUSED: UNLOCATED'}
      </span>
    );
  }

  if (type === 'uncalibrated') {
    return (
      <span
        title="Uncalibrated: Checkpoint has not been through Platt scaling fit"
        className={`inline-flex items-center gap-1 font-mono font-medium rounded-md border border-amber-500/40 bg-amber-950/40 text-amber-300 ${sizeClasses}`}
      >
        <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
        {label || 'UNCALIBRATED LOGIT'}
      </span>
    );
  }

  return (
    <span
      title="Experimental: Synthetic-composite trained model head"
      className={`inline-flex items-center gap-1 font-mono font-medium rounded-md border border-cyan-500/40 bg-cyan-950/40 text-cyan-300 ${sizeClasses}`}
    >
      <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
      {label || 'EXPERIMENTAL (SYNTHETIC)'}
    </span>
  );
};
