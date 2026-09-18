import React, { useCallback, useEffect, useState } from 'react';
import { WaterfallCanvas, type WaterfallStatus } from './WaterfallCanvas';
import { PaletteSwitcher } from './PaletteSwitcher';
import { MeasurementCalipers } from './MeasurementCalipers';
import { Waves, Maximize2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useSurveyStore } from '../../store/useSurveyStore';
import { waterfallImageUrl } from '../../services/api';

interface SonarWaterfallPanelProps {
  className?: string;
}

export const SonarWaterfallPanel: React.FC<SonarWaterfallPanelProps> = ({ className = '' }) => {
  const navigate = useNavigate();
  const { activeSurveyId } = useSurveyStore();
  const [waterfallStatus, setWaterfallStatus] = useState<WaterfallStatus>('loading');
  const onWaterfallStatus = useCallback((status: WaterfallStatus) => setWaterfallStatus(status), []);

  useEffect(() => {
    setWaterfallStatus('loading');
  }, [activeSurveyId]);

  return (
    <div className={`flex flex-col glass-panel rounded-xl overflow-hidden p-3 gap-2.5 ${className}`}>
      {/* Header Bar */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2">
          <Waves className="w-4 h-4 text-cyan-400" />
          <h3 className="font-heading font-bold text-sm text-white tracking-wide">
            SONAR WATERFALL SWATH
          </h3>
          <span className="text-[10px] font-mono text-slate-400 bg-slate-900 border border-slate-700 px-1.5 py-0.5 rounded">
            PORT / NADIR / STARBOARD
          </span>
        </div>

        <button
          onClick={() => navigate(`/surveys/${activeSurveyId}/waterfall`)}
          title="Open Fullscreen Waterfall"
          className="flex items-center gap-1 text-xs font-mono text-slate-400 hover:text-cyan-300 transition-colors p-1"
        >
          <Maximize2 className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">FULLSCREEN</span>
        </button>
      </div>

      {/* Waterfall Display with Calipers Overlay */}
      <div className="relative flex-1 min-h-[340px] rounded-lg overflow-hidden bg-black/90">
        <WaterfallCanvas
          sourceUrl={activeSurveyId && activeSurveyId !== 'SURVEY-NEW' ? waterfallImageUrl(activeSurveyId) : ''}
          onStatusChange={onWaterfallStatus}
        />
        {waterfallStatus === 'ready' && <MeasurementCalipers />}
      </div>

      {/* Bottom Controls */}
      <PaletteSwitcher />
    </div>
  );
};
