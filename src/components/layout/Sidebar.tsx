import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useSurveyStore } from '../../store/useSurveyStore';
import { 
  Terminal, 
  Layers, 
  Waves, 
  Box, 
  Flame, 
  ShieldCheck, 
  UploadCloud,
  FileText
} from 'lucide-react';

export const Sidebar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { activeSurveyId } = useSurveyStore();

  const navItems = [
    {
      label: 'Operator Console',
      icon: Terminal,
      path: `/surveys/${activeSurveyId}/console`,
      badge: 'LIVE',
    },
    {
      label: 'Executive Summary',
      icon: Layers,
      path: `/surveys/${activeSurveyId}/summary`,
      badge: null,
    },
    {
      label: 'Sonar Waterfall',
      icon: Waves,
      path: `/surveys/${activeSurveyId}/waterfall`,
      badge: null,
    },
    {
      label: '3D Digital Twin',
      icon: Box,
      path: `/surveys/${activeSurveyId}/twin`,
      badge: '3D',
    },
    {
      label: 'What We Killed',
      icon: Flame,
      path: `/surveys/${activeSurveyId}/ablations`,
      badge: 'ABLATIONS',
    },
    {
      label: 'Calibration Status',
      icon: ShieldCheck,
      path: `/settings/calibration`,
      badge: null,
    },
    {
      label: 'Upload & Ingest',
      icon: UploadCloud,
      path: `/`,
      badge: null,
    },
  ];

  return (
    <aside className="w-60 border-r border-slate-800/80 bg-[#030A17]/80 backdrop-blur-md flex flex-col justify-between shrink-0 select-none">
      <div className="p-3 space-y-1">
        <div className="px-3 py-2 text-[10px] font-mono tracking-widest text-slate-500 uppercase">
          NAVIGATION CONTROL
        </div>

        {navItems.map((item) => {
          const isActive = location.pathname === item.path || (item.path.includes('/console') && location.pathname.includes('/console'));
          const Icon = item.icon;

          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-sans font-medium transition-all group ${
                isActive
                  ? 'bg-cyan-500/15 text-cyan-200 border border-cyan-500/30 shadow-[0_0_12px_rgba(34,211,238,0.15)] font-semibold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Icon className={`w-4 h-4 transition-colors ${isActive ? 'text-cyan-400' : 'text-slate-500 group-hover:text-slate-300'}`} />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                  isActive ? 'bg-cyan-900/60 text-cyan-300 border border-cyan-400/40' : 'bg-slate-800 text-slate-400'
                }`}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Bottom Technical Stamp */}
      <div className="p-3 border-t border-slate-800/80 text-[11px] font-mono text-slate-500 space-y-1">
        <div className="flex justify-between items-center">
          <span>AI Engine</span>
          <span className="text-cyan-400">YOLO26n-seg</span>
        </div>
        <div className="flex justify-between items-center">
          <span>Verification</span>
          <span className="text-emerald-400">10-Feature L2</span>
        </div>
        <div className="flex justify-between items-center">
          <span>License</span>
          <span className="text-slate-400">BSD-3 Clean</span>
        </div>
      </div>
    </aside>
  );
};
