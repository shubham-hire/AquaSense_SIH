import React from 'react';
import { useSurveyStore } from '../../store/useSurveyStore';
import { SonarColormap } from '../../utils/colormaps';
import { Palette, Eye, AlertTriangle } from 'lucide-react';

export const PaletteSwitcher: React.FC = () => {
  const { waterfallPalette, setWaterfallPalette, dspFilterActive, setDspFilterActive } = useSurveyStore();

  const palettes: { id: SonarColormap; label: string; preview: string }[] = [
    { id: 'amber', label: 'Amber Sonar', preview: 'from-amber-700 via-amber-400 to-amber-100' },
    { id: 'cobalt', label: 'Naval Cobalt', preview: 'from-blue-950 via-cyan-500 to-cyan-100' },
    { id: 'ironbow', label: 'Ironbow', preview: 'from-purple-900 via-red-500 to-yellow-300' },
    { id: 'grayscale', label: 'Monochrome', preview: 'from-slate-900 via-slate-500 to-slate-100' },
  ];

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 p-2 bg-slate-950/70 border border-slate-800 rounded-lg text-xs font-mono">
      {/* Colormap Selectors */}
      <div className="flex items-center gap-1.5">
        <Palette className="w-3.5 h-3.5 text-cyan-400 mr-1" />
        <span className="text-slate-400 text-[11px] mr-1">PALETTE:</span>
        <div className="flex items-center gap-1">
          {palettes.map((p) => (
            <button
              key={p.id}
              onClick={() => setWaterfallPalette(p.id)}
              className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] transition-all border ${
                waterfallPalette === p.id
                  ? 'bg-cyan-500/20 text-cyan-200 border-cyan-400/60 shadow-[0_0_8px_rgba(34,211,238,0.2)] font-semibold'
                  : 'text-slate-400 border-transparent hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <span className={`w-2.5 h-2.5 rounded-full bg-gradient-to-r ${p.preview}`} />
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Switchable DSP Toggle with Honest Ablation E06 Warning */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setDspFilterActive(!dspFilterActive)}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] transition-all border ${
            dspFilterActive
              ? 'bg-cyan-500/20 text-cyan-300 border-cyan-400/50 shadow-[0_0_10px_rgba(34,211,238,0.2)]'
              : 'bg-slate-900/80 text-slate-400 border-slate-700 hover:text-slate-200'
          }`}
        >
          <Eye className="w-3.5 h-3.5" />
          <span>DSP ENHANCE: {dspFilterActive ? 'ON' : 'OFF'}</span>
        </button>

        <span
          title="Ablation E06 finding: Destructive preprocessing (CLAHE/notch) degrades mAP50 by -72%. DSP is kept for visualization and caliper enhancement only, disabled in the detection path."
          className="cursor-help flex items-center text-[10px] text-amber-400/90 gap-1 bg-amber-950/40 border border-amber-500/30 px-1.5 py-0.5 rounded"
        >
          <AlertTriangle className="w-3 h-3 text-amber-400" />
          <span className="hidden sm:inline">VISUAL ONLY (Ablation E06)</span>
        </span>
      </div>
    </div>
  );
};
