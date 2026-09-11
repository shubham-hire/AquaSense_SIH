// 256-step RGBA Lookup Tables for Sonar Waterfall Canvas

export type SonarColormap = 'cobalt' | 'amber' | 'ironbow' | 'grayscale';

export function generateColormapLut(colormap: SonarColormap): Uint8ClampedArray {
  const lut = new Uint8ClampedArray(256 * 4);

  for (let i = 0; i < 256; i++) {
    const norm = i / 255;
    let r = 0, g = 0, b = 0;

    switch (colormap) {
      case 'cobalt': {
        // Deep ocean naval cobalt / cyan
        r = Math.min(255, norm * 25);
        g = Math.min(255, norm * 185 + 15);
        b = Math.min(255, norm * 255 + 40);
        break;
      }
      case 'amber': {
        // Traditional high-phosphor amber sonar
        r = Math.min(255, norm * 255 * 1.15);
        g = Math.min(255, norm * 190);
        b = Math.min(255, norm * 30);
        break;
      }
      case 'ironbow': {
        // Thermal ironbow (black -> purple -> red -> yellow -> white)
        if (norm < 0.25) {
          r = norm * 4 * 128;
          g = 0;
          b = norm * 4 * 128;
        } else if (norm < 0.5) {
          const t = (norm - 0.25) * 4;
          r = 128 + t * 127;
          g = 0;
          b = 128 - t * 128;
        } else if (norm < 0.75) {
          const t = (norm - 0.5) * 4;
          r = 255;
          g = t * 255;
          b = 0;
        } else {
          const t = (norm - 0.75) * 4;
          r = 255;
          g = 255;
          b = t * 255;
        }
        break;
      }
      case 'grayscale':
      default: {
        // Standard Hydrographic Monochrome
        const val = norm * 255;
        r = val;
        g = val;
        b = val;
        break;
      }
    }

    const idx = i * 4;
    lut[idx] = Math.round(r);
    lut[idx + 1] = Math.round(g);
    lut[idx + 2] = Math.round(b);
    lut[idx + 3] = 255; // Alpha
  }

  return lut;
}
