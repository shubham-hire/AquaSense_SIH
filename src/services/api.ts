import type { Detection, ReviewDecision, ReviewOutcome, SurveyMission, SurveyNavigation } from '../types';

/**
 * Local Vite development proxies `/api` to FastAPI. On Vercel, set
 * `VITE_API_BASE_URL` to the public origin of the separately deployed API.
 * It is a public URL, never a secret.
 */
const configuredApiBase = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/$/, '');
export const API_BASE = configuredApiBase || '/api';

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

/** Build a WebSocket URL without relying on Vercel to host the socket server. */
export function streamUrl(path: string): string {
  const configuredSocketBase = import.meta.env.VITE_WS_BASE_URL?.trim().replace(/\/$/, '');
  if (configuredSocketBase) return `${configuredSocketBase}${path}`;

  if (configuredApiBase) {
    const apiOrigin = new URL(configuredApiBase);
    apiOrigin.protocol = apiOrigin.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${apiOrigin.toString().replace(/\/$/, '')}${path}`;
  }

  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${protocol}://${window.location.host}${API_BASE}${path}`;
}

export interface BackendQcReport {
  status: 'PASS' | 'WARNING' | 'CORRUPTED';
  ping_count: number;
  dropout_ratio_percent: number;
  recommendations: string[];
}

interface IngestResponse {
  survey_id: string;
  qc_report: BackendQcReport;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), init);
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `Backend request failed (${response.status})`);
  }
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    throw new Error('The API endpoint returned an unexpected response. Set VITE_API_BASE_URL to your deployed AquaSense API on Vercel.');
  }
  return response.json() as Promise<T>;
}

/** Upload and process one mission through the offline-first FastAPI pipeline. */
export async function ingestAndProcessSurvey(surveyId: string, file: File): Promise<BackendQcReport> {
  const formData = new FormData();
  formData.append('file', file);
  const ingest = await request<IngestResponse>(`/v1/surveys/${encodeURIComponent(surveyId)}/ingest`, {
    method: 'POST', body: formData,
  });
  await request(`/v1/surveys/${encodeURIComponent(surveyId)}/process`, { method: 'POST' });
  return ingest.qc_report;
}

/** Convert the deliberate backend snake_case contract to the existing React domain model. */
export async function fetchSurveyDetections(surveyId: string): Promise<Detection[]> {
  const payload = await request<BackendDetection[]>(`/v1/surveys/${encodeURIComponent(surveyId)}/detections`);
  return payload.map(toFrontendDetection);
}

interface BackendSurvey {
  survey_id: string;
  name: string;
  created_at: string;
  detection_count: number;
  qc_report: BackendQcReport | null;
}

/** Restore persisted mission metadata after the browser or API restarts. */
export async function fetchPersistedSurveys(): Promise<SurveyMission[]> {
  const payload = await request<BackendSurvey[]>('/v1/surveys');
  return payload.map((survey) => ({
    id: survey.survey_id,
    codeName: `UPLOAD-${survey.survey_id}`,
    name: survey.name,
    vesselName: 'Not provided',
    vehicleType: 'Uploaded survey',
    areaSqKm: 0,
    swathWidthMeters: 0,
    status: 'Completed',
    startTime: survey.created_at,
    locationName: 'Navigation available per survey',
    centerCoordinates: [0, 0],
    trackPoints: [],
    frequencyKhz: 0,
    summaryMetrics: {
      totalPings: survey.qc_report?.ping_count ?? 0,
      candidateCount: survey.detection_count,
      verifiedCount: survey.detection_count,
      rejectedCount: 0,
      unlocatedCount: 0,
      uncalibratedCount: 0,
      lowQualityCount: 0,
      avgConfidencePercent: 0,
      precisionGainPercent: 0,
    },
  }));
}

interface BackendNavigationPoint {
  ping_index: number; timestamp: string | null; latitude: number; longitude: number;
  altitude_m: number | null; depth_m: number | null; heading_deg: number | null; speed_mps: number | null;
}

interface BackendSurveyNavigation {
  format: string; total_ping_count: number; valid_navigation_pings: number;
  map_center: [number, number] | null; track_points: BackendNavigationPoint[];
}

/** Invalid vendor fixes are excluded by the API before the map sees them. */
export async function fetchSurveyNavigation(surveyId: string): Promise<SurveyNavigation> {
  const payload = await request<BackendSurveyNavigation>(`/v1/surveys/${encodeURIComponent(surveyId)}/navigation`);
  return {
    status: payload.track_points.length > 0 ? 'ready' : 'unavailable',
    format: payload.format,
    totalPingCount: payload.total_ping_count,
    validNavigationPings: payload.valid_navigation_pings,
    mapCenter: payload.map_center,
    trackPoints: payload.track_points.map((point) => ({
      pingIndex: point.ping_index, timestamp: point.timestamp, latitude: point.latitude, longitude: point.longitude,
      altitudeMeters: point.altitude_m, depthMeters: point.depth_m, headingDeg: point.heading_deg, speedMps: point.speed_mps,
    })),
  };
}

