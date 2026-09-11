import React from 'react';
import { PriorityLevel } from '../../types';

interface PriorityBadgeProps {
  priority: PriorityLevel;
  className?: string;
  size?: 'sm' | 'md';
}

export const PriorityBadge: React.FC<PriorityBadgeProps> = ({
  priority,
  className = '',
  size = 'md',
}) => {
  const getStyle = () => {
    switch (priority) {
      case 'CRITICAL':
        return 'bg-[#B23A2E]/20 text-[#FF6B6B] border-[#B23A2E]/60 shadow-[0_0_10px_rgba(178,58,46,0.35)]';
      case 'HIGH':
        return 'bg-[#C97A1E]/20 text-[#FFA94D] border-[#C97A1E]/60 shadow-[0_0_10px_rgba(201,122,30,0.3)]';
      case 'MEDIUM':
        return 'bg-[#C9A227]/20 text-[#FFE066] border-[#C9A227]/60';
      case 'LOW':
      default:
        return 'bg-[#4C8C5B]/20 text-[#8CE99A] border-[#4C8C5B]/60';
    }
  };

  const sizeClasses = size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs';

  return (
    <span
      className={`inline-flex items-center gap-1 font-mono font-semibold tracking-wider uppercase rounded-md border ${sizeClasses} ${getStyle()} ${className}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
      {priority}
    </span>
  );
};
