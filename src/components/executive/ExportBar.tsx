import React, { useState } from 'react';
import { useSurveyStore } from '../../store/useSurveyStore';
import { 
  generateReportJson, 
  generateReportCsv, 
  generateGeoJson, 
  downloadFile 
} from '../../services/exportService';
import { FileJson, FileSpreadsheet, Map, FileDown, CheckCircle2 } from 'lucide-react';

export const ExportBar: React.FC = () => {
  const { surveys, activeSurveyId, detections } = useSurveyStore();
  const [downloadSuccess, setDownloadSuccess] = useState<string | null>(null);

  const activeSurvey = surveys.find((s) => s.id === activeSurveyId) || surveys[0];
  const surveyDetections = detections.filter((d) => d.surveyId === activeSurveyId);

  const handleExport = (type: 'json' | 'csv' | 'geojson' | 'pdf') => {
    const timestamp = new Date().toISOString().slice(0, 10);

    if (type === 'json') {
      const content = generateReportJson(activeSurvey, surveyDetections);
      downloadFile(content, `AquaSense_${activeSurvey.id}_report_${timestamp}.json`, 'application/json');
      notifySuccess('Structured JSON Report');
    } else if (type === 'csv') {
      const content = generateReportCsv(activeSurvey, surveyDetections);
      downloadFile(content, `AquaSense_${activeSurvey.id}_report_${timestamp}.csv`, 'text/csv');
      notifySuccess('Structured CSV Report');
    } else if (type === 'geojson') {
      const content = generateGeoJson(activeSurvey, surveyDetections);
      downloadFile(content, `AquaSense_${activeSurvey.id}_hazards_${timestamp}.geojson`, 'application/geo+json');
      notifySuccess('GIS GeoJSON Layer');
    } else if (type === 'pdf') {
      window.print();
      notifySuccess('Mission Audit Document');
    }
  };

  const notifySuccess = (name: string) => {
    setDownloadSuccess(name);
    setTimeout(() => setDownloadSuccess(null), 3000);
  };

  return (
    <div className="glass-panel p-4 rounded-xl flex flex-wrap items-center justify-between gap-4 border border-cyan-500/20">
      <div>
        <h4 className="font-heading font-bold text-sm text-white flex items-center gap-2">
          <span>PS 26057 STRUCTURED ANOMALOUS REPORTING ENGINE</span>
          {downloadSuccess && (
            <span className="text-xs text-emerald-400 font-mono flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Downloaded {downloadSuccess}!
            </span>
          )}
        </h4>
        <p className="text-xs text-slate-400 font-sans mt-0.5">
          Exports include exact coordinates, real-world width/height dimensions, and classification per hazard.
        </p>
      </div>

      {/* Export Button Strip */}
      <div className="flex flex-wrap items-center gap-2">
        {/* 1. PS-Required JSON */}
        <button
          onClick={() => handleExport('json')}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-cyan-950/60 hover:bg-cyan-900/80 border border-cyan-500/40 text-cyan-200 text-xs font-mono font-semibold transition-all shadow-[0_0_10px_rgba(34,211,238,0.15)]"
        >
          <FileJson className="w-4 h-4 text-cyan-400" />
          <span>DOWNLOAD JSON (PS Mapped)</span>
        </button>

        {/* 2. PS-Required CSV */}
        <button
          onClick={() => handleExport('csv')}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 text-xs font-mono font-semibold transition-all"
        >
          <FileSpreadsheet className="w-4 h-4 text-emerald-400" />
          <span>DOWNLOAD CSV</span>
        </button>

        {/* 3. GIS GeoJSON */}
        <button
          onClick={() => handleExport('geojson')}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 text-xs font-mono font-semibold transition-all"
        >
          <Map className="w-4 h-4 text-blue-400" />
          <span>GEOJSON</span>
        </button>

        {/* 4. Printable PDF Brief */}
        <button
          onClick={() => handleExport('pdf')}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 text-xs font-mono font-semibold transition-all"
        >
          <FileDown className="w-4 h-4 text-amber-400" />
          <span>MISSION BRIEF PDF</span>
        </button>
      </div>
    </div>
  );
};
