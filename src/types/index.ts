// Domain Types for AquaSense (PRD v1.1 and Frontend Architecture Compliant)

export type PriorityLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

export type ReviewOutcome = 'CONFIRMED' | 'REJECTED_FP' | 'CORRECTED';

export interface ReviewDecision {
  outcome: ReviewOutcome;
  correctedClass?: string | null;   // only when outcome === 'CORRECTED'
  note?: string | null;             // operator free-text (max 1000 chars)
  navTrustworthy: boolean;          // operator nav attestation
  reviewedBy: string;               // operator identifier
  reviewedAt: string;               // ISO datetime
}

export type PositionStatus =
  | { kind: 'located'; lat: number; lng: number }
  | { kind: 'unlocated'; reason: string };

export type DetectionClass =
  | 'entangled_net'
  | 'shipwreck'
  | 'pipeline_anomaly'
  | 'cylinder_drum'
  | 'unexploded_ordnance'
  | 'marine_debris'
  | 'subsea_cable'
  | 'biological_cluster'
  | 'geological_formation';

export interface BoundingBox {
  x: number;          // normalized centre X, retained for map/mission use
  y: number;          // normalized centre Y, retained for map/mission use
  widthM: number;     // Real-world width in meters (PS-required)
  heightM: number;    // Real-world height in meters (PS-required)
  /** Normalized source-image box for exact image overlays. */
  imageBox?: { left: number; top: number; width: number; height: number } | null;
}

export interface ContourPoint {
  x: number;
  y: number;
}

export interface AcousticShadow {
  lengthMeters: number;
  angleDeg: number;
  shadowRatio: number;
  estimatedHeightMeters: number | null; // null if occluded (refusal invariant)
}

export interface VerificationFeatures {
  targetContrast: number;
  shadowRatio: number;
  shadowSideConsistent: boolean;
  highlightCompactness: number;
  edgeStraightness: number;
  textureHomogeneity: number;
  backgroundRoughness: number;
  localSnr: number;
  sizeRank: number;
  aspectRatio: number;
}

export interface Detection {
  id: string;
  surveyId: string;
  classification: DetectionClass | string;
  classNameLabel: string;
  confidencePercent: number;          // Integer 0–100% (PS-required format, never raw float)
  boundingBox: BoundingBox;
  segmentationMask: { type: 'polygon' | 'rle'; data: number[][] } | null; // §8.1a polygon mask
  position: PositionStatus;           // Structural refusal invariant
  calibrated: boolean;                // Platt calibration status (§8.3)
  lowDataQuality: boolean;            // Sensor/motion problem flag (§9.2)
  motionUncorrected: boolean;         // Missing motion telemetry flag (§9.2)
  experimental: { note: string } | null; // Synthetic ghost-gear flag (§7.2)
  threatLevel: PriorityLevel;
  rawDetectorLogit: number;
  acousticShadow?: AcousticShadow;
  errorBudget?: {
    sigmaGps: number;
    sigmaCrossTrack: number;
    sigmaRange: number;
    sigmaAltitude: number;
    sigmaPosTotal: number;
  };
  verificationFeatures?: VerificationFeatures;
  featureWeights?: Record<string, number>;
  cropUrl?: string;
  pingTimestamp: string;
  pingIndex: number;
  dspApplied: boolean;
  notes?: string;
  rejectionReason?: string;
  /** Operator review — undefined/null when not yet reviewed. */
  review?: ReviewDecision | null;
}

export interface TrackPoint {
  latitude: number;
  longitude: number;
  depthMeters: number;
  altitudeMeters: number;
  headingDeg: number;
  speedKnots: number;
  pingIndex: number;
  timestamp: string;
}

/** Navigation supplied by an ingested sonar file; never fabricated from demo data. */
export interface ExtractedTrackPoint {
  pingIndex: number;
  timestamp: string | null;
  latitude: number;
  longitude: number;
  altitudeMeters: number | null;
  depthMeters: number | null;
  headingDeg: number | null;
  speedMps: number | null;
}

export interface SurveyNavigation {
  status: 'loading' | 'ready' | 'unavailable' | 'error';
  format?: string;
  totalPingCount?: number;
  validNavigationPings?: number;
  mapCenter: [number, number] | null;
  trackPoints: ExtractedTrackPoint[];
  error?: string;
}

export interface SurveyMission {
  id: string;
  codeName: string;
  name: string;
  vesselName: string;
  vehicleType: string;
  areaSqKm: number;
  swathWidthMeters: number;
  status: 'Active' | 'Completed' | 'Processing';
  startTime: string;
  endTime?: string;
  locationName: string;
  centerCoordinates: [number, number];
  trackPoints: TrackPoint[];
  frequencyKhz: number;
  summaryMetrics: {
    totalPings: number;
    candidateCount: number;
    verifiedCount: number;
    rejectedCount: number;
    unlocatedCount: number;
    uncalibratedCount: number;
    lowQualityCount: number;
    avgConfidencePercent: number;
    precisionGainPercent: number;
  };
}

export interface QcReport {
  surveyId: string;
  timestamp: string;
  fileName: string;
  fileSizeBytes: number;
  format: 'XTF' | 'JSF' | 'SL2' | 'GeoTIFF' | 'PNG/JPG';
  pingCount: number;
  swathRangeMeters: number;
  nadirBlindZoneMeters: number;
  dynamicRangeDb: number;
  speckleIndex: number;
  dropoutRatioPercent: number;
  motionArtifactRows: number[];
  resolutionMetersPerPixel: number;
  status: 'PASS' | 'WARNING' | 'CORRUPTED';
  recommendations: string[];
}

export interface AblationRecord {
  id: string;
  component: string;
  category: 'Preprocessing' | 'Architecture' | 'Split Protocol';
  baselineConfig: string;
  testedConfig: string;
  baselineMetric: string;
  testedMetric: string;
  baselineValue: number;
  testedValue: number;
  deltaPercent: number;
  decision: 'KILLED_FOR_DETECTION' | 'RETAINED_HONESTLY' | 'ADOPTED';
  caption: string;
}

export interface ModelCheckpoint {
  id: string;
  name: string;
  architecture: string;
  calibrated: boolean;
  plattScalingSplit: string;
  splitProtocol: string;
  mAP50: number;
  verifiedStatus: string;
  lastVerifiedDate: string;
}
