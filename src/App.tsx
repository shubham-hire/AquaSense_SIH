import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { Sidebar } from './components/layout/Sidebar';
import { LandingPage } from './components/landing/LandingPage';
import { OperatorConsole } from './components/console/OperatorConsole';
import { ExecutiveSummary } from './components/executive/ExecutiveSummary';
import { SonarWaterfallView } from './components/sonar/SonarWaterfallView';
import { DigitalTwinView } from './components/three/DigitalTwinView';
import { DetectionDetailPage } from './components/detail/DetectionDetailPage';
import { AblationPanel } from './components/ablations/AblationPanel';
import { CalibrationStatusPage } from './components/calibration/CalibrationStatusPage';
import { useSurveyStore } from './store/useSurveyStore';

export const App: React.FC = () => {
  const { activeSurveyId } = useSurveyStore();

  return (
    <AppShell>
      <Sidebar />
      <main className="flex-1 flex overflow-hidden">
        <Routes>
          <Route path="/" element={<LandingPage />} />
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
      </main>
    </AppShell>
  );
};

export default App;
