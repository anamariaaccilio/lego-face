import * as THREE from 'three';
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js';
import { Cabeza } from './escena/minifig.js';

async function escenaCabeza(renderer, img, peinado) {
  const scene = new THREE.Scene();
  const c = new Cabeza(renderer);
  c.ponerImagen(img);
  await c.ponerCabello(peinado);
  scene.add(c.grupo);
  return { scene, cabeza: c };
}

/** Render de la cabeza (con su cabello) con fondo transparente, como PNG. */
export async function imagenCabeza(img, peinado = null, lado = 900) {
  const r = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  r.setSize(lado, lado);
  r.toneMapping = THREE.ACESFilmicToneMapping;
  const { scene } = await escenaCabeza(r, img, peinado);
  scene.add(new THREE.HemisphereLight('#ffffff', '#8a8f99', 1.6));
  const luz = new THREE.DirectionalLight('#ffffff', 2.2);
  luz.position.set(2, 3, 4);
  scene.add(luz);
  const cam = new THREE.PerspectiveCamera(30, 1, 0.1, 20);
  cam.position.set(1.0, 1.35, 3.4);
  cam.lookAt(0, peinado ? 0.75 : 0.6, 0);
  r.render(scene, cam);
  const url = r.domElement.toDataURL('image/png');
  r.dispose();
  return url;
}

/** Cabeza como archivo .glb con la cara y el cabello incluidos. */
export async function glbCabeza(img, peinado = null) {
  const r = new THREE.WebGLRenderer();
  const { scene } = await escenaCabeza(r, img, peinado);
  const datos = await new GLTFExporter().parseAsync(scene, { binary: true });
  r.dispose();
  return new Blob([datos], { type: 'model/gltf-binary' });
}

export function descargar(origen, nombre) {
  const url = origen instanceof Blob ? URL.createObjectURL(origen) : origen;
  const a = document.createElement('a');
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  if (origen instanceof Blob) setTimeout(() => URL.revokeObjectURL(url), 2000);
}
