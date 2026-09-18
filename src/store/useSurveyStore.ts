import { create } from 'zustand';
import { Detection, PriorityLevel, ReviewDecision, SurveyMission, SurveyNavigation } from '../types';
import { SonarColormap } from '../utils/colormaps';

/** Default survey ID used when no file has been uploaded yet. */
export const DEFAULT_SURVEY_ID = 'SURVEY-NEW';

interface SurveyState {
  mode: 'operator' | 'executive';
  setMode: (mode: 'operator' | 'executive') => void;
  surveys: SurveyMission[];
  activeSurveyId: string;
  detections: Detection[];
  selectedDetectionId: string | null;
  ensureSurvey: (survey: SurveyMission) => void;
  setActiveSurveyId: (id: string) => void;
  setSelectedDetectionId: (id: string | null) => void;
  waterfallPalette: SonarColormap;
  setWaterfallPalette: (palette: SonarColormap) => void;
  dspFilterActive: boolean;
  setDspFilterActive: (active: boolean) => void;
  isLiveStreaming: boolean;
  setIsLiveStreaming: (streaming: boolean) => void;
  streamedDetections: Detection[];
  addStreamedDetection: (detection: Detection) => void;
  replaceSurveyDetections: (surveyId: string, detections: Detection[]) => void;
  resetStream: () => void;
  confidenceThreshold: number;
  setConfidenceThreshold: (val: number) => void;
  filterClass: string;
  setFilterClass: (cls: string) => void;
  filterPriority: PriorityLevel | 'ALL';
  setFilterPriority: (pri: PriorityLevel | 'ALL') => void;
  showOnlyRefused: boolean;
  setShowOnlyRefused: (val: boolean) => void;
  setDetectionReview: (detectionId: string, review: ReviewDecision | null) => void;
  navigationBySurvey: Record<string, SurveyNavigation | undefined>;
  setSurveyNavigation: (surveyId: string, navigation: SurveyNavigation) => void;
  /** Local blob URL of the uploaded image/file for preview with bounding boxes. */
  uploadedImageUrl: string | null;
  setUploadedImageUrl: (url: string | null) => void;
}

function updateMissionMetrics(mission: SurveyMission, detections: Detection[]): SurveyMission {
  const count = detections.length;
  return {
    ...mission,
    status: 'Completed',
    summaryMetrics: {
      ...mission.summaryMetrics,
      candidateCount: count,
      verifiedCount: count,
      rejectedCount: 0,
      unlocatedCount: detections.filter((item) => item.position.kind === 'unlocated').length,
      uncalibratedCount: detections.filter((item) => !item.calibrated).length,
      lowQualityCount: detections.filter((item) => item.lowDataQuality).length,
      avgConfidencePercent: count
        ? Math.round(detections.reduce((sum, item) => sum + item.confidencePercent, 0) / count)
        : 0,
    },
  };
}

export const useSurveyStore = create<SurveyState>((set, get) => ({
  mode: 'operator',
  setMode: (mode) => set({ mode }),

  surveys: [],
  activeSurveyId: DEFAULT_SURVEY_ID,
  detections: [],
  selectedDetectionId: null,

  ensureSurvey: (survey) =>
    set((state) => ({
      surveys: state.surveys.some((item) => item.id === survey.id)
        ? state.surveys
        : [...state.surveys, survey],
      activeSurveyId: survey.id,
    })),
  setActiveSurveyId: (id) => {
    const matched = get().detections.filter((d) => d.surveyId === id);
    set({ activeSurveyId: id, selectedDetectionId: matched[0]?.id ?? null });
  },
  setSelectedDetectionId: (id) => set({ selectedDetectionId: id }),

  waterfallPalette: 'amber',
  setWaterfallPalette: (waterfallPalette) => set({ waterfallPalette }),
  dspFilterActive: false,
  setDspFilterActive: (dspFilterActive) => set({ dspFilterActive }),

  isLiveStreaming: false,
  setIsLiveStreaming: (isLiveStreaming) => set({ isLiveStreaming }),
  // Live results must start empty; demo records must never appear as model output.
  streamedDetections: [],

  addStreamedDetection: (detection) =>
    set((state) => {
      if (state.streamedDetections.some((item) => item.id === detection.id)) return state;
      return {
        streamedDetections: [...state.streamedDetections, detection],
        detections: state.detections.some((item) => item.id === detection.id)
          ? state.detections
          : [...state.detections, detection],
      };
    }),

  replaceSurveyDetections: (surveyId, incoming) =>
    set((state) => ({
      detections: [...state.detections.filter((item) => item.surveyId !== surveyId), ...incoming],
      streamedDetections: [
        ...state.streamedDetections.filter((item) => item.surveyId !== surveyId),
        ...incoming,
      ],
      selectedDetectionId: incoming[0]?.id ?? null,
      surveys: state.surveys.map((mission) =>
        mission.id === surveyId ? updateMissionMetrics(mission, incoming) : mission
      ),
    })),

  resetStream: () => set({ streamedDetections: [], isLiveStreaming: false }),

  // The backend already applies its configured 10% inference threshold. Matching
  // that value prevents valid low-confidence candidates from being hidden by default.
  confidenceThreshold: 10,
  setConfidenceThreshold: (confidenceThreshold) => set({ confidenceThreshold }),
  filterClass: 'ALL',
  setFilterClass: (filterClass) => set({ filterClass }),
  filterPriority: 'ALL',
  setFilterPriority: (filterPriority) => set({ filterPriority }),
  showOnlyRefused: false,
  setShowOnlyRefused: (showOnlyRefused) => set({ showOnlyRefused }),

  setDetectionReview: (detectionId, review) =>
    set((state) => ({
      detections: state.detections.map((item) =>
        item.id === detectionId ? { ...item, review } : item
      ),
    })),

  navigationBySurvey: {},
  setSurveyNavigation: (surveyId, navigation) =>
    set((state) => ({
      navigationBySurvey: { ...state.navigationBySurvey, [surveyId]: navigation },
    })),

  uploadedImageUrl: null,
  setUploadedImageUrl: (uploadedImageUrl) => set({ uploadedImageUrl }),
}));
