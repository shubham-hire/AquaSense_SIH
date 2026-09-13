import React, { useState } from 'react';
import { CheckCircle2, XCircle, RefreshCw, MapPin, MapPinOff, Trash2, Loader2 } from 'lucide-react';
import { useSurveyStore } from '../../store/useSurveyStore';
import { submitReview, deleteReview } from '../../services/api';
import type { ReviewOutcome } from '../../types';

// The 6 canonical classes from configs/sonar_debris_yolo26.yaml
const CLASS_OPTIONS = [
  { value: 'human_artifact_wreck',         label: 'Human Artifact / Wreck' },
  { value: 'electrical_cable',             label: 'Electrical Cable' },
  { value: 'electronic_hazard',            label: 'Electronic Hazard' },
  { value: 'plastic_debris',              label: 'Plastic Debris' },
  { value: 'metal_drum_scrap',            label: 'Metal Drum / Scrap' },
  { value: 'biological_geological_exclusion', label: 'Biological / Geological' },
];

const OUTCOME_STYLES: Record<ReviewOutcome, { bg: string; border: string; text: string; icon: React.ReactNode; label: string }> = {
  CONFIRMED:    { bg: 'bg-emerald-950/60', border: 'border-emerald-500/60', text: 'text-emerald-300', icon: <CheckCircle2 className="w-4 h-4" />, label: 'Confirm' },
  REJECTED_FP:  { bg: 'bg-red-950/60',     border: 'border-red-500/60',     text: 'text-red-300',     icon: <XCircle className="w-4 h-4" />,       label: 'False Positive' },
  CORRECTED:    { bg: 'bg-amber-950/60',   border: 'border-amber-500/60',   text: 'text-amber-300',   icon: <RefreshCw className="w-4 h-4" />,     label: 'Reclassify' },
};

interface ReviewPanelProps {
  detectionId: string;
}

