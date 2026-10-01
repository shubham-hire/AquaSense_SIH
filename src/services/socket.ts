import { useEffect } from 'react';
import { useSurveyStore } from '../store/useSurveyStore';
import { fetchSurveyDetections, streamUrl, toFrontendDetection, type BackendDetection } from './api';

interface StreamMessage {
  event: string;
  [key: string]: unknown;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function parseStreamMessage(data: unknown): StreamMessage {
  if (typeof data !== 'string') {
    throw new Error('The live stream returned a non-text payload.');
  }

  const parsed: unknown = JSON.parse(data);
  if (!isRecord(parsed) || typeof parsed.event !== 'string' || !parsed.event.trim()) {
    throw new Error('The live stream payload is missing an event name.');
  }
  return parsed as StreamMessage;
}

function assertBackendDetection(value: unknown): asserts value is BackendDetection {
  if (!isRecord(value)) throw new Error('Detection data is missing.');

  const boundingBox = value.bounding_box;
  const position = value.position;
  const provenance = value.provenance;
  const hasCoreFields =
    typeof value.id === 'string' &&
    typeof value.survey_id === 'string' &&
    typeof value.classification === 'string' &&
    isFiniteNumber(value.confidence_percent) &&
    typeof value.calibrated === 'boolean' &&
    typeof value.low_data_quality === 'boolean' &&
    typeof value.motion_uncorrected === 'boolean' &&
    typeof value.model_version === 'string' &&
    typeof value.dsp_applied === 'boolean' &&
    typeof value.ping_timestamp === 'string' &&
    isFiniteNumber(value.ping_index);
  const hasBoundingBox =
    isRecord(boundingBox) &&
    isFiniteNumber(boundingBox.x) &&
    isFiniteNumber(boundingBox.y) &&
    isFiniteNumber(boundingBox.width_m) &&
    isFiniteNumber(boundingBox.height_m);
  const hasPosition =
    isRecord(position) &&
    (position.position_source === 'GPS_FIX' || position.position_source === 'UNAVAILABLE') &&
    (position.position_source !== 'GPS_FIX' ||
      (isFiniteNumber(position.latitude) && isFiniteNumber(position.longitude)));
  const hasProvenance = isRecord(provenance) && typeof provenance.pipeline_version === 'string';

  if (!hasCoreFields || !hasBoundingBox || !hasPosition || !hasProvenance) {
    throw new Error('Detection data does not match the expected format.');
  }
}

function errorDetail(reason: unknown): string {
  return reason instanceof Error && reason.message.trim() ? ` ${reason.message}` : '';
}

/**
 * Subscribes to FastAPI's live pipeline stream. Each verified candidate updates the
 * map, twin and queue before the mission's full processing run completes.
 */
export function useLiveDetectionSocket() {
  const {
    isLiveStreaming,
    addStreamedDetection,
    activeSurveyId,
    replaceSurveyDetections,
    setIsLiveStreaming,
    setProcessingError,
  } = useSurveyStore();

  useEffect(() => {
    if (!isLiveStreaming) return undefined;

    let deliberatelyClosed = false;
    let terminalEventReceived = false;
    let socket: WebSocket;

    const stopWithError = (message: string) => {
      if (deliberatelyClosed || terminalEventReceived) return;
      terminalEventReceived = true;
      setProcessingError(message);
    };

    try {
      socket = new WebSocket(streamUrl(`/v1/surveys/${encodeURIComponent(activeSurveyId)}/stream`));
    } catch (reason) {
      stopWithError(`Unable to open the live processing stream.${errorDetail(reason)}`);
      return undefined;
    }

    socket.onmessage = async ({ data }) => {
      if (deliberatelyClosed || terminalEventReceived) return;

      let message: StreamMessage;
      try {
        message = parseStreamMessage(data);
      } catch (reason) {
        stopWithError(`The live processing stream sent an invalid message.${errorDetail(reason)}`);
        return;
      }

      if (message.event === 'detection.verified') {
        try {
          assertBackendDetection(message.data);
          addStreamedDetection(toFrontendDetection(message.data));
        } catch (reason) {
          stopWithError(`The live processing stream sent an invalid detection.${errorDetail(reason)}`);
        }
        return;
      }

      if (message.event === 'processing.failed') {
        const detail = typeof message.detail === 'string' && message.detail.trim()
          ? ` ${message.detail.trim()}`
          : ' The backend did not provide further details.';
        stopWithError(`Survey processing failed.${detail}`);
        return;
      }

      if (message.event === 'processing.complete') {
        terminalEventReceived = true;
        setIsLiveStreaming(false);
        try {
          const persisted = await fetchSurveyDetections(activeSurveyId);
          replaceSurveyDetections(activeSurveyId, persisted);
        } catch (reason) {
          setProcessingError(`Processing completed, but the saved detections could not be loaded.${errorDetail(reason)}`);
        }
      }
    };

    socket.onerror = () => {
      stopWithError('The live processing stream encountered a connection error. Check the backend connection and try again.');
    };

    socket.onclose = (event) => {
      if (deliberatelyClosed || terminalEventReceived) return;
      const reason = event.reason.trim() ? ` ${event.reason.trim()}` : '';
      stopWithError(`The live processing stream closed before processing finished.${reason}`);
    };

    return () => {
      deliberatelyClosed = true;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
      if (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN) {
        socket.close(1000, 'Client cleanup');
      }
    };
  }, [
    isLiveStreaming,
    activeSurveyId,
    addStreamedDetection,
    replaceSurveyDetections,
    setIsLiveStreaming,
    setProcessingError,
  ]);
}
