import React, { useEffect, useRef } from 'react';
import { useSurveyStore } from '../../store/useSurveyStore';
import { Image as ImageIcon, ScanLine } from 'lucide-react';

interface Props {
  className?: string;
}

const THREAT_COLORS: Record<string, string> = {
  CRITICAL: '#f87171',
  HIGH: '#fb923c',
  MEDIUM: '#facc15',
  LOW: '#34d399',
};

/**
 * Displays the locally-uploaded image with bounding-box overlays drawn from
 * the pipeline's detection results. Requires no backend round-trip for the
 * image — it reads the blob URL stored during upload.
 */
export const DetectionImageViewer: React.FC<Props> = ({ className = '' }) => {
  const { uploadedImageUrl, detections, activeSurveyId } = useSurveyStore();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const surveyDetections = detections.filter((d) => d.surveyId === activeSurveyId);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !uploadedImageUrl) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const img = new Image();
    img.src = uploadedImageUrl;
    img.onload = () => {
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      ctx.drawImage(img, 0, 0);

      // Draw each detection's bounding box
      surveyDetections.forEach((det) => {
        const color = THREAT_COLORS[det.threatLevel] ?? '#67e8f9';
        const imageBox = det.boundingBox.imageBox;
        // ``widthM`` / ``heightM`` are real-world measurements, not pixels.
        // The API provides source-image-relative geometry so the overlay stays
        // correct regardless of the preview's CSS size or image resolution.
        if (!imageBox) return;
        const x = imageBox.left * img.naturalWidth;
        const y = imageBox.top * img.naturalHeight;
        const bw = imageBox.width * img.naturalWidth;
        const bh = imageBox.height * img.naturalHeight;

        // Box
        ctx.strokeStyle = color;
        ctx.lineWidth = Math.max(2, img.naturalWidth / 300);
        ctx.strokeRect(x, y, bw, bh);

        // Filled semi-transparent background for label
        const labelText = `${det.confidencePercent}% ${det.classNameLabel}`;
        const fontSize = Math.max(12, img.naturalWidth / 60);
        ctx.font = `bold ${fontSize}px monospace`;
        const textWidth = ctx.measureText(labelText).width;
        const labelHeight = fontSize * 1.6;
        const labelY = y - labelHeight < 0 ? y + bh : y - labelHeight;

        ctx.fillStyle = color + 'cc';
        ctx.fillRect(x, labelY, textWidth + 10, labelHeight);

        // Label text
        ctx.fillStyle = '#000';
        ctx.fillText(labelText, x + 5, labelY + fontSize * 1.2);

        // Segmentation polygon if available
        if (det.segmentationMask?.type === 'polygon' && det.segmentationMask.data.length > 0) {
          ctx.beginPath();
          const pts = det.segmentationMask.data;
          ctx.moveTo(pts[0][0], pts[0][1]);
          pts.slice(1).forEach(([px, py]) => ctx.lineTo(px, py));
          ctx.closePath();
          ctx.fillStyle = color + '33';
          ctx.fill();
          ctx.strokeStyle = color;
          ctx.lineWidth = Math.max(1.5, img.naturalWidth / 400);
          ctx.stroke();
        }
      });
    };
  }, [uploadedImageUrl, surveyDetections]);

  if (!uploadedImageUrl) {
    return (
      <div className={`flex flex-col glass-panel rounded-xl overflow-hidden p-3 gap-2.5 ${className}`}>
        <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
          <ImageIcon className="w-4 h-4 text-cyan-400" />
          <h3 className="font-heading font-bold text-sm text-white tracking-wide">UPLOADED IMAGE</h3>
        </div>
        <div className="flex-1 min-h-[340px] rounded-lg bg-black/80 flex flex-col items-center justify-center gap-3 text-center p-6">
          <ScanLine className="w-8 h-8 text-slate-600" />
          <p className="text-xs font-mono text-slate-500">No image uploaded yet.<br />Upload a PNG or JPG to see AI detections here.</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex flex-col glass-panel rounded-xl overflow-hidden p-3 gap-2.5 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2">
          <ImageIcon className="w-4 h-4 text-cyan-400" />
          <h3 className="font-heading font-bold text-sm text-white tracking-wide">UPLOADED IMAGE</h3>
          <span className="text-[10px] font-mono text-slate-400 bg-slate-900 border border-slate-700 px-1.5 py-0.5 rounded">
            {surveyDetections.length} DETECTIONS
          </span>
        </div>
      </div>

      {/* Canvas with bounding boxes */}
      <div className="relative flex-1 min-h-[340px] rounded-lg overflow-hidden bg-black/90">
        <canvas
          ref={canvasRef}
          className="h-full w-full object-contain"
          aria-label="Uploaded image with detection bounding boxes"
        />
        {surveyDetections.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="bg-slate-950/80 rounded-lg border border-slate-700 p-3 text-center max-w-xs">
              <ScanLine className="w-5 h-5 text-amber-400 mx-auto mb-1.5" />
              <p className="text-xs font-mono text-slate-300">Processing… detections will appear here.</p>
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      {surveyDetections.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(THREAT_COLORS).map(([level, color]) => (
            <div key={level} className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-sm border" style={{ backgroundColor: color + '55', borderColor: color }} />
              <span className="text-[10px] font-mono text-slate-400">{level}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
