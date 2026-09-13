import { useEffect } from 'react';
import { useSurveyStore } from '../store/useSurveyStore';
import { fetchSurveyDetections, streamUrl, toFrontendDetection, type BackendDetection } from './api';

/**
 * Subscribes to FastAPI's live pipeline stream. Each verified candidate updates the
 * map, twin and queue before the mission's full processing run completes.
 */
export function useLiveDetectionSocket() {
  const { isLiveStreaming, addStreamedDetection, activeSurveyId, replaceSurveyDetections, setIsLiveStreaming } = useSurveyStore();

  useEffect(() => {
    if (!isLiveStreaming) return;
    const socket = new WebSocket(streamUrl(`/v1/surveys/${encodeURIComponent(activeSurveyId)}/stream`));
    socket.onmessage = async ({ data }) => {
      const message = JSON.parse(data);
      if (message.event === 'detection.verified') {
        addStreamedDetection(toFrontendDetection(message.data as BackendDetection));
      }
      if (message.event === 'processing.complete') {
        const persisted = await fetchSurveyDetections(activeSurveyId);
        replaceSurveyDetections(activeSurveyId, persisted);
        setIsLiveStreaming(false);
      }
    };
    return () => socket.close();
  }, [isLiveStreaming, activeSurveyId, addStreamedDetection, replaceSurveyDetections, setIsLiveStreaming]);
}