export function toFrontendDetection(detection: BackendDetection): Detection {
  return {
    id: detection.id,
    surveyId: detection.survey_id,
    classification: detection.classification,
    classNameLabel: detection.classification.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()),
    confidencePercent: detection.confidence_percent,
    boundingBox: {
      x: detection.bounding_box.x,
      y: detection.bounding_box.y,
      widthM: detection.bounding_box.width_m,
      heightM: detection.bounding_box.height_m,
      imageBox: detection.bounding_box.image_box ?? null,
    },
    segmentationMask: detection.segmentation_mask,
    position: detection.position.position_source === 'GPS_FIX'
      ? { kind: 'located', lat: detection.position.latitude!, lng: detection.position.longitude! }
      : { kind: 'unlocated', reason: detection.position.refusal_reason ?? 'Navigation unavailable' },
    calibrated: detection.calibrated,
    lowDataQuality: detection.low_data_quality,
    motionUncorrected: detection.motion_uncorrected,
    experimental: null,
    threatLevel: detection.threat_level,
    rawDetectorLogit: 0,
    verificationFeatures: detection.verification_features,
    featureWeights: detection.feature_weights,
    pingTimestamp: detection.ping_timestamp,
    pingIndex: detection.ping_index,
    dspApplied: detection.dsp_applied,
    notes: `${detection.model_version} · ${detection.provenance.pipeline_version}`,
    review: detection.review
      ? {
          outcome: detection.review.outcome as ReviewOutcome,
          correctedClass: detection.review.corrected_class ?? null,
          note: detection.review.note ?? null,
          navTrustworthy: detection.review.nav_trustworthy,
          reviewedBy: detection.review.reviewed_by,
          reviewedAt: detection.review.reviewed_at,
        }
      : null,
  };
}

export interface BackendDetection {
  id: string; survey_id: string; classification: string; confidence_percent: number;
  bounding_box: {
    x: number; y: number; width_m: number; height_m: number;
    image_box?: { left: number; top: number; width: number; height: number } | null;
  };
  segmentation_mask: { type: 'polygon' | 'rle'; data: number[][] } | null;
  position: { latitude: number | null; longitude: number | null; position_source: 'GPS_FIX' | 'UNAVAILABLE'; refusal_reason: string | null };
  calibrated: boolean; low_data_quality: boolean; motion_uncorrected: boolean; model_version: string;
  dsp_applied: boolean; ping_timestamp: string; ping_index: number; threat_level: Detection['threatLevel'];
  verification_features: Detection['verificationFeatures']; feature_weights: Record<string, number>;
  provenance: { pipeline_version: string };
  review?: {
    outcome: string;
    corrected_class: string | null;
    note: string | null;
    nav_trustworthy: boolean;
    reviewed_by: string;
    reviewed_at: string;
  } | null;
}

/** Submit or overwrite an operator review for a single detection. */
export async function submitReview(
  detectionId: string,
  review: {
    outcome: 'CONFIRMED' | 'REJECTED_FP' | 'CORRECTED';
    corrected_class?: string | null;
    note?: string | null;
    nav_trustworthy: boolean;
    reviewed_by?: string;
  }
): Promise<{ ok: boolean; outcome: string }> {
  return request<{ ok: boolean; outcome: string }>(
    `/v1/detections/${encodeURIComponent(detectionId)}/review`,
    { method: 'PUT', body: JSON.stringify(review), headers: { 'Content-Type': 'application/json' } }
  );
}

/** Delete an operator review (returns detection to unreviewed state). */
export async function deleteReview(detectionId: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(
    `/v1/detections/${encodeURIComponent(detectionId)}/review`,
    { method: 'DELETE' }
  );
}

/** Backend-generated reports include the same refusal/provenance fields seen in the console. */
export function reportDownloadUrl(surveyId: string, format: 'json' | 'csv' | 'geojson' | 'pdf'): string {
  const base = apiUrl(`/v1/surveys/${encodeURIComponent(surveyId)}`);
  return format === 'geojson' ? `${base}/geojson` : `${base}/report.${format}`;
}

/** Normalized image artifact generated during XTF, JSF, or SL2 ingestion. */
export function waterfallImageUrl(surveyId: string): string {
  return apiUrl(`/v1/surveys/${encodeURIComponent(surveyId)}/waterfall.png`);
}