export const ReviewPanel: React.FC<ReviewPanelProps> = ({ detectionId }) => {
  const { detections, setDetectionReview } = useSurveyStore();
  const detection = detections.find((d) => d.id === detectionId);
  const existingReview = detection?.review ?? null;

  const [selectedOutcome, setSelectedOutcome] = useState<ReviewOutcome | null>(
    existingReview?.outcome ?? null
  );
  const [correctedClass, setCorrectedClass] = useState<string>(
    existingReview?.correctedClass ?? CLASS_OPTIONS[0].value
  );
  const [note, setNote] = useState<string>(existingReview?.note ?? '');
  const [navTrustworthy, setNavTrustworthy] = useState<boolean>(
    existingReview?.navTrustworthy ?? true
  );
  const [reviewedBy, setReviewedBy] = useState<string>(existingReview?.reviewedBy ?? 'operator');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isDirty =
    selectedOutcome !== null &&
    (selectedOutcome !== existingReview?.outcome ||
      (selectedOutcome === 'CORRECTED' && correctedClass !== existingReview?.correctedClass) ||
      note !== (existingReview?.note ?? '') ||
      navTrustworthy !== (existingReview?.navTrustworthy ?? true) ||
      reviewedBy !== (existingReview?.reviewedBy ?? 'operator'));

  const handleSubmit = async () => {
    if (!selectedOutcome) return;
    if (selectedOutcome === 'CORRECTED' && !correctedClass) return;
    setSaving(true);
    setError(null);
    try {
      await submitReview(detectionId, {
        outcome: selectedOutcome,
        corrected_class: selectedOutcome === 'CORRECTED' ? correctedClass : null,
        note: note.trim() || null,
        nav_trustworthy: navTrustworthy,
        reviewed_by: reviewedBy.trim() || 'operator',
      });
      setDetectionReview(detectionId, {
        outcome: selectedOutcome,
        correctedClass: selectedOutcome === 'CORRECTED' ? correctedClass : null,
        note: note.trim() || null,
        navTrustworthy,
        reviewedBy: reviewedBy.trim() || 'operator',
        reviewedAt: new Date().toISOString(),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save review');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    setError(null);
    try {
      await deleteReview(detectionId);
      setDetectionReview(detectionId, null);
      setSelectedOutcome(null);
      setNote('');
      setNavTrustworthy(true);
      setReviewedBy('operator');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clear review');
    } finally {
      setDeleting(false);
    }
  };

  const style = selectedOutcome ? OUTCOME_STYLES[selectedOutcome] : null;

  return (
    <div className="glass-panel rounded-xl p-4 mt-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-cyan-400" />
          <h3 className="font-heading font-bold text-sm text-white tracking-wide">
            OPERATOR REVIEW
          </h3>
          {existingReview && (
            <span
              className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${OUTCOME_STYLES[existingReview.outcome].bg} ${OUTCOME_STYLES[existingReview.outcome].border} ${OUTCOME_STYLES[existingReview.outcome].text}`}
            >
              {existingReview.outcome}
            </span>
          )}
        </div>

        {existingReview && (
          <button
            id={`review-delete-${detectionId}`}
            onClick={handleDelete}
            disabled={deleting}
            title="Clear review"
            className="flex items-center gap-1.5 px-2 py-1 rounded text-[11px] font-mono text-slate-400 hover:text-red-400 hover:bg-red-950/30 border border-transparent hover:border-red-800/40 transition-all"
          >
            {deleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
            <span>Clear</span>
          </button>
        )}
      </div>

      {/* Outcome selector */}
      <div className="grid grid-cols-3 gap-2">
        {(Object.entries(OUTCOME_STYLES) as [ReviewOutcome, typeof OUTCOME_STYLES[ReviewOutcome]][]).map(([outcome, s]) => (
          <button
            key={outcome}
            id={`review-outcome-${outcome.toLowerCase()}-${detectionId}`}
            onClick={() => setSelectedOutcome(outcome)}
            className={`flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg border text-xs font-mono font-bold transition-all ${
              selectedOutcome === outcome
                ? `${s.bg} ${s.border} ${s.text} shadow-[0_0_10px_rgba(0,0,0,0.3)]`
                : 'bg-slate-900/40 border-slate-800 text-slate-400 hover:border-slate-600 hover:text-slate-200'
            }`}
          >
            {s.icon}
            <span>{s.label}</span>
          </button>
        ))}
      </div>

      {/* Corrected class dropdown */}
      {selectedOutcome === 'CORRECTED' && (
        <div className="space-y-1.5">
          <label className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
            Corrected Classification
          </label>
          <select
            id={`review-corrected-class-${detectionId}`}
            value={correctedClass}
            onChange={(e) => setCorrectedClass(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs font-mono text-white focus:border-amber-500/60 focus:outline-none transition-colors"
          >
            {CLASS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      )}

      {/* Note textarea */}
      <div className="space-y-1.5">
        <label className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
          Operator Note
          <span className="ml-2 text-slate-600 normal-case">({note.length}/1000)</span>
        </label>
        <textarea
          id={`review-note-${detectionId}`}
          value={note}
          onChange={(e) => setNote(e.target.value.slice(0, 1000))}
          rows={2}
          placeholder="Optional note for the feedback dataset…"
          className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs font-mono text-slate-200 placeholder-slate-600 focus:border-cyan-500/60 focus:outline-none resize-none transition-colors"
        />
      </div>

      {/* Nav trustworthy + reviewed-by row */}
      <div className="flex items-center gap-4">
        {/* Nav attestation toggle */}
        <label
          id={`review-nav-label-${detectionId}`}
          className="flex items-center gap-2 cursor-pointer group flex-1"
        >
          <div
            onClick={() => setNavTrustworthy(!navTrustworthy)}
            className={`w-8 h-4.5 rounded-full border flex items-center transition-colors ${
              navTrustworthy
                ? 'bg-emerald-700/70 border-emerald-500/50'
                : 'bg-slate-800 border-slate-600'
            }`}
          >
            <div
              className={`w-3 h-3 rounded-full shadow transition-transform mx-0.5 ${
                navTrustworthy ? 'bg-emerald-300 translate-x-3.5' : 'bg-slate-400 translate-x-0'
              }`}
            />
          </div>
          <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-400 group-hover:text-slate-200 transition-colors">
            {navTrustworthy
              ? <><MapPin className="w-3 h-3 text-emerald-400" /><span>Nav location trusted</span></>
              : <><MapPinOff className="w-3 h-3 text-slate-500" /><span>Nav location doubtful</span></>}
          </div>
        </label>

        {/* Reviewed-by field */}
        <div className="flex items-center gap-2 flex-1">
          <label className="text-[10px] font-mono text-slate-500 whitespace-nowrap">Reviewed by</label>
          <input
            id={`review-reviewed-by-${detectionId}`}
            type="text"
            value={reviewedBy}
            onChange={(e) => setReviewedBy(e.target.value.slice(0, 128))}
            placeholder="operator"
            className="flex-1 px-2 py-1 rounded bg-slate-900 border border-slate-700 text-[11px] font-mono text-slate-200 placeholder-slate-600 focus:border-cyan-500/60 focus:outline-none transition-colors"
          />
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="text-[11px] font-mono text-red-400 bg-red-950/30 border border-red-800/40 rounded px-3 py-2">
          {error}
        </div>
      )}

      {/* Submit button */}
      <div className="flex justify-end pt-1">
        <button
          id={`review-submit-${detectionId}`}
          onClick={handleSubmit}
          disabled={!selectedOutcome || saving}
          className={`flex items-center gap-2 px-5 py-2 rounded-lg text-xs font-mono font-bold transition-all ${
            !selectedOutcome || saving
              ? 'bg-slate-800 border border-slate-700 text-slate-500 cursor-not-allowed'
              : style
              ? `${style.bg} ${style.border} border ${style.text} hover:brightness-110 active:scale-95`
              : ''
          }`}
        >
          {saving
            ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /><span>Saving…</span></>
            : <><CheckCircle2 className="w-3.5 h-3.5" /><span>{existingReview ? 'Update Review' : 'Save Review'}</span></>
          }
        </button>
      </div>
    </div>
  );
};
