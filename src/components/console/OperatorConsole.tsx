import React from 'react';
import { SonarWaterfallPanel } from '../sonar/SonarWaterfallPanel';
import { LiveMapPanel } from '../map/LiveMapPanel';
import { DigitalTwinPanel } from '../three/DigitalTwinPanel';
import { DetectionQueue } from './DetectionQueue';
import { ThresholdControls } from './ThresholdControls';
import { RefusalStrip } from './RefusalStrip';

export const OperatorConsole: React.FC = () => {
  return (
    <div className="flex-1 min-h-0 flex flex-col p-4 gap-3 overflow-y-auto bg-[#111A2A]">
      {/* Operator Threshold & Class Filter Controls */}
      <ThresholdControls />

      {/* Main 4-Quadrant Tactical Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 flex-1 min-h-[700px]">
        {/* Top-Left: Sonar Waterfall Swath with Calipers */}
        <SonarWaterfallPanel className="min-h-[380px]" />

        {/* Top-Right: 3D Digital Twin with Instanced Threat Beacons */}
        <DigitalTwinPanel className="min-h-[380px]" />

        {/* Bottom-Left: Real-Time Map Overlay during Ingestion */}
        <LiveMapPanel className="min-h-[360px]" />

        {/* Bottom-Right: Detection Queue with Verification Badges */}
        <div className="min-h-[360px]">
          <DetectionQueue />
        </div>
      </div>

      {/* Persistent Bottom Refusal & Scientific Honesty Strip */}
      <RefusalStrip />
    </div>
  );
};
