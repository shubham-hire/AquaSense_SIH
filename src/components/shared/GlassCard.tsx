import React from 'react';

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  elevated?: boolean;
  inset?: boolean;
  onClick?: () => void;
}

export const GlassCard: React.FC<GlassCardProps> = ({
  children,
  className = '',
  elevated = false,
  inset = false,
  onClick,
}) => {
  const panelClass = elevated
    ? 'glass-panel-elevated'
    : inset
    ? 'glass-panel-inset'
    : 'glass-panel';

  return (
    <div
      onClick={onClick}
      className={`rounded-xl ${panelClass} ${onClick ? 'cursor-pointer transition-all duration-200 hover:border-cyan-400/50' : ''} ${className}`}
    >
      {children}
    </div>
  );
};
