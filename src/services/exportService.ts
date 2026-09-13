import { Detection, SurveyMission } from '../types';

/**
 * Generates PS 26057 compliant structured JSON report (PRD §11)
 */
export function generateReportJson(survey: SurveyMission, detections: Detection[]): string {
  const records = detections.map((d) => ({
    detection_id: d.id,
    latitude: d.position.kind === 'located' ? d.position.lat : null,
    longitude: d.position.kind === 'located' ? d.position.lng : null,
    classification: d.classification,
    confidence_percent: d.confidencePercent, // Integer 0–100% per PS
    bounding_box: {
      x: d.boundingBox.x,
      y: d.boundingBox.y,
      width_m: d.boundingBox.widthM,
      height_m: d.boundingBox.heightM,
    },
    segmentation_mask: d.segmentationMask
      ? { type: d.segmentationMask.type, points: d.segmentationMask.data }
      : null,
    position_source: d.position.kind === 'located' ? 'GPS_FIX' : 'UNAVAILABLE',
    low_data_quality: d.lowDataQuality,
    motion_uncorrected: d.motionUncorrected,
    calibrated: d.calibrated,
    survey_id: survey.id,
    ping_timestamp: d.pingTimestamp,
    review: d.review
      ? {
          outcome: d.review.outcome,
          corrected_class: d.review.correctedClass ?? null,
          note: d.review.note ?? null,
          nav_trustworthy: d.review.navTrustworthy,
          reviewed_by: d.review.reviewedBy,
          reviewed_at: d.review.reviewedAt,
        }
      : null,
  }));

  const payload = {
    report_metadata: {
      generator: 'AquaSense MoES / NIOT SIH 2026 PS 26057',
      survey_id: survey.id,
      survey_name: survey.name,
      vessel: survey.vesselName,
      generated_at: new Date().toISOString(),
      total_detections: detections.length,
      unlocated_refusal_count: detections.filter((d) => d.position.kind === 'unlocated').length,
    },
    detections: records,
  };

  return JSON.stringify(payload, null, 2);
}

/**
 * Generates PS 26057 compliant structured CSV report (PRD §11)
 */
export function generateReportCsv(survey: SurveyMission, detections: Detection[]): string {
  const headers = [
    'detection_id',
    'latitude',
    'longitude',
    'classification',
    'confidence_percent',
    'width_m',
    'height_m',
    'has_segmentation_mask',
    'position_source',
    'low_data_quality',
    'calibrated',
    'threat_level',
    'survey_id',
    'ping_timestamp',
    // Review columns
    'review_outcome',
    'corrected_class',
    'nav_trustworthy',
    'operator_note',
    'reviewed_at',
    'reviewed_by',
  ];

  const rows = detections.map((d) => [
    d.id,
    d.position.kind === 'located' ? d.position.lat.toFixed(6) : 'NULL',
    d.position.kind === 'located' ? d.position.lng.toFixed(6) : 'NULL',
    d.classification,
    d.confidencePercent,
    d.boundingBox.widthM.toFixed(2),
    d.boundingBox.heightM.toFixed(2),
    d.segmentationMask ? 'TRUE' : 'FALSE',
    d.position.kind === 'located' ? 'GPS_FIX' : 'UNAVAILABLE',
    d.lowDataQuality ? 'TRUE' : 'FALSE',
    d.calibrated ? 'TRUE' : 'FALSE',
    d.threatLevel,
    survey.id,
    d.pingTimestamp,
    // Review columns
    d.review?.outcome ?? '',
    d.review?.correctedClass ?? '',
    d.review != null ? String(d.review.navTrustworthy) : '',
    d.review?.note ?? '',
    d.review?.reviewedAt ?? '',
    d.review?.reviewedBy ?? '',
  ]);

  return [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
}

/**
 * Generates standard GeoJSON FeatureCollection
 */
export function generateGeoJson(survey: SurveyMission, detections: Detection[]): string {
  const features = detections
    .filter((d): d is Detection & { position: { kind: 'located'; lat: number; lng: number } } => d.position.kind === 'located')
    .map((d) => ({
      type: 'Feature' as const,
      geometry: {
        type: 'Point' as const,
        coordinates: [d.position.lng, d.position.lat],
      },
      properties: {
        id: d.id,
        classification: d.classification,
        label: d.classNameLabel,
        confidencePercent: d.confidencePercent,
        threatLevel: d.threatLevel,
        widthM: d.boundingBox.widthM,
        heightM: d.boundingBox.heightM,
        hasMask: !!d.segmentationMask,
        calibrated: d.calibrated,
        lowDataQuality: d.lowDataQuality,
        surveyId: survey.id,
        review_outcome: d.review?.outcome ?? null,
        corrected_class: d.review?.correctedClass ?? null,
        nav_trustworthy: d.review?.navTrustworthy ?? null,
      },
    }));

  return JSON.stringify(
    {
      type: 'FeatureCollection',
      name: `AquaSense_${survey.id}_Spatial_Hazards`,
      features,
    },
    null,
    2
  );
}

/**
 * Helper to download text file
 */
export function downloadFile(content: string, fileName: string, contentType: string) {
  const blob = new Blob([content], { type: contentType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
