import React, { useEffect, useRef, useState } from 'react';
import { AlertCircle, LoaderCircle, ScanLine } from 'lucide-react';
import { useSurveyStore } from '../../store/useSurveyStore';
import { generateColormapLut } from '../../utils/colormaps';

export type WaterfallStatus = 'loading' | 'ready' | 'unavailable' | 'error';

interface WaterfallCanvasProps {
  width?: number;
  height?: number;
  sourceUrl?: string;
  onCanvasClick?: (e: React.MouseEvent<HTMLCanvasElement>) => void;
  onStatusChange?: (status: WaterfallStatus) => void;
}

/** Displays the source waterfall; palette and DSP recolor browser pixels only. */
export const WaterfallCanvas: React.FC<WaterfallCanvasProps> = ({
  width = 640,
  height = 420,
  sourceUrl,
  onCanvasClick,
  onStatusChange,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const { waterfallPalette, dspFilterActive } = useSurveyStore();
  const [sourceImage, setSourceImage] = useState<HTMLImageElement | null>(null);
  const [status, setStatus] = useState<WaterfallStatus>(sourceUrl ? 'loading' : 'unavailable');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sourceUrl) {
      setSourceImage(null);
      setStatus('unavailable');
      setError(null);
      return;
    }
    let disposed = false;
    const image = new Image();
    image.crossOrigin = 'anonymous';
    setSourceImage(null);
    setStatus('loading');
    setError(null);
    image.onload = () => {
      if (!disposed) {
        setSourceImage(image);
        setStatus('ready');
      }
    };
    image.onerror = () => {
      if (!disposed) {
        setStatus('error');
        setError('The backend did not provide an extracted waterfall for this survey.');
      }
    };
    image.src = sourceUrl;
    return () => { disposed = true; };
  }, [sourceUrl]);

  useEffect(() => {
    onStatusChange?.(status);
  }, [onStatusChange, status]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !sourceImage) return;
    const context = canvas.getContext('2d');
    if (!context) return;

    context.drawImage(sourceImage, 0, 0, width, height);
    try {
      const imageData = context.getImageData(0, 0, width, height);
      const lut = generateColormapLut(waterfallPalette);
      for (let pixel = 0; pixel < imageData.data.length; pixel += 4) {
        let intensity = (imageData.data[pixel] + imageData.data[pixel + 1] + imageData.data[pixel + 2]) / 3;
        if (dspFilterActive) intensity = Math.min(255, Math.pow(intensity / 255, 1.25) * 280);
        const lutIndex = Math.max(0, Math.min(255, Math.floor(intensity))) * 4;
        imageData.data[pixel] = lut[lutIndex];
        imageData.data[pixel + 1] = lut[lutIndex + 1];
        imageData.data[pixel + 2] = lut[lutIndex + 2];
      }
      context.putImageData(imageData, 0, 0);
    } catch {
      // Keep the unmodified source visible if a host blocks canvas readback.
    }
    context.strokeStyle = 'rgba(34, 211, 238, 0.4)';
    context.setLineDash([4, 4]);
    context.beginPath();
    context.moveTo(width / 2, 0);
    context.lineTo(width / 2, height);
    context.stroke();
    context.setLineDash([]);
  }, [dspFilterActive, height, sourceImage, waterfallPalette, width]);

  const heading = status === 'loading' ? 'Loading extracted waterfall…' : status === 'error' ? 'Waterfall unavailable' : 'No extracted sonar image';

  return (
    <div className="relative h-full w-full">
      <canvas ref={canvasRef} width={width} height={height} onClick={onCanvasClick} className="h-full w-full cursor-crosshair rounded-lg border border-slate-700/80 shadow-inner" aria-label="Extracted sonar waterfall" />
      {status !== 'ready' && <div className="absolute inset-0 grid place-items-center bg-slate-950/80 p-4 text-center">
        <div className="max-w-xs rounded-lg border border-slate-700 bg-slate-950/90 p-3">
          {status === 'loading' ? <LoaderCircle className="mx-auto mb-2 h-5 w-5 animate-spin text-cyan-300" aria-hidden="true" /> : status === 'error' ? <AlertCircle className="mx-auto mb-2 h-5 w-5 text-rose-300" aria-hidden="true" /> : <ScanLine className="mx-auto mb-2 h-5 w-5 text-amber-300" aria-hidden="true" />}
          <p className="text-xs font-semibold text-slate-100">{heading}</p>
          <p className="mt-1 text-[11px] leading-relaxed text-slate-400" role={status === 'error' ? 'alert' : undefined}>{error ?? 'Upload and ingest an XTF, JSF, or SL2 survey to inspect its real sonar return.'}</p>
        </div>
      </div>}
    </div>
  );
};
