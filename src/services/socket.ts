import { useEffect, useRef } from 'react';
import { useSurveyStore } from '../store/useSurveyStore';
import { MOCK_DETECTIONS } from '../data/mockDetections';

/**
 * Hook simulating the native WebSocket client for live detection streaming (§5).
 * Drops detections in real time as they clear verification, preventing drift between
 * the Waterfall Canvas, Digital Twin, Detection Queue, and Live Map.
 */
export function useLiveDetectionSocket() {
  const { isLiveStreaming, addStreamedDetection, activeSurveyId } = useSurveyStore();
  const currentIndexRef = useRef(3);

  useEffect(() => {
    if (!isLiveStreaming) return;

    const interval = setInterval(() => {
      const remaining = MOCK_DETECTIONS.filter(
        (d) => d.surveyId === activeSurveyId
      );

      if (currentIndexRef.current < remaining.length) {
        const nextDetection = remaining[currentIndexRef.current];
        addStreamedDetection(nextDetection);
        currentIndexRef.current += 1;
      } else {
        // Loop or finish
        clearInterval(interval);
      }
    }, 2800);

    return () => clearInterval(interval);
  }, [isLiveStreaming, activeSurveyId, addStreamedDetection]);
}
