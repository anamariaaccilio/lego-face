import * as THREE from 'three';

export const COLOR = {
  amarillo: '#F2CD37',
  rojo: '#C91A09',
  azul: '#0055BF',
  azulOscuro: '#0A3463',
  naranja: '#FE8A18',
  verde: '#237841',
  blanco: '#F4F4F4',
  negro: '#1B2A34',
  grisClaro: '#A0A5A9',
  grisOscuro: '#6C6E68',
  marron: '#583927',
  beige: '#E4CD9E',
};

// Lado cilíndrico de la cabeza: el lienzo cubre toda la vuelta (2πr) y la altura recta.
export const CABEZA = { r: 0.5, h: 0.82, bisel: 0.08 };
const ALTO_LADO = CABEZA.h - 2 * CABEZA.bisel;
export const LIENZO_CARA = { w: 1024, h: Math.round((1024 * ALTO_LADO) / (2 * Math.PI * CABEZA.r)) };

function lienzo(w, h) {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  return c;
}

function textura(canvas, renderer) {
  const t = new THREE.CanvasTexture(canvas);
  t.colorSpace = THREE.SRGBColorSpace;
  if (renderer) t.anisotropy = renderer.capabilities.getMaxAnisotropy();
  return t;
}

const cajas = new WeakMap();

/** Rectángulo donde la estampa tiene rasgos (alfa > 0). Las estampas traen mucho margen vacío. */
function cajaRasgos(img) {
  if (cajas.has(img)) return cajas.get(img);
  const W = img.naturalWidth || img.width;
  const H = img.naturalHeight || img.height;
  const c = lienzo(W, H);
  const g = c.getContext('2d');
  g.drawImage(img, 0, 0);
  const d = g.getImageData(0, 0, W, H).data;
  let x0 = W, y0 = H, x1 = -1, y1 = -1;
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      if (d[(y * W + x) * 4 + 3] > 40) {
        if (x < x0) x0 = x;
        if (x > x1) x1 = x;
        if (y < y0) y0 = y;
        if (y > y1) y1 = y;
      }
    }
  }
  const caja = x1 < 0 ? { x: 0, y: 0, w: W, h: H } : { x: x0, y: y0, w: x1 - x0 + 1, h: y1 - y0 + 1 };
  cajas.set(img, caja);
  return caja;
}

/**
 * Cara generada (RGBA, alfa 0 = piel) puesta al frente de la cabeza.
 * Se recorta a sus rasgos y se agranda hasta llenar ~85 % del alto de la cara,
 * sin pasar de ~105° de la vuelta para que no se doble hacia los costados.
 */
export function texturaCaraImagen(img, renderer) {
  const { w, h } = LIENZO_CARA;
  const c = lienzo(w, h);
  const g = c.getContext('2d');
  g.fillStyle = COLOR.amarillo;
  g.fillRect(0, 0, w, h);
  if (img) {
    const k = cajaRasgos(img);
    const escala = Math.min((h * 0.86) / k.h, (w * 0.29) / k.w);
    const dw = k.w * escala;
    const dh = k.h * escala;
    g.imageSmoothingQuality = 'high';
    g.drawImage(img, k.x, k.y, k.w, k.h, w / 2 - dw / 2, h / 2 - dh / 2, dw, dh);
  }
  return textura(c, renderer);
}

/** Cara de Tito, dibujada a mano. boca: 'sonrisa' | 'abierta'. */
export function texturaCaraTito(boca, renderer) {
  const { w, h } = LIENZO_CARA;
  const c = lienzo(w, h);
  const g = c.getContext('2d');
  g.fillStyle = COLOR.amarillo;
  g.fillRect(0, 0, w, h);
  const cx = w / 2;
  const cy = h / 2;
  g.fillStyle = COLOR.negro;
  g.strokeStyle = COLOR.negro;
  g.lineCap = 'round';
  // cejas
  g.lineWidth = 9;
  for (const s of [-1, 1]) {
    g.beginPath();
    g.moveTo(cx + s * 26, cy - 52);
    g.quadraticCurveTo(cx + s * 44, cy - 62, cx + s * 64, cy - 54);
    g.stroke();
  }
  // ojos con brillo
  for (const s of [-1, 1]) {
    g.beginPath();
    g.ellipse(cx + s * 45, cy - 16, 13, 17, 0, 0, Math.PI * 2);
    g.fillStyle = COLOR.negro;
    g.fill();
    g.beginPath();
    g.arc(cx + s * 45 + 4, cy - 22, 4.5, 0, Math.PI * 2);
    g.fillStyle = '#fff';
    g.fill();
  }
  g.fillStyle = COLOR.negro;
  if (boca === 'abierta') {
    g.beginPath();
    g.moveTo(cx - 40, cy + 26);
    g.quadraticCurveTo(cx, cy + 86, cx + 40, cy + 26);
    g.closePath();
    g.fill();
    g.beginPath();
    g.ellipse(cx, cy + 52, 18, 9, 0, 0, Math.PI * 2);
    g.fillStyle = '#B5372B';
    g.fill();
  } else {
    g.lineWidth = 9;
    g.beginPath();
    g.moveTo(cx - 48, cy + 26);
    g.quadraticCurveTo(cx, cy + 66, cx + 48, cy + 26);
    g.stroke();
  }
  return textura(c, renderer);
}

