import { create } from 'zustand';
import { Detection, PriorityLevel, SurveyMission } from '../types';
import { MOCK_SURVEYS } from '../data/mockSurveys';
import { MOCK_DETECTIONS } from '../data/mockDetections';
import { SonarColormap } from '../utils/colormaps';

interface SurveyState {
  // Navigation & View Mode
  mode: 'operator' | 'executive';
  setMode: (mode: 'operator' | 'executive') => void;

  // Active Survey & Detections
  surveys: SurveyMission[];
  activeSurveyId: string;
  detections: Detection[];
  selectedDetectionId: string | null;
  setActiveSurveyId: (id: string) => void;
  setSelectedDetectionId: (id: string | null) => void;

  // Waterfall Controls
  waterfallPalette: SonarColormap;
  setWaterfallPalette: (palette: SonarColormap) => void;
  dspFilterActive: boolean;
  setDspFilterActive: (active: boolean) => void;

  // Live Processing Simulation
  isLiveStreaming: boolean;
  setIsLiveStreaming: (streaming: boolean) => void;
  streamedDetections: Detection[];
  addStreamedDetection: (detection: Detection) => void;
  replaceSurveyDetections: (surveyId: string, detections: Detection[]) => void;
  resetStream: () => void;

  // Operator Thresholds & Filters
  confidenceThreshold: number; // 0 to 100
  setConfidenceThreshold: (val: number) => void;
  filterClass: string;
  setFilterClass: (cls: string) => void;
  filterPriority: PriorityLevel | 'ALL';
  setFilterPriority: (pri: PriorityLevel | 'ALL') => void;
  showOnlyRefused: boolean;
  setShowOnlyRefused: (val: boolean) => void;
}

export const useSurveyStore = create<SurveyState>((set, get) => ({
  mode: 'operator',
  setMode: (mode) => set({ mode }),

  surveys: MOCK_SURVEYS,
  activeSurveyId: MOCK_SURVEYS[0].id,
  detections: MOCK_DETECTIONS,
  selectedDetectionId: MOCK_DETECTIONS[0].id,

  setActiveSurveyId: (id) => {
    const matched = get().detections.filter((d) => d.surveyId === id);
    set({
      activeSurveyId: id,
      selectedDetectionId: matched.length > 0 ? matched[0].id : null,
    });
  },

  setSelectedDetectionId: (id) => set({ selectedDetectionId: id }),

  waterfallPalette: 'amber',
  setWaterfallPalette: (waterfallPalette) => set({ waterfallPalette }),

  dspFilterActive: false,
  setDspFilterActive: (dspFilterActive) => set({ dspFilterActive }),

  isLiveStreaming: false,
  setIsLiveStreaming: (isLiveStreaming) => set({ isLiveStreaming }),
  streamedDetections: MOCK_DETECTIONS.slice(0, 3), // Start with first few, append during stream

  addStreamedDetection: (detection) =>
    set((state) => {
      // Prevent duplicates
      if (state.streamedDetections.some((d) => d.id === detection.id)) return state;
      return {
        streamedDetections: [...state.streamedDetections, detection],
        detections: state.detections.some((d) => d.id === detection.id)
          ? state.detections
          : [...state.detections, detection],
      };
    }),

  replaceSurveyDetections: (surveyId, incoming) =>
    set((state) => ({
      detections: [...state.detections.filter((d) => d.surveyId !== surveyId), ...incoming],
      streamedDetections: [...state.streamedDetections.filter((d) => d.surveyId !== surveyId), ...incoming],
      selectedDetectionId: incoming[0]?.id ?? null,
    })),

  resetStream: () =>
    set({
      streamedDetections: MOCK_DETECTIONS.slice(0, 3),
      isLiveStreaming: false,
    }),

  confidenceThreshold: 50,
  setConfidenceThreshold: (confidenceThreshold) => set({ confidenceThreshold }),

  filterClass: 'ALL',
  setFilterClass: (filterClass) => set({ filterClass }),

  filterPriority: 'ALL',
  setFilterPriority: (filterPriority) => set({ filterPriority }),

  showOnlyRefused: false,
  setShowOnlyRefused: (showOnlyRefused) => set({ showOnlyRefused }),
}));
