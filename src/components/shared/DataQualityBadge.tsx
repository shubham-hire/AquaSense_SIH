import React from 'react';
import { Waves, Activity } from 'lucide-react';

interface DataQualityBadgeProps {
  type: 'low_data_quality' | 'motion_uncorrected';
  size?: 'sm' | 'md';
}

export const DataQualityBadge: React.FC<DataQualityBadgeProps> = ({
  type,
  size = 'md',
}) => {
  const sizeClasses = size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-1 text-xs';

  if (type === 'low_data_quality') {
    return (
      <span
        title="Sensor / Motion Alert: Overlaps acoustic dropout or severe vessel heave row"
        className={`inline-flex items-center gap-1 font-mono font-medium rounded-md border border-[#8A7B5C]/70 bg-[#8A7B5C]/15 text-[#E6DCB8] ${sizeClasses}`}
      >
        <Waves className="w-3.5 h-3.5 text-[#E6DCB8]" />
        LOW DATA QUALITY
      </span>
    );
  }

  return (
    <span
      title="Platform Gyro Warning: Vessel roll/pitch uncorrected"
      className={`inline-flex items-center gap-1 font-mono font-medium rounded-md border border-[#8A7B5C]/60 bg-[#8A7B5C]/10 text-[#D8CCA8] ${sizeClasses}`}
    >
      <Activity className="w-3.5 h-3.5 text-[#D8CCA8]" />
      MOTION UNCORRECTED
    </span>
  );
};
