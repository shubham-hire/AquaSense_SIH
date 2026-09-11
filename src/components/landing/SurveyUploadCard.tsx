import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSurveyStore } from '../../store/useSurveyStore';
import { UploadCloud, FileText, CheckCircle2, Waves, ArrowRight } from 'lucide-react';

export const SurveyUploadCard: React.FC = () => {
  const navigate = useNavigate();
  const { activeSurveyId, setIsLiveStreaming } = useSurveyStore();
  const [dragActive, setDragActive] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<string | null>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setUploadedFile(e.dataTransfer.files[0].name);
    }
  };

  const handleSimulatedUpload = (name: string) => {
    setUploadedFile(name);
  };

  const startProcessing = () => {
    setIsLiveStreaming(true);
    navigate(`/surveys/${activeSurveyId}/console`);
  };

  return (
    <div className="glass-panel p-6 rounded-2xl border border-cyan-500/30 flex flex-col gap-4">
      <div>
        <div className="flex items-center gap-2">
          <UploadCloud className="w-5 h-5 text-cyan-400" />
          <h3 className="font-heading font-extrabold text-base text-white">
            RAW SONAR LOG INGESTION (PS 26057 REQUIRED)
          </h3>
        </div>
        <p className="text-xs text-slate-400 mt-1 font-sans">
          Upload Triton <code className="text-cyan-300 font-mono">.XTF</code>, EdgeTech <code className="text-cyan-300 font-mono">.JSF</code>, Lowrance <code className="text-cyan-300 font-mono">.SL2</code>, or GeoTIFF swath logs for real-time pipeline processing and map overlay.
        </p>
      </div>

      {/* Drag and Drop Zone */}
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        className={`p-8 rounded-xl border-2 border-dashed transition-all flex flex-col items-center justify-center text-center gap-2 cursor-pointer ${
          dragActive
            ? 'border-cyan-400 bg-cyan-950/40'
            : 'border-slate-700 bg-slate-950/60 hover:border-slate-600'
        }`}
      >
        <div className="w-12 h-12 rounded-full bg-cyan-500/10 border border-cyan-400/20 flex items-center justify-center text-cyan-300">
          <Waves className="w-6 h-6" />
        </div>
        <div className="text-sm font-semibold text-white">
          {uploadedFile ? `Loaded: ${uploadedFile}` : 'Drag & drop sonar mission file here'}
        </div>
        <div className="text-xs text-slate-400 font-mono">
          Supports .XTF, .JSF, .SL2, GeoTIFF up to 2.5 GB
        </div>
      </div>

      {/* Preset Indian Ocean Sonar Log Demos */}
      <div className="space-y-1.5">
        <div className="text-[11px] font-mono text-slate-400 uppercase">
          OR LOAD SAMPLE HYDROGRAPHIC MISSION LOG:
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono">
          <button
            onClick={() => handleSimulatedUpload('ORV_Sagar_Nidhi_Swatch_Deep_09.xtf')}
            className={`p-2.5 rounded-lg border text-left flex items-center justify-between transition-all ${
              uploadedFile?.includes('Sagar_Nidhi')
                ? 'bg-cyan-950/60 border-cyan-400/80 text-cyan-200'
                : 'bg-slate-900/60 border-slate-800 text-slate-300 hover:bg-slate-900'
            }`}
          >
            <div>
              <div className="font-semibold text-white">ORV_Sagar_Nidhi_09.xtf</div>
              <div className="text-[10px] text-slate-400">410 kHz EdgeTech Swatch Log (14.8 km²)</div>
            </div>
            <FileText className="w-4 h-4 text-cyan-400" />
          </button>

          <button
            onClick={() => handleSimulatedUpload('Sagar_Kanya_Gulf_Mannar_MPA.jsf')}
            className={`p-2.5 rounded-lg border text-left flex items-center justify-between transition-all ${
              uploadedFile?.includes('Mannar')
                ? 'bg-cyan-950/60 border-cyan-400/80 text-cyan-200'
                : 'bg-slate-900/60 border-slate-800 text-slate-300 hover:bg-slate-900'
            }`}
          >
            <div>
              <div className="font-semibold text-white">Sagar_Kanya_Mannar.jsf</div>
              <div className="text-[10px] text-slate-400">900 kHz Klein 3900 MPA Coral Log</div>
            </div>
            <FileText className="w-4 h-4 text-cyan-400" />
          </button>
        </div>
      </div>

      {/* Start Ingestion Button */}
      <button
        onClick={startProcessing}
        className="w-full mt-2 py-3 rounded-xl bg-gradient-to-r from-[#065A82] to-[#1C7293] hover:from-[#0873A6] hover:to-[#228BAF] text-white font-heading font-extrabold text-sm border border-cyan-400/50 shadow-[0_0_20px_rgba(34,211,238,0.25)] flex items-center justify-center gap-2 transition-all cursor-pointer"
      >
        <span>LAUNCH PIPELINE & REAL-TIME MAP STREAM</span>
        <ArrowRight className="w-4 h-4" />
      </button>
    </div>
  );
};
