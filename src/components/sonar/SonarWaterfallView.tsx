import React from 'react';
import { SonarWaterfallPanel } from './SonarWaterfallPanel';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Waves } from 'lucide-react';
import { useSurveyStore } from '../../store/useSurveyStore';

export const SonarWaterfallView: React.FC = () => {
  const navigate = useNavigate();
  const { activeSurveyId } = useSurveyStore();

  return (
    <div className="flex-1 flex flex-col p-4 gap-3 bg-[#111A2A] overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <button
          onClick={() => navigate(`/surveys/${activeSurveyId}/console`)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs font-mono text-slate-300 hover:text-white transition-all"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>BACK TO OPERATOR CONSOLE</span>
        </button>

        <div className="flex items-center gap-2 text-xs font-mono text-cyan-400">
          <Waves className="w-4 h-4" />
          <span>FULLSCREEN HYDROGRAPHIC WATERFALL DISPLAY</span>
        </div>
      </div>

      <div className="flex-1 flex flex-col min-h-0">
        <SonarWaterfallPanel className="flex-1" />
      </div>
    </div>
  );
};
