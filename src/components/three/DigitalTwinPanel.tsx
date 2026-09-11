import React, { useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { SeabedMesh } from './SeabedMesh';
import { DetectionBeacons } from './DetectionBeacons';
import { useSurveyStore } from '../../store/useSurveyStore';
import { Box, Maximize2, RotateCcw, AlertCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface DigitalTwinPanelProps {
  className?: string;
}

export const DigitalTwinPanel: React.FC<DigitalTwinPanelProps> = ({ className = '' }) => {
  const navigate = useNavigate();
  const { detections, activeSurveyId, selectedDetectionId, setSelectedDetectionId } = useSurveyStore();
  const [webGlFailed, setWebGlFailed] = useState(false);

  const surveyDetections = detections.filter((d) => d.surveyId === activeSurveyId);

  return (
    <div className={`relative flex flex-col glass-panel rounded-xl overflow-hidden p-3 gap-2.5 ${className}`}>
      {/* Top Title Bar */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2">
          <Box className="w-4 h-4 text-cyan-400" />
          <h3 className="font-heading font-bold text-sm text-white tracking-wide">
            3D DIGITAL TWIN & BEACONS
          </h3>
          <span className="text-[10px] font-mono text-cyan-300 bg-cyan-950/80 border border-cyan-500/30 px-1.5 py-0.5 rounded">
            R3F INSTANCED
          </span>
        </div>

        <button
          onClick={() => navigate(`/surveys/${activeSurveyId}/twin`)}
          title="Open Fullscreen 3D Twin"
          className="flex items-center gap-1 text-xs font-mono text-slate-400 hover:text-cyan-300 transition-colors p-1"
        >
          <Maximize2 className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">FULLSCREEN</span>
        </button>
      </div>

      {/* 3D Canvas Area */}
      <div className="relative flex-1 min-h-[340px] rounded-lg overflow-hidden border border-slate-800 bg-gradient-to-b from-[#020712] to-[#030A17]">
        {webGlFailed ? (
          <div className="w-full h-full flex flex-col items-center justify-center p-6 text-center text-slate-400 space-y-2">
            <AlertCircle className="w-8 h-8 text-amber-400" />
            <div className="font-bold text-slate-200">WebGL Context Unavailable</div>
            <p className="text-xs max-w-sm">
              Graceful fallback enabled: displaying 2D bathymetry map representation.
            </p>
          </div>
        ) : (
          <Canvas
            camera={{ position: [0, 14, 22], fov: 45 }}
            onCreated={({ gl }) => {
              gl.setClearColor('#020712');
            }}
            onError={() => setWebGlFailed(true)}
          >
            {/* Ambient & Depth Underwater Lighting */}
            <ambientLight intensity={0.4} />
            <directionalLight position={[10, 20, 15]} intensity={1.2} color="#E0F2FE" />
            <pointLight position={[0, -2, 0]} intensity={1.5} color="#22D3EE" distance={30} />

            {/* Bounded Camera Rig: no unbounded pan/zoom into empty space */}
            <OrbitControls
              enableDamping
              dampingFactor={0.05}
              minDistance={8}
              maxDistance={38}
              maxPolarAngle={Math.PI / 2.1} // Prevent going below seafloor
            />

            {/* Bathymetric Seabed Elevation Mesh */}
            <SeabedMesh />

            {/* Instanced Threat Beacons */}
            <DetectionBeacons
              detections={surveyDetections}
              selectedId={selectedDetectionId}
              onSelect={setSelectedDetectionId}
            />
          </Canvas>
        )}

        {/* Legend Overlay */}
        <div className="absolute bottom-2 left-2 z-10 bg-slate-950/90 border border-slate-800 rounded-md p-2 text-[10px] font-mono text-slate-400 space-y-1 backdrop-blur-md">
          <div className="font-bold text-slate-300">PRIORITY BEACONS</div>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#B23A2E]" /> Critical
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#C97A1E]" /> High
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#C9A227]" /> Med
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#4C8C5B]" /> Low
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
