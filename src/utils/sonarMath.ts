// DSP and Mathematical Formulas from PRD v1.1 and Reuse Extraction Guide

/**
 * Calculates the Quadrature Error Budget for a geolocated sonar contact.
 * sigma_pos = sqrt(sigma_GPS^2 + sigma_cross^2 + sigma_range^2 + sigma_alt^2)
 */
export function calculateErrorBudget(
  slantRangeM: number,
  groundRangeM: number,
  altitudeM: number,
  sigmaGpsM = 1.2,
  sigmaHeadingDeg = 1.5,
  sigmaAltitudeM = 0.4
) {
  const headingRad = (sigmaHeadingDeg * Math.PI) / 180;
  const sigmaCrossTrack = groundRangeM * Math.sin(headingRad);
  const sigmaRange = 0.03 * slantRangeM + 0.2;
  const sigmaAltitude = sigmaAltitudeM;
  const sigmaGps = sigmaGpsM;

  const varianceTotal =
    sigmaGps * sigmaGps +
    sigmaCrossTrack * sigmaCrossTrack +
    sigmaRange * sigmaRange +
    sigmaAltitude * sigmaAltitude;

  const sigmaPosTotal = Math.sqrt(varianceTotal);

  return {
    sigmaGps: Number(sigmaGps.toFixed(2)),
    sigmaCrossTrack: Number(sigmaCrossTrack.toFixed(2)),
    sigmaRange: Number(sigmaRange.toFixed(2)),
    sigmaAltitude: Number(sigmaAltitude.toFixed(2)),
    sigmaPosTotal: Number(sigmaPosTotal.toFixed(2)),
  };
}

/**
 * Calculates acoustic shadow height inversion.
 * H_target = (H_altitude * L_shadow) / (R_slant + L_shadow)
 * Returns null when shadow or altitude cannot be validated (Refusal invariant).
 */
export function invertShadowHeight(
  altitudeM: number | null | undefined,
  slantRangeM: number | null | undefined,
  shadowLengthM: number | null | undefined
): number | null {
  if (
    altitudeM == null ||
    slantRangeM == null ||
    shadowLengthM == null ||
    altitudeM <= 0 ||
    slantRangeM <= 0 ||
    shadowLengthM <= 0
  ) {
    return null; // Refusal invariant: refuse rather than fabricate
  }

  const height = (altitudeM * shadowLengthM) / (slantRangeM + shadowLengthM);
  return Number(height.toFixed(2));
}

/**
 * Slant-to-ground range correction.
 * Y_ground = sqrt(R_slant^2 - H_altitude^2)
 */
export function slantToGroundRange(
  slantRangeM: number,
  altitudeM: number
): number {
  if (slantRangeM <= altitudeM) return 0;
  return Number(Math.sqrt(slantRangeM * slantRangeM - altitudeM * altitudeM).toFixed(2));
}

/**
 * Inverted shadow length formula for synthetic ghost-gear generation.
 * L_shadow = (H_target * R_slant) / (H_altitude - H_target)
 */
export function calculateSyntheticShadowLength(
  targetHeightM: number,
  slantRangeM: number,
  altitudeM: number
): number {
  const deltaAlt = altitudeM - targetHeightM;
  if (deltaAlt <= 0.05) return slantRangeM * 2;
  return Number(((targetHeightM * slantRangeM) / deltaAlt).toFixed(2));
}

/**
 * Circular heading interpolation avoiding the 0°/360° wraparound bug.
 * Delta h = ((h1 - h0 + 180) % 360) - 180
 */
export function interpolateHeading(h0: number, h1: number, t: number): number {
  const diff = (((h1 - h0 + 180) % 360 + 360) % 360) - 180;
  const interpolated = (h0 + diff * t + 360) % 360;
  return Number(interpolated.toFixed(1));
}
