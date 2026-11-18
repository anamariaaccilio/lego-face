import * as THREE from 'three';
import { construirFabrica } from './fabrica.js';
import { Minifig } from './minifig.js';
import { COLOR } from './texturas.js';

/**
 * Vistas de cámara por estación.
 * mira: punto que se centra. dist/alto: distancia y altura de la cámara. ancho: lo que debe caber a lo ancho.
 * corrX: corre el encuadre en x cuando hay un panel lateral (fracción del ancho visible).
 */
const VISTAS = {
  recepcion: { mira: [0, 2.9, 0], dist: 14.5, alto: 1.6, ancho: 9.5, corrX: 0 },
  foto: { mira: [-7, 2.45, -1.9], dist: 6.4, alto: 0.15, ancho: 5.4, corrX: 0 },
  asesoria: { mira: [-15, 3.0, -0.6], dist: 11.5, alto: 1.2, ancho: 8.5, corrX: 0.2 },
  maquina: { mira: [7.6, 2.3, 0.4], dist: 14, alto: 3.2, ancho: 12, corrX: 0.2, lado: -2.6 },
  fabricando: { mira: [8.6, 2.0, 0], dist: 13.5, alto: 2.4, ancho: 13.5, corrX: 0 },
  control: { mira: [17.2, 1.2, 0], dist: 9.6, alto: 1.1, ancho: 8.6, corrX: 0 },
  resumen: { mira: [0, 2.9, 0], dist: 14.5, alto: 1.6, ancho: 9.5, corrX: 0.22 },
};

const POS_TITO = {
  recepcion: [1.5, 0.9],
  foto: [-4.2, 0.7],
  asesoria: [-11.3, 1.3],
  maquina: [5.3, 1.6],
  fabricando: [5.3, 1.8],
  control: [12.9, 1.9],
  resumen: [1.5, 0.9],
};

export class Mundo {
  constructor(contenedor) {
    const r = new THREE.WebGLRenderer({ antialias: true });
    r.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    r.shadowMap.enabled = true;
    r.shadowMap.type = THREE.PCFSoftShadowMap;
    r.toneMapping = THREE.ACESFilmicToneMapping;
    r.toneMappingExposure = 1.05;
    contenedor.appendChild(r.domElement);
    this.renderer = r;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#cfd8e0');
    scene.fog = new THREE.Fog('#cfd8e0', 22, 46);
    this.scene = scene;

    this.camara = new THREE.PerspectiveCamera(34, 1, 0.1, 120);
    scene.add(new THREE.HemisphereLight('#fff6e8', '#7b8794', 1.4));
    const sol = new THREE.DirectionalLight('#fff1db', 2.4);
    sol.position.set(4, 14, 9);
    sol.target.position.set(6, 0, 0);
    sol.castShadow = true;
    sol.shadow.mapSize.set(2048, 2048);
    Object.assign(sol.shadow.camera, { left: -24, right: 18, top: 9, bottom: -9, near: 1, far: 40 });
    sol.shadow.bias = -0.0004;
    sol.shadow.normalBias = 0.02;
    scene.add(sol, sol.target);

    const f = construirFabrica(scene, r);
    this.cabina = f.cabina;
    this.oficina = f.oficina;
    this.linea = f.linea;
    this.control = f.control;

    this.tito = new Minifig(r, { torsoColor: COLOR.blanco, piernas: COLOR.azul, brazos: COLOR.azul, tito: true });
    this.tito.ponerEn(...POS_TITO.recepcion);
    scene.add(this.tito.raiz);

    this.mira = new THREE.Vector3();
    this.miraObj = new THREE.Vector3();
    this.posObj = new THREE.Vector3();
    this.vista = 'recepcion';
    this.panelLateral = false;
    this._calcular(true);

    this.reloj = new THREE.Clock();
    this.t = 0;
    this.alActualizar = [];
    this.raycaster = new THREE.Raycaster();
    window.addEventListener('resize', () => this.redimensionar());
    this.redimensionar();
    r.setAnimationLoop(() => this._cuadro());
  }

  redimensionar() {
    const el = this.renderer.domElement.parentElement;
    const w = el.clientWidth;
    const h = el.clientHeight;
    this.renderer.setSize(w, h);
    this.camara.aspect = w / h;
    this.camara.updateProjectionMatrix();
    this._calcular(false);
  }

  /** Mueve la cámara a una estación y manda a Tito a su puesto. */
  irA(vista, { tito = true, panelLateral = false } = {}) {
    this.vista = vista;
    this.panelLateral = panelLateral && window.innerWidth > 860;
    this._calcular(false);
    if (tito) return this.tito.caminarA(...POS_TITO[vista]);
    return Promise.resolve();
  }

  _calcular(inmediato) {
    const v = VISTAS[this.vista];
    const tanMedio = Math.tan(THREE.MathUtils.degToRad(this.camara.fov / 2));
    const dist = Math.max(v.dist, v.ancho / (2 * tanMedio * this.camara.aspect));
    const anchoVisible = 2 * tanMedio * dist * this.camara.aspect;
    const corr = this.panelLateral ? anchoVisible * v.corrX : 0;
    this.miraObj.set(v.mira[0] + corr, v.mira[1], v.mira[2]);
    this.posObj.set(v.mira[0] + corr + (v.lado || 0), v.mira[1] + v.alto, v.mira[2] + dist);
    if (inmediato) {
      this.mira.copy(this.miraObj);
      this.camara.position.copy(this.posObj);
    }
  }

  _cuadro() {
    const dt = Math.min(this.reloj.getDelta(), 0.05);
    this.t += dt;
    const k = 1 - Math.exp(-dt * 2.6);
    this.camara.position.lerp(this.posObj, k);
    this.mira.lerp(this.miraObj, k);
    // leve vaivén para que la escena respire
    const vaiven = new THREE.Vector3(Math.sin(this.t * 0.35) * 0.08, Math.sin(this.t * 0.5) * 0.05, 0);
    this.camara.lookAt(this.mira.clone().add(vaiven));
    // la neblina sigue a la cámara, así una vista lejana (celular vertical) no se lava
    const d = this.camara.position.distanceTo(this.mira);
    this.scene.fog.near = d + 8;
    this.scene.fog.far = d + 32;

    this.tito.update(dt, this.camara);
    this.cabina.update(dt);
    this.oficina.update(dt);
    this.linea.update(dt, this.t);
    this.control.update(dt, this.t);
    for (const fn of this.alActualizar) fn(dt);
    this.renderer.render(this.scene, this.camara);
  }

  /** Posición en pantalla (px) de un punto del mundo; null si queda detrás de la cámara. */
  enPantalla(p) {
    const v = p.clone().project(this.camara);
    if (v.z > 1) return null;
    const el = this.renderer.domElement;
    return { x: ((v.x + 1) / 2) * el.clientWidth, y: ((1 - v.y) / 2) * el.clientHeight };
  }

  /** Índice del puesto de control bajo el puntero, o null. */
  puestoBajo(ev) {
    const el = this.renderer.domElement;
    const rect = el.getBoundingClientRect();
    const p = new THREE.Vector2(((ev.clientX - rect.left) / rect.width) * 2 - 1, -((ev.clientY - rect.top) / rect.height) * 2 + 1);
    this.raycaster.setFromCamera(p, this.camara);
    const hit = this.raycaster.intersectObjects(this.control.objetivos(), true)[0];
    return hit ? hit.object.userData.puesto ?? null : null;
  }
}