/** Frente del torso de Tito: overol con bolsillo y gafete. */
export function texturaTorsoTito(renderer) {
  const c = lienzo(256, 256);
  const g = c.getContext('2d');
  g.fillStyle = COLOR.blanco;
  g.fillRect(0, 0, 256, 256);
  // overol
  g.fillStyle = COLOR.azul;
  g.fillRect(40, 120, 176, 136);
  g.fillRect(48, 0, 34, 130);
  g.fillRect(174, 0, 34, 130);
  g.fillStyle = COLOR.amarillo;
  for (const x of [65, 191]) {
    g.beginPath();
    g.arc(x, 112, 9, 0, Math.PI * 2);
    g.fill();
  }
  // bolsillo
  g.strokeStyle = COLOR.azulOscuro;
  g.lineWidth = 5;
  g.strokeRect(96, 150, 64, 50);
  // gafete
  g.fillStyle = '#fff';
  g.fillRect(150, 34, 62, 30);
  g.fillStyle = COLOR.rojo;
  g.fillRect(150, 34, 62, 9);
  g.fillStyle = COLOR.negro;
  g.font = 'bold 17px Fredoka, sans-serif';
  g.textAlign = 'center';
  g.fillText('TITO', 181, 61);
  return textura(c, renderer);
}

/** Banda transportadora, se repite y se desplaza. */
export function texturaBanda(renderer) {
  const c = lienzo(128, 128);
  const g = c.getContext('2d');
  g.fillStyle = '#2b2f33';
  g.fillRect(0, 0, 128, 128);
  g.fillStyle = '#363b40';
  for (let x = 0; x < 128; x += 32) g.fillRect(x, 0, 14, 128);
  const t = textura(c, renderer);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}

/** Franjas de advertencia amarillo y negro. */
export function texturaFranjas(renderer) {
  const c = lienzo(128, 32);
  const g = c.getContext('2d');
  g.fillStyle = COLOR.amarillo;
  g.fillRect(0, 0, 128, 32);
  g.fillStyle = COLOR.negro;
  for (let x = -32; x < 160; x += 32) {
    g.beginPath();
    g.moveTo(x, 32);
    g.lineTo(x + 16, 32);
    g.lineTo(x + 32, 0);
    g.lineTo(x + 16, 0);
    g.closePath();
    g.fill();
  }
  const t = textura(c, renderer);
  t.wrapS = THREE.RepeatWrapping;
  return t;
}

/** Letrero de la pared. */
export function texturaLetrero(texto, renderer, fondo = COLOR.rojo) {
  const c = lienzo(1024, 192);
  const g = c.getContext('2d');
  g.fillStyle = fondo;
  g.fillRect(0, 0, 1024, 192);
  g.fillStyle = COLOR.amarillo;
  g.fillRect(0, 0, 1024, 14);
  g.fillRect(0, 178, 1024, 14);
  g.fillStyle = '#fff';
  g.font = '600 104px Fredoka, sans-serif';
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.fillText(texto, 512, 102);
  return textura(c, renderer);
}

/** Pared de ladrillos. */
export function texturaPared(renderer) {
  const c = lienzo(512, 256);
  const g = c.getContext('2d');
  g.fillStyle = '#d9d2c3';
  g.fillRect(0, 0, 512, 256);
  const alto = 32;
  for (let fila = 0; fila < 8; fila++) {
    const desf = fila % 2 ? 64 : 0;
    for (let x = -desf; x < 512; x += 128) {
      g.fillStyle = fila % 3 === 0 ? '#e3dccd' : '#ddd5c5';
      g.fillRect(x + 3, fila * alto + 3, 122, alto - 6);
    }
  }
  const t = textura(c, renderer);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}
