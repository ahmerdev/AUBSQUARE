import * as THREE from 'three';

export const BRAND = {
  bg: '#0B0B12',
  magenta: '#EC008C',
  purple: '#7B2FFF',
  violet: '#9333EA',
  lavender: '#C99BFF',
};

/** Soft round sprite used for particles / bokeh (avoids the default square points). */
export const makeSoftDot = () => {
  const size = 64;
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const g = c.getContext('2d')!;
  const grad = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  grad.addColorStop(0, 'rgba(255,255,255,1)');
  grad.addColorStop(0.35, 'rgba(255,255,255,0.55)');
  grad.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grad;
  g.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
};

export const roundedRectShape = (w: number, h: number, r: number) => {
  const s = new THREE.Shape();
  const x = -w / 2;
  const y = -h / 2;
  s.moveTo(x + r, y);
  s.lineTo(x + w - r, y);
  s.quadraticCurveTo(x + w, y, x + w, y + r);
  s.lineTo(x + w, y + h - r);
  s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  s.lineTo(x + r, y + h);
  s.quadraticCurveTo(x, y + h, x, y + h - r);
  s.lineTo(x, y + r);
  s.quadraticCurveTo(x, y, x + r, y);
  return s;
};

/** The AUB SQUARE brand motif: a bevelled rounded-square frame. */
export const makeSquareFrame = (outer = 3.2, inner = 2.46, depth = 0.34, radius = 0.6, curveSegments = 14) => {
  const shape = roundedRectShape(outer, outer, radius);
  shape.holes.push(roundedRectShape(inner, inner, Math.max(0.12, radius - (outer - inner) / 2 + 0.1)));
  const geo = new THREE.ExtrudeGeometry(shape, {
    depth,
    bevelEnabled: true,
    bevelThickness: 0.07,
    bevelSize: 0.06,
    bevelSegments: 4,
    curveSegments,
  });
  geo.translate(0, 0, -depth / 2);
  geo.computeVertexNormals();
  return geo;
};

/** Magenta → violet → purple → magenta light palette sampled by page progress. */
const STOPS = [new THREE.Color(BRAND.magenta), new THREE.Color(BRAND.violet), new THREE.Color(BRAND.purple), new THREE.Color('#D11AA0')];
export const sampleStops = (t: number, out: THREE.Color, reverse = false) => {
  const n = STOPS.length - 1;
  const v = Math.min(0.9999, Math.max(0, reverse ? 1 - t : t)) * n;
  const i = Math.floor(v);
  return out.lerpColors(STOPS[i], STOPS[i + 1], v - i);
};
