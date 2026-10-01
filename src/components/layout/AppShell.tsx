import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSurveyStore } from '../../store/useSurveyStore';
import { useLiveDetectionSocket } from '../../services/socket';
import { fetchPersistedSurveys, fetchSurveyDetections } from '../../services/api';
import { InteractiveCursor } from '../shared/InteractiveCursor';
import { 
  Radar, 
  Layers, 
  Terminal, 
  ShieldCheck,
  ShieldAlert,
  ShieldQuestion,
  AlertTriangle,
  X,
  Play,
  Pause,
  RotateCcw,
} from 'lucide-react';

export const AppShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();
  const {
    surveys,
    activeSurveyId,
    setActiveSurveyId,
    mode,
    setMode,
    isLiveStreaming,
    setIsLiveStreaming,
    processingError,
    clearProcessingError,
    resetStream,
    detections,
    hydrateSurveys,
    replaceSurveyDetections,
  } = useSurveyStore();

  // Initialize live streaming synchronization hook
  useLiveDetectionSocket();

  // The browser store is ephemeral; restore the mission index and its active
  // detection set from SQLite whenever the app opens or an operator switches missions.
  useEffect(() => {
    let cancelled = false;
    fetchPersistedSurveys()
      .then((persisted) => {
        if (!cancelled) hydrateSurveys(persisted);
      })
      .catch(() => {
        // The landing page remains usable when the local API is not running.
      });
    return () => { cancelled = true; };
  }, [hydrateSurveys]);

  useEffect(() => {
    let cancelled = false;
    if (activeSurveyId === 'SURVEY-NEW' || isLiveStreaming) return undefined;
    fetchSurveyDetections(activeSurveyId)
      .then((persisted) => {
        if (!cancelled) replaceSurveyDetections(activeSurveyId, persisted);
      })
      .catch(() => {
        // A just-created mission may not have completed ingestion yet.
      });
    return () => { cancelled = true; };
  }, [activeSurveyId, isLiveStreaming, replaceSurveyDetections]);

  const activeSurvey = surveys.find((s) => s.id === activeSurveyId) ?? null;
  const activeSurveyDetections = detections.filter((detection) => detection.surveyId === activeSurveyId);
  const calibrationStatus = activeSurveyDetections.length === 0
    ? 'unknown'
    : activeSurveyDetections.every((detection) => detection.calibrated)
      ? 'calibrated'
      : 'uncalibrated';
  const calibrationDisplay = calibrationStatus === 'calibrated'
    ? {
        label: 'PLATT CALIBRATED',
        title: 'Every detection in the active survey is marked calibrated.',
        className: 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300 hover:border-emerald-400',
        iconClassName: 'text-emerald-400',
        Icon: ShieldCheck,
      }
    : calibrationStatus === 'uncalibrated'
      ? {
          label: 'NOT CALIBRATED',
          title: 'At least one detection in the active survey is marked calibrated: false.',
          className: 'bg-amber-950/40 border-amber-500/40 text-amber-300 hover:border-amber-400',
          iconClassName: 'text-amber-400',
          Icon: ShieldAlert,
        }
      : {
          label: 'CALIBRATION UNKNOWN',
          title: 'No detections are available for the active survey, so calibration status is unknown.',
          className: 'bg-slate-900/70 border-slate-600/60 text-slate-300 hover:border-slate-500',
          iconClassName: 'text-slate-400',
          Icon: ShieldQuestion,
        };
  const CalibrationIcon = calibrationDisplay.Icon;

  const handleToggleMode = () => {
    if (mode === 'operator') {
      setMode('executive');
      navigate(`/surveys/${activeSurveyId}/summary`);
    } else {
      setMode('operator');
      navigate(`/surveys/${activeSurveyId}/console`);
    }
  };

  return (
    <div className="app-ocean h-screen overflow-hidden flex flex-col bg-[#111A2A] text-slate-100">
      <InteractiveCursor />
      {/* Top Telemetry & Command Bar */}
      <header className="relative z-50 h-16 shrink-0 border-b border-cyan-300/20 bg-[#142238]/90 backdrop-blur-md px-4 flex items-center justify-between gap-4">
        {/* Left: Branding & Vessel Profile */}
        <div className="flex items-center gap-3">
          <div 
            onClick={() => navigate('/')} 
            className="flex items-center gap-2.5 cursor-pointer group"
          >
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-[#065A82] to-[#1C7293] border border-cyan-400/40 flex items-center justify-center p-2 shadow-[0_0_15px_rgba(34,211,238,0.25)] group-hover:border-cyan-300 transition-all">
              <Radar className="w-6 h-6 text-cyan-200 group-hover:rotate-45 transition-transform duration-500" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-heading font-extrabold text-lg text-white tracking-wide">
                  OCEAN<span className="text-cyan-400">AID</span>
                </span>
                <span className="text-[10px] font-mono uppercase bg-cyan-950/80 text-cyan-300 border border-cyan-500/30 px-1.5 py-0.5 rounded">
                  MoES / NIOT
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-sans hidden sm:block">
                Deep Ocean Marine Debris & Sonar Anomaly Platform (PS 26057)
              </p>
            </div>
          </div>

          <div className="h-6 w-[1px] bg-slate-700/60 mx-1 hidden md:block" />

          {/* Active Survey Selector Dropdown — only shown when surveys exist */}
          {surveys.length > 0 && (
            <div className="relative hidden md:block">
              <div className="flex items-center gap-2 bg-slate-900/80 border border-slate-700/80 rounded-lg px-3 py-1.5 text-xs">
                <span className="text-slate-400 font-mono">MISSION:</span>
                <select
                  value={activeSurveyId}
                  onChange={(e) => setActiveSurveyId(e.target.value)}
                  className="bg-transparent text-cyan-200 font-medium font-sans focus:outline-none cursor-pointer pr-4"
                >
                  {surveys.map((s) => (
                    <option key={s.id} value={s.id} className="bg-slate-900 text-white">
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}
        </div>

        {/* Center: Live Processing Telemetry */}
        <div className="hidden lg:flex items-center gap-4 bg-slate-950/60 border border-cyan-500/20 px-4 py-1.5 rounded-full text-xs font-mono">
          <div className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${activeSurvey ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'}`} />
            <span className="text-slate-300">{activeSurvey ? activeSurvey.vesselName : 'No active mission'}</span>
          </div>
          <span className="text-slate-600">|</span>
          <span className="text-slate-400">
            {activeSurvey ? `${activeSurvey.frequencyKhz} kHz SSS` : 'Upload a file to begin'}
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-cyan-300">
            {activeSurvey ? `${activeSurvey.summaryMetrics.verifiedCount} Verified Targets` : '—'}
          </span>
        </div>

        {/* Right: Controls & Mode Switcher */}
        <div className="flex items-center gap-2.5">
          {/* Live Sonar Stream Toggle */}
          <div className="flex items-center bg-slate-900/90 border border-slate-700 rounded-lg p-1">
            <button
              onClick={() => setIsLiveStreaming(!isLiveStreaming)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono font-medium transition-all ${
                isLiveStreaming
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-[0_0_10px_rgba(245,158,11,0.25)]'
                  : 'text-slate-300 hover:text-white'
              }`}
            >
              {isLiveStreaming ? (
                <>
                  <Pause className="w-3.5 h-3.5 text-amber-400" />
                  STREAMING
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 text-emerald-400" />
                  STREAM LOG
                </>
              )}
            </button>
            <button
              onClick={resetStream}
              title="Reset Live Stream"
              className="p-1 text-slate-400 hover:text-cyan-300 transition-colors ml-1"
            >
              <RotateCcw className="w-3 h-3" />
            </button>
          </div>

          {/* Executive vs Operator Mode Toggle */}
          <button
            onClick={handleToggleMode}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-sans font-semibold border transition-all ${
              mode === 'executive'
                ? 'bg-gradient-to-r from-emerald-600/30 to-cyan-600/30 text-cyan-200 border-cyan-400/50 shadow-[0_0_12px_rgba(34,211,238,0.25)]'
                : 'bg-slate-900 border-slate-700 text-slate-200 hover:border-slate-500'
            }`}
          >
            {mode === 'executive' ? (
              <>
                <Layers className="w-3.5 h-3.5 text-cyan-400" />
                EXECUTIVE DECK
              </>
            ) : (
              <>
                <Terminal className="w-3.5 h-3.5 text-amber-400" />
                OPERATOR CONSOLE
              </>
            )}
          </button>

          {/* Model Calibration Status Indicator */}
          <div
            onClick={() => navigate('/settings/calibration')}
            title={calibrationDisplay.title}
            className={`hidden sm:flex items-center gap-1.5 border px-2.5 py-1.5 rounded-lg text-xs font-mono cursor-pointer transition-colors ${calibrationDisplay.className}`}
          >
            <CalibrationIcon className={`w-3.5 h-3.5 ${calibrationDisplay.iconClassName}`} />
            <span className="hidden xl:inline">{calibrationDisplay.label}</span>
          </div>
        </div>

        {processingError && (
          <div
            role="alert"
            className="absolute top-full left-1/2 mt-2 flex w-[calc(100vw-2rem)] max-w-2xl -translate-x-1/2 items-center gap-2 rounded-lg border border-rose-500/40 bg-rose-950/95 px-3 py-2 text-xs font-mono text-rose-200 shadow-lg backdrop-blur-md"
          >
            <AlertTriangle className="h-4 w-4 shrink-0 text-rose-400" />
            <span className="min-w-0 flex-1 truncate" title={processingError}>{processingError}</span>
            <button
              type="button"
              onClick={clearProcessingError}
              title="Dismiss processing error"
              aria-label="Dismiss processing error"
              className="shrink-0 rounded p-0.5 text-rose-300 transition-colors hover:bg-rose-900 hover:text-white"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </header>

      {/* Main Body with Persistent Navigation */}
      <div className="flex-1 min-h-0 flex overflow-hidden">
        {children}
      </div>
    </div>
  );
};
