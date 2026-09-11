import React from 'react';
import { Detection } from '../../types';

interface MaskOrBoxOutlineProps {
  detection: Detection;
  width?: number;
  height?: number;
  strokeWidth?: number;
  interactive?: boolean;
  className?: string;
}

export const MaskOrBoxOutline: React.FC<MaskOrBoxOutlineProps> = ({
  detection,
  width = 100,
  height = 100,
  strokeWidth = 2,
  interactive = false,
  className = '',
}) => {
  const getStrokeColor = () => {
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

  const strokeColor = getStrokeColor();

  // If pixel-level polygon segmentation mask exists (for ghost nets, ropes)
  if (detection.segmentationMask && detection.segmentationMask.data.length > 0) {
    const rawPoints = detection.segmentationMask.data;
    // Normalize coordinates to 0..width and 0..height
    const minX = Math.min(...rawPoints.map((p) => p[0]));
    const maxX = Math.max(...rawPoints.map((p) => p[0]));
    const minY = Math.min(...rawPoints.map((p) => p[1]));
    const maxY = Math.max(...rawPoints.map((p) => p[1]));
    const spanX = Math.max(1, maxX - minX);
    const spanY = Math.max(1, maxY - minY);

    const pointsString = rawPoints
      .map((p) => {
        const nx = ((p[0] - minX) / spanX) * (width - 16) + 8;
        const ny = ((p[1] - minY) / spanY) * (height - 16) + 8;
        return `${nx.toFixed(1)},${ny.toFixed(1)}`;
      })
      .join(' ');

    return (
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className={`pointer-events-none ${className}`}
      >
        <polygon
          points={pointsString}
          fill={strokeColor}
          fillOpacity={0.25}
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          strokeDasharray="4 2"
          className={interactive ? 'transition-all duration-300' : ''}
        />
      </svg>
    );
  }

  // Otherwise, fallback to bounding box outline for rigid objects (pipes, cylinders, shipwrecks)
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={`pointer-events-none ${className}`}
    >
      <rect
        x={strokeWidth * 2}
        y={strokeWidth * 2}
        width={width - strokeWidth * 4}
        height={height - strokeWidth * 4}
        rx={4}
        fill={strokeColor}
        fillOpacity={0.15}
        stroke={strokeColor}
        strokeWidth={strokeWidth}
      />
      {/* Corner crosshairs */}
      <line
        x1={strokeWidth * 2}
        y1={strokeWidth * 2 + 8}
        x2={strokeWidth * 2 + 8}
        y2={strokeWidth * 2 + 8}
        stroke="#22D3EE"
        strokeWidth={1.5}
      />
      <line
        x1={width - strokeWidth * 2 - 8}
        y1={strokeWidth * 2 + 8}
        x2={width - strokeWidth * 2}
        y2={strokeWidth * 2 + 8}
        stroke="#22D3EE"
        strokeWidth={1.5}
      />
    </svg>
  );
};
