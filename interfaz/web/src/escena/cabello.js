import * as THREE from 'three';
import { toCreasedNormals } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { CABEZA } from './texturas.js';

/**
 * Piezas de cabello de LDraw (CC BY 2.0, ver public/cabello/CREDITOS.txt), convertidas a triángulos
 * con interfaz/herramientas/ldraw_a_json.py. En LDraw la cabeza y el cabello comparten origen: la cara
 * superior de la cabeza, con -Y hacia arriba y la cara mirando a -Z. 12 LDU = radio de la cabeza.
 */
export const COLORES_CABELLO = [
  { id: 'negro', nombre: 'Negro', hex: '#1b1b1f' },
  { id: 'castaño', nombre: 'Castaño', hex: '#5c3a21' },
  { id: 'rubio', nombre: 'Rubio', hex: '#e2bd5b' },
  { id: 'pelirrojo', nombre: 'Pelirrojo', hex: '#b9471f' },
  { id: 'gris', nombre: 'Gris', hex: '#8f9396' },
  { id: 'blanco', nombre: 'Blanco', hex: '#ecebe6' },
  { id: 'rosa', nombre: 'Rosa', hex: '#ee7fb5' },
  { id: 'azul', nombre: 'Azul', hex: '#2f6fd6' },
  { id: 'morado', nombre: 'Morado', hex: '#7d4bb3' },
  { id: 'verde', nombre: 'Verde', hex: '#3e9b53' },
];
export const hexDe = (color) => COLORES_CABELLO.find((c) => c.id === color)?.hex || '#5c3a21';

let catalogo = null;
const geometrias = new Map();

export function cargarCatalogo() {
  catalogo ??= fetch('/cabello/catalogo.json').then((r) => r.json());
  return catalogo;
}

export function geometriaCabello(id) {
  if (!geometrias.has(id)) {
    geometrias.set(id, fetch(`/cabello/${id}.json`).then((r) => r.json()).then(({ pos }) => {
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
      // las piezas vienen en facetas: se suavizan las curvas y se respetan los quiebres marcados
      return toCreasedNormals(g, THREE.MathUtils.degToRad(35));
    }));
  }
  return geometrias.get(id);
}

/** Malla lista para colgar del grupo de una Cabeza (origen en la base del cuello). */
export function mallaCabello(geo, color) {
  const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: hexDe(color), roughness: 0.38, side: THREE.DoubleSide }));
  m.rotation.x = Math.PI; // -Y de LDraw hacia arriba y la cara hacia +Z
  m.scale.setScalar(CABEZA.r / 12);
  // cara superior de la cabeza, un poco más arriba: la cara impresa llena casi todo el alto y el flequillo tapaba las cejas
  m.position.y = 0.12 + CABEZA.h + 0.07;
  m.castShadow = true;
  m.receiveShadow = true;
  m.name = 'cabello';
  return m;
}
