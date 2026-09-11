import React, { useRef, useEffect } from 'react';
import { useSurveyStore } from '../../store/useSurveyStore';
import { generateColormapLut } from '../../utils/colormaps';

interface WaterfallCanvasProps {
  width?: number;
  height?: number;
  onCanvasClick?: (e: React.MouseEvent<HTMLCanvasElement>) => void;
}

export const WaterfallCanvas: React.FC<WaterfallCanvasProps> = ({
  width = 640,
  height = 420,
  onCanvasClick,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const { waterfallPalette, dspFilterActive, isLiveStreaming } = useSurveyStore();

  // Ping buffer reference (N rows of width floats)
  const bufferRef = useRef<Float32Array[]>([]);
  const animationFrameRef = useRef<number | null>(null);

  // Initialize buffer with realistic side-scan profile
  useEffect(() => {
    const rows = height;
    const initialBuffer: Float32Array[] = [];

    for (let y = 0; y < rows; y++) {
      const row = new Float32Array(width);
      for (let x = 0; x < width; x++) {
        const centerDist = Math.abs(x - width / 2);
        if (centerDist < 25) {
          // Nadir water column gap
          row[x] = Math.random() * 15;
        } else if (centerDist >= 25 && centerDist < 35) {
          // Sharp first seabed reflection
          row[x] = 180 + Math.random() * 50;
        } else {
          // Seabed reverberation + target features
          let val = 85 + Math.random() * 45;
          // Target 1: ghost net highlight & shadow
          if (centerDist > 110 && centerDist < 135 && y > 120 && y < 170) {
            val = 240 + Math.random() * 15; // highlight
          } else if (centerDist >= 135 && centerDist < 175 && y > 120 && y < 170) {
            val = 8 + Math.random() * 8; // shadow
          }
          // Target 2: cylinder highlight & shadow
          if (centerDist > 190 && centerDist < 205 && y > 260 && y < 290) {
            val = 250 + Math.random() * 5;
          } else if (centerDist >= 205 && centerDist < 235 && y > 260 && y < 290) {
            val = 4 + Math.random() * 5;
          }
          row[x] = val;
        }
      }
      initialBuffer.push(row);
    }
    bufferRef.current = initialBuffer;
  }, [width, height]);

  // Render loop using colormap LUT
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const lut = generateColormapLut(waterfallPalette);
    const imgData = ctx.createImageData(width, height);
    const data = imgData.data;

    const render = () => {
      // If live streaming, shift new ping into buffer
      if (isLiveStreaming && bufferRef.current.length > 0) {
        const newRow = new Float32Array(width);
        for (let x = 0; x < width; x++) {
          const centerDist = Math.abs(x - width / 2);
          if (centerDist < 25) {
            newRow[x] = Math.random() * 15;
          } else if (centerDist >= 25 && centerDist < 35) {
            newRow[x] = 180 + Math.random() * 50;
          } else {
            newRow[x] = 85 + Math.random() * 45;
          }
        }
        bufferRef.current.pop();
        bufferRef.current.unshift(newRow);
      }

      // Draw rows to imageData
      const buffer = bufferRef.current;
      for (let y = 0; y < height; y++) {
        const row = buffer[y] || buffer[0];
        if (!row) continue;

        for (let x = 0; x < width; x++) {
          let intensity = row[x];

          // Apply DSP contrast enhancement for visualization if toggled
          if (dspFilterActive) {
            intensity = Math.min(255, Math.pow(intensity / 255, 1.25) * 280);
          }

          const lutIdx = Math.max(0, Math.min(255, Math.floor(intensity))) * 4;
          const pixelIdx = (y * width + x) * 4;

          data[pixelIdx] = lut[lutIdx];
          data[pixelIdx + 1] = lut[lutIdx + 1];
          data[pixelIdx + 2] = lut[lutIdx + 2];
          data[pixelIdx + 3] = 255;
        }
      }

      ctx.putImageData(imgData, 0, 0);

      // Nadir center line overlay
      ctx.strokeStyle = 'rgba(34, 211, 238, 0.4)';
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(width / 2, 0);
      ctx.lineTo(width / 2, height);
      ctx.stroke();
      ctx.setLineDash([]);

      animationFrameRef.current = requestAnimationFrame(render);
    };

    animationFrameRef.current = requestAnimationFrame(render);

    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    };
  }, [width, height, waterfallPalette, dspFilterActive, isLiveStreaming]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      onClick={onCanvasClick}
      className="w-full h-full object-cover rounded-lg border border-slate-700/80 cursor-crosshair shadow-inner"
    />
  );
};
