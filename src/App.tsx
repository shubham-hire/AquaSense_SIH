import React, { Suspense, lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { Sidebar } from './components/layout/Sidebar';
import { IntroLanding } from './components/landing/IntroLanding';

const LandingPage = lazy(() => import('./components/landing/LandingPage').then((module) => ({ default: module.LandingPage })));
const OperatorConsole = lazy(() => import('./components/console/OperatorConsole').then((module) => ({ default: module.OperatorConsole })));
const ExecutiveSummary = lazy(() => import('./components/executive/ExecutiveSummary').then((module) => ({ default: module.ExecutiveSummary })));
const SonarWaterfallView = lazy(() => import('./components/sonar/SonarWaterfallView').then((module) => ({ default: module.SonarWaterfallView })));
const DigitalTwinView = lazy(() => import('./components/three/DigitalTwinView').then((module) => ({ default: module.DigitalTwinView })));
const DetectionDetailPage = lazy(() => import('./components/detail/DetectionDetailPage').then((module) => ({ default: module.DetectionDetailPage })));
const AblationPanel = lazy(() => import('./components/ablations/AblationPanel').then((module) => ({ default: module.AblationPanel })));
const CalibrationStatusPage = lazy(() => import('./components/calibration/CalibrationStatusPage').then((module) => ({ default: module.CalibrationStatusPage })));

const RouteFallback = () => (
  <div className="flex flex-1 items-center justify-center bg-[#111A2A] font-mono text-sm text-cyan-300">
    Loading workspace…
  </div>
);

export const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<IntroLanding />} />
      <Route path="*" element={<AppShell><Sidebar /><main className="flex-1 min-w-0 flex overflow-hidden">
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/ingest" element={<LandingPage />} />
            <Route path="/surveys/:id/console" element={<OperatorConsole />} />
            <Route path="/surveys/:id/summary" element={<ExecutiveSummary />} />
            <Route path="/surveys/:id/waterfall" element={<SonarWaterfallView />} />
            <Route path="/surveys/:id/twin" element={<DigitalTwinView />} />
            <Route path="/surveys/:id/detections/:d" element={<DetectionDetailPage />} />
            <Route path="/surveys/:id/ablations" element={<AblationPanel />} />
            <Route path="/settings/calibration" element={<CalibrationStatusPage />} />
            {/* Default redirect */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </main></AppShell>} />
    </Routes>
  );
};

export default App;
