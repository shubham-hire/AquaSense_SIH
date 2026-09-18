import React, { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSurveyStore, DEFAULT_SURVEY_ID } from '../../store/useSurveyStore';
import { UploadCloud, Waves, ArrowRight, AlertCircle, LoaderCircle } from 'lucide-react';
import { fetchSurveyNavigation, ingestAndProcessSurvey } from '../../services/api';

function createSurveyId(): string {
  const uniquePart = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID().slice(0, 8)
    : Math.random().toString(36).slice(2, 10);
  return `survey-${Date.now().toString(36)}-${uniquePart}`;
}

export const SurveyUploadCard: React.FC = () => {
  const navigate = useNavigate();
  const {
    activeSurveyId,
    replaceSurveyDetections,
    setIsLiveStreaming,
    setSurveyNavigation,
    setUploadedImageUrl,
    ensureSurvey,
  } = useSurveyStore();
  const [dragActive, setDragActive] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [surveyId, setSurveyId] = useState(createSurveyId);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [qcSummary, setQcSummary] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const selectFile = (file: File) => {
    setSurveyId(createSurveyId());
    setSelectedFile(file);
    setUploadedFileName(file.name);
    setError(null);
    setQcSummary(null);
    // Revoke the previous blob URL and create a new one for image preview
    const isImageFile = file.type.startsWith('image/');
    if (isImageFile) {
      const url = URL.createObjectURL(file);
      setUploadedImageUrl(url);
    } else {
      setUploadedImageUrl(null);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      selectFile(e.dataTransfer.files[0]);
    }
  };

  const startProcessing = async () => {
    if (!selectedFile) {
      setError('Choose a sonar file or image first.');
      return;
    }
    setIsProcessing(true);
    setError(null);
    try {
      ensureSurvey({
        id: surveyId,
        codeName: `UPLOAD-${surveyId}`,
        name: selectedFile.name,
        vesselName: 'Not provided',
        vehicleType: 'Uploaded survey',
        areaSqKm: 0,
        swathWidthMeters: 0,
        status: 'Processing',
        startTime: new Date().toISOString(),
        locationName: 'Navigation pending',
        centerCoordinates: [0, 0],
        trackPoints: [],
        frequencyKhz: 0,
        summaryMetrics: {
          totalPings: 0,
          candidateCount: 0,
          verifiedCount: 0,
          rejectedCount: 0,
          unlocatedCount: 0,
          uncalibratedCount: 0,
          lowQualityCount: 0,
          avgConfidencePercent: 0,
          precisionGainPercent: 0,
        },
      });
      setSurveyNavigation(surveyId, { status: 'loading', mapCenter: null, trackPoints: [] });
      const qc = await ingestAndProcessSurvey(surveyId, selectedFile);
      try {
        setSurveyNavigation(surveyId, await fetchSurveyNavigation(surveyId));
      } catch (navigationError) {
        setSurveyNavigation(surveyId, {
          status: 'error',
          mapCenter: null,
          trackPoints: [],
          error: navigationError instanceof Error ? navigationError.message : 'Navigation could not be loaded.',
        });
      }
      setQcSummary(`QC ${qc.status}: ${qc.ping_count} pings · ${qc.dropout_ratio_percent}% dropout`);
      // The WebSocket hook replaces the UI as candidates clear verification.
      replaceSurveyDetections(surveyId, []);
      setIsLiveStreaming(true);
      navigate(`/surveys/${encodeURIComponent(surveyId)}/console`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to process the sonar file.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="glass-panel p-6 rounded-2xl border border-cyan-500/30 flex flex-col gap-4">
      <div>
        <div className="flex items-center gap-2">
          <UploadCloud className="w-5 h-5 text-cyan-400" />
          <h3 className="font-heading font-extrabold text-base text-white">
            UPLOAD SURVEY FILE OR IMAGE
          </h3>
        </div>
        <p className="text-xs text-slate-400 mt-1 font-sans">
          Upload Triton <code className="text-cyan-300 font-mono">.XTF</code>, EdgeTech <code className="text-cyan-300 font-mono">.JSF</code>, Lowrance <code className="text-cyan-300 font-mono">.SL2</code>, GeoTIFF, or any sonar image (PNG / JPG) for AI pipeline detection.
        </p>
      </div>

      {/* Drag and Drop Zone */}
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
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
          {uploadedFileName ? `Loaded: ${uploadedFileName}` : 'Drag & drop sonar mission file or image here'}
        </div>
        <div className="text-xs text-slate-400 font-mono">
          Supports .XTF, .JSF, .SL2, GeoTIFF, PNG, JPG up to 500 MB
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".xtf,.jsf,.sl2,.tif,.tiff,.png,.jpg,.jpeg"
          className="hidden"
          onChange={(event) => event.target.files?.[0] && selectFile(event.target.files[0])}
        />
      </div>

      {qcSummary && <p className="text-xs font-mono text-emerald-300">{qcSummary}</p>}
      {error && <p className="text-xs font-mono text-rose-300 flex gap-1.5"><AlertCircle className="w-4 h-4 shrink-0" />{error}</p>}

      {/* Start Ingestion Button */}
      <button
        onClick={startProcessing}
        disabled={isProcessing || !selectedFile}
        className="w-full mt-2 py-3 rounded-xl bg-gradient-to-r from-[#065A82] to-[#1C7293] hover:from-[#0873A6] hover:to-[#228BAF] text-white font-heading font-extrabold text-sm border border-cyan-400/50 shadow-[0_0_20px_rgba(34,211,238,0.25)] flex items-center justify-center gap-2 transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
      >
        <span>{isProcessing ? 'INGESTING & PROCESSING…' : 'LAUNCH PIPELINE & DETECT'}</span>
        {isProcessing ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
      </button>
    </div>
  );
};
