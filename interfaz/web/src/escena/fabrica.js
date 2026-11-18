import * as THREE from 'three';
import { Cabeza } from './minifig.js';
import { COLOR, texturaBanda, texturaFranjas, texturaLetrero, texturaPared } from './texturas.js';

const plastico = (color, extra = {}) =>
  new THREE.MeshStandardMaterial({ color, roughness: 0.34, metalness: 0, ...extra });

function caja(w, h, d, color, x = 0, y = 0, z = 0) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), typeof color === 'string' ? plastico(color) : color);
  m.position.set(x, y, z);
  m.castShadow = true;
  m.receiveShadow = true;
  return m;
}

const GEO_PERNO = new THREE.CylinderGeometry(0.24, 0.24, 0.17, 20);

/** Ladrillo con pernos. Medidas en pernos (1 perno = 0.8). Origen en la base. */
export function ladrillo(nx, nz, alto, color) {
  const g = new THREE.Group();
  const w = nx * 0.8;
  const d = nz * 0.8;
  g.add(caja(w - 0.02, alto, d - 0.02, color, 0, alto / 2, 0));
  const m = plastico(color);
  for (let i = 0; i < nx; i++) {
    for (let j = 0; j < nz; j++) {
      const p = new THREE.Mesh(GEO_PERNO, m);
      p.position.set((i - (nx - 1) / 2) * 0.8, alto + 0.085, (j - (nz - 1) / 2) * 0.8);
      p.castShadow = true;
      g.add(p);
    }
  }
  return g;
}

function letrero(texto, renderer, w, x, y, z, fondo) {
  const m = new THREE.Mesh(
    new THREE.PlaneGeometry(w, w * 0.1875),
    new THREE.MeshStandardMaterial({ map: texturaLetrero(texto, renderer, fondo), roughness: 0.6 }),
  );
  m.position.set(x, y, z);
  return m;
}

function lampara(scene, x, z) {
  const g = new THREE.Group();
  const cable = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 2.4, 6), plastico(COLOR.negro));
  cable.position.y = 1.2;
  const pantalla = new THREE.Mesh(
    new THREE.ConeGeometry(0.7, 0.5, 32, 1, true),
    plastico(COLOR.verde, { side: THREE.DoubleSide }),
  );
  const foco = new THREE.Mesh(
    new THREE.SphereGeometry(0.2, 16, 10),
    new THREE.MeshStandardMaterial({ color: '#fff3d6', emissive: '#ffe2a8', emissiveIntensity: 2.2 }),
  );
  foco.position.y = -0.2;
  g.add(cable, pantalla, foco);
  g.position.set(x, 7.6, z);
  scene.add(g);
  const luz = new THREE.PointLight('#ffd9a0', 9, 9, 1.6);
  luz.position.set(x, 7.1, z);
  scene.add(luz);
}

/* ---------------- cabina de fotos ---------------- */

export class Cabina {
  constructor(scene, renderer, x) {
    this.x = x;
    const g = new THREE.Group();
    g.position.x = x;
    g.add(caja(5.4, 4.6, 0.3, COLOR.azul, 0, 2.3, -2.3));
    g.add(caja(3.7, 2.3, 0.22, COLOR.negro, 0, 2.45, -2.08));
    this.pantallaMat = new THREE.MeshBasicMaterial({ color: '#10161c' });
    this.pantalla = new THREE.Mesh(new THREE.PlaneGeometry(3.4, 1.9125), this.pantallaMat);
    this.pantalla.position.set(0, 2.45, -1.96);
    g.add(this.pantalla);
    // cámara encima de la pantalla
    g.add(caja(0.8, 0.45, 0.45, COLOR.grisOscuro, 0, 3.85, -1.95));
    const lente = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.15, 0.2, 24), plastico(COLOR.negro));
    lente.rotation.x = Math.PI / 2;
    lente.position.set(0, 3.85, -1.66);
    g.add(lente);
    // guía ovalada para la cara
    const curva = new THREE.EllipseCurve(0, 0, 0.42, 0.58);
    const linea = new THREE.LineLoop(
      new THREE.BufferGeometry().setFromPoints(curva.getPoints(64)),
      new THREE.LineDashedMaterial({ color: '#ffffff', dashSize: 0.08, gapSize: 0.06, transparent: true, opacity: 0.85 }),
    );
    linea.computeLineDistances();
    linea.position.set(0, 2.5, -1.94);
    this.guia = linea;
    g.add(linea);
    // focos laterales
    for (const s of [-1, 1]) {
      g.add(caja(0.08, 2.6, 0.08, COLOR.negro, s * 2.35, 1.3, -1.2));
      const caja_luz = caja(0.9, 0.9, 0.3,
        new THREE.MeshStandardMaterial({ color: '#ffffff', emissive: '#fff8ea', emissiveIntensity: 0.8 }),
        s * 2.35, 2.9, -1.2);
      caja_luz.rotation.y = -s * 0.5;
      g.add(caja_luz);
    }
    g.add(letrero('FOTOS', renderer, 2.6, 0, 5.0, -2.12, COLOR.azulOscuro));
    this.flash = new THREE.PointLight('#ffffff', 0, 12, 1.2);
    this.flash.position.set(0, 3, 1.5);
    g.add(this.flash);
    scene.add(g);
    this.textura = null;
  }

  _ajustar(tex, ancho, alto, espejo) {
    const a = ancho / alto;
    const m = 16 / 9;
    tex.wrapS = THREE.RepeatWrapping;
    let rx = 1;
    let ry = 1;
    if (a > m) rx = m / a;
    else ry = a / m;
    tex.repeat.set(espejo ? -rx : rx, ry);
    tex.offset.set(espejo ? (1 + rx) / 2 : (1 - rx) / 2, (1 - ry) / 2);
  }

  mostrarVideo(video) {
    const t = new THREE.VideoTexture(video);
    t.colorSpace = THREE.SRGBColorSpace;
    this._ajustar(t, video.videoWidth || 16, video.videoHeight || 9, true);
    this._poner(t);
    this.guia.visible = true;
  }

  mostrarFoto(canvas, espejo = true) {
    const t = new THREE.CanvasTexture(canvas);
    t.colorSpace = THREE.SRGBColorSpace;
    this._ajustar(t, canvas.width, canvas.height, espejo);
    this._poner(t);
    this.guia.visible = false;
  }

  apagar() {
    this._poner(null);
    this.guia.visible = true;
  }

  _poner(t) {
    if (this.textura) this.textura.dispose();
    this.textura = t;
    this.pantallaMat.map = t;
    this.pantallaMat.color.set(t ? '#ffffff' : '#10161c');
    this.pantallaMat.needsUpdate = true;
  }

  disparar() {
    this.flash.intensity = 60;
  }

  update(dt) {
    this.flash.intensity *= Math.exp(-dt * 9);
  }
}

/* ---------------- línea de estampado ---------------- */

export class Linea {
  constructor(scene, renderer) {
    this.X0 = 3.3; // salida de la tolva
    this.XP = 8.5; // prensa
    this.XE = 13.6; // fin de la banda
    this.ESP = 1.55;
    this.Y = 1.08;
    const largo = 11.6;
    const cx = 8.4;

    this.banda = texturaBanda(renderer);
    this.banda.repeat.set(largo / 1.2, 1);
    const g = new THREE.Group();
    g.add(caja(largo, 0.14, 1.3, new THREE.MeshStandardMaterial({ map: this.banda, roughness: 0.8 }), cx, 1.01, 0));
    g.add(caja(largo, 0.5, 1.1, COLOR.grisOscuro, cx, 0.7, 0));
    const franjas = texturaFranjas(renderer);
    franjas.repeat.set(largo / 1.2, 1);
    for (const s of [-1, 1]) {
      g.add(caja(largo, 0.16, 0.1, new THREE.MeshStandardMaterial({ map: franjas, roughness: 0.5 }), cx, 1.14, s * 0.7));
      for (const x of [3.2, 6.4, 9.6, 12.8]) g.add(caja(0.24, 0.6, 0.24, COLOR.negro, x, 0.3, s * 0.45));
    }
    // tolva de cabezas lisas
    g.add(caja(1.5, 2.2, 1.6, COLOR.azul, 2.4, 1.1, 0));
    g.add(caja(1.7, 0.2, 1.8, COLOR.amarillo, 2.4, 2.3, 0));
    // bandeja final
    g.add(caja(1.4, 0.9, 1.6, COLOR.verde, 14.9, 0.45, 0));

    // prensa
    const xp = this.XP;
    // columnas atrás, para no tapar la cara que se estampa
    for (const s of [-1, 1]) g.add(caja(0.34, 3.6, 0.34, COLOR.grisClaro, xp + s * 0.85, 1.8, -0.85));
    g.add(caja(2.1, 0.95, 2.4, COLOR.rojo, xp, 3.95, -0.1));
    g.add(letrero('ESTAMPADO', renderer, 1.8, xp, 3.95, 1.21, COLOR.rojo));
    this.piston = caja(0.32, 1, 0.32, COLOR.grisClaro, xp, 3.2, 0);
    this.sello = caja(1.05, 0.3, 1.05, COLOR.grisOscuro, xp, 2.9, 0);
    g.add(this.piston, this.sello);
    this.luz = new THREE.Mesh(
      new THREE.SphereGeometry(0.16, 16, 10),
      new THREE.MeshStandardMaterial({ color: '#333', emissive: '#40ff70', emissiveIntensity: 0.4 }),
    );
    this.luz.position.set(xp + 0.65, 4.55, 0.6);
    g.add(this.luz);
    this.chispa = new THREE.PointLight('#fff2b0', 0, 4, 1.5);
    this.chispa.position.set(xp, 2.2, 0.9);
    g.add(this.chispa);

    // consola decorativa
    const consola = new THREE.Group();
    consola.add(caja(1.8, 1.2, 0.9, COLOR.grisClaro, 0, 0.6, 0));
    const tapa = caja(1.9, 0.12, 1.0, COLOR.negro, 0, 1.25, 0.05);
    tapa.rotation.x = 0.45;
    consola.add(tapa);
    [COLOR.rojo, COLOR.amarillo, COLOR.verde, COLOR.azul].forEach((c, i) => {
      const b = new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.11, 0.1, 20), plastico(c, { emissive: c, emissiveIntensity: 0.25 }));
      b.position.set(-0.6 + i * 0.4, 1.33, 0.12);
      b.rotation.x = 0.45;
      consola.add(b);
    });
    consola.position.set(4.6, 0, 2.6);
    consola.rotation.y = 0.5;
    g.add(consola);
    scene.add(g);

    this.cabezas = Array.from({ length: 5 }, () => {
      const c = new Cabeza(renderer);
      c.grupo.visible = false;
      scene.add(c.grupo);
      return c;
    });
    this.activo = false;
  }

  /** peinado: { id, color } que se encaja en cada cabeza al estamparla, o null. */
  iniciar(n = 5, peinado = null) {
    this.peinado = peinado;
    this.cabezas.forEach((c) => c.ponerCabello(null));
    this.n = n;
    this.s = 0;
    this.listos = Array(n).fill(null);
    this.estampadas = 0;
    this.prensa = null;
    this.activo = true;
    this.terminada = false;
    this.cabezas.forEach((c) => {
      c.vaciar();
      c.grupo.visible = false;
    });
  }

  entregar(i, img) {
    this.listos[i] = img;
  }

  /** Avanza la banda; se detiene bajo la prensa hasta que la cara de esa cabeza llegue del servidor. */
  update(dt, t) {
    if (!this.activo) {
      this.luz.material.emissiveIntensity = 0.4;
      this.mueve = this.espera = false;
      return;
    }
    const todas = this.listos.every(Boolean);
    const v = todas ? 3.4 : 2.4;
    let mueve = false;
    let espera = false;

    if (this.prensa) {
      const p = this.prensa;
      p.t += dt / 0.5;
      const baja = Math.sin(Math.min(1, p.t) * Math.PI);
      this.sello.position.y = 2.9 - baja * 0.58;
      this.piston.position.y = 3.2 - baja * 0.29;
      this.piston.scale.y = 1 + baja * 0.58;
      if (p.t >= 0.5 && !p.puesta) {
        p.puesta = true;
        this.cabezas[p.k].ponerImagen(this.listos[p.k]);
        this.cabezas[p.k].ponerCabello(this.peinado);
        this.chispa.intensity = 25;
        this.onEstampada?.(p.k);
      }
      if (p.t >= 1) {
        this.prensa = null;
        this.estampadas++;
      }
    } else if (this.estampadas < this.n) {
      const meta = this.XP - this.X0 + this.estampadas * this.ESP;
      if (this.s < meta) {
        this.s = Math.min(meta, this.s + v * dt);
        mueve = true;
      } else if (this.listos[this.estampadas]) {
        this.prensa = { k: this.estampadas, t: 0, puesta: false };
      } else {
        espera = true;
      }
    } else {
      const fin = this.XE - this.X0 + (this.n - 1) * this.ESP + 0.9;
      if (this.s < fin) {
        this.s += v * dt;
        mueve = true;
      } else if (!this.terminada) {
        this.terminada = true;
        this.activo = false;
        this.onFin?.();
      }
    }

    this.mueve = mueve;
    this.espera = espera;
    if (mueve) this.banda.offset.x -= (v * dt) / 1.2;
    this.chispa.intensity *= Math.exp(-dt * 10);
    this.luz.material.emissive.set(espera ? '#ffb000' : '#40ff70');
    this.luz.material.emissiveIntensity = espera ? 0.6 + Math.sin(t * 9) * 0.5 : 0.9;
    if (espera) this.sello.position.y = 2.9 + Math.sin(t * 40) * 0.012;

    this.cabezas.forEach((c, i) => {
      if (i >= this.n) {
        c.grupo.visible = false;
        return;
      }
      const x = this.X0 + this.s - i * this.ESP;
      c.grupo.visible = x > this.X0 - 0.2 && x < this.XE + 0.8;
      let y = this.Y;
      if (x > this.XE) y -= (x - this.XE) * 1.6; // cae a la bandeja
      c.grupo.position.set(x, y, 0);
      c.grupo.rotation.y = 0;
    });
  }
}

/* ---------------- control de calidad ---------------- */

function iconoSello(tipo) {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d');
  g.fillStyle = tipo === 'aprobada' ? COLOR.verde : COLOR.rojo;
  g.beginPath();
  g.arc(64, 64, 58, 0, Math.PI * 2);
  g.fill();
  g.strokeStyle = '#fff';
  g.lineWidth = 14;
  g.lineCap = 'round';
  g.lineJoin = 'round';
  g.beginPath();
  if (tipo === 'aprobada') {
    g.moveTo(36, 66);
    g.lineTo(56, 86);
    g.lineTo(92, 44);
  } else {
    g.moveTo(42, 42);
    g.lineTo(86, 86);
    g.moveTo(86, 42);
    g.lineTo(42, 86);
  }
  g.stroke();
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

export class Control {
  constructor(scene, renderer, cx) {
    this.cx = cx;
    const g = new THREE.Group();
    g.add(caja(7.6, 0.9, 1.8, COLOR.blanco, cx, 0.45, 0));
    g.add(caja(7.8, 0.1, 2.0, COLOR.grisClaro, cx, 0.95, 0));
    g.add(letrero('CONTROL DE CALIDAD', renderer, 5.2, cx, 5.4, -4.35, COLOR.verde));
    scene.add(g);
    this.iconos = { aprobada: iconoSello('aprobada'), rechazada: iconoSello('rechazada') };
    this.puestos = Array.from({ length: 5 }, (_, i) => {
      const x = cx + (i - 2) * 1.42;
      const pedestal = caja(1.0, 0.3, 1.0, COLOR.grisOscuro, x, 1.15, 0);
      const anillo = new THREE.Mesh(
        new THREE.TorusGeometry(0.62, 0.05, 10, 48),
        new THREE.MeshStandardMaterial({ color: '#ffffff', emissive: '#ffffff', emissiveIntensity: 0.15 }),
      );
      anillo.rotation.x = Math.PI / 2;
      anillo.position.set(x, 1.32, 0);
      const cabeza = new Cabeza(renderer);
      cabeza.grupo.position.set(x, 1.3, 0);
      cabeza.grupo.traverse((o) => (o.userData.puesto = i));
      const sello = new THREE.Sprite(new THREE.SpriteMaterial({ transparent: true, depthTest: false }));
      sello.scale.set(0.55, 0.55, 1);
      sello.position.set(x + 0.45, 2.55, 0.4);
      sello.visible = false;
      g.add(pedestal, anillo, cabeza.grupo, sello);
      return { x, anillo, cabeza, sello, decision: null, aparece: 0 };
    });
    this.seleccion = null;
    this.hover = null;
  }

  cargar(imgs, peinado = null) {
    this.puestos.forEach((p, i) => {
      p.cabeza.ponerImagen(imgs[i]);
      p.cabeza.ponerCabello(peinado);
      p.decision = null;
      p.sello.visible = false;
      p.aparece = -i * 0.12;
      p.cabeza.grupo.scale.setScalar(0.001);
      p.cabeza.grupo.rotation.y = 0;
      this._anillo(p);
    });
    this.seleccion = null;
  }

  decidir(i, decision) {
    const p = this.puestos[i];
    if (decision === 'aceptada') decision = 'aprobada';
    p.decision = decision;
    p.sello.visible = !!decision;
    if (decision) {
      p.sello.material.map = this.iconos[decision];
      p.sello.material.needsUpdate = true;
      p.golpe = 1;
    }
    this._anillo(p);
  }

  _anillo(p) {
    const c = p.decision === 'aprobada' ? '#2bd463' : p.decision === 'rechazada' ? '#ff3b2f' : '#ffffff';
    p.anillo.material.color.set(c);
    p.anillo.material.emissive.set(c);
    p.anillo.material.emissiveIntensity = p.decision ? 1.1 : 0.15;
  }

  objetivos() {
    return this.puestos.map((p) => p.cabeza.grupo);
  }

  update(dt, t) {
    this.puestos.forEach((p, i) => {
      p.aparece = Math.min(1, p.aparece + dt * 2.2);
      const a = Math.max(0, p.aparece);
      const rebote = a < 1 ? 1 + Math.sin(a * Math.PI) * 0.25 : 1;
      const sel = this.seleccion === i;
      const hov = this.hover === i;
      const escala = a * rebote * (sel ? 1.28 : hov ? 1.1 : 1);
      const s = p.cabeza.grupo.scale.x;
      p.cabeza.grupo.scale.setScalar(s + (escala - s) * Math.min(1, dt * 10));
      const yObj = 1.3 + (sel ? 0.3 : 0);
      p.cabeza.grupo.position.y += (yObj - p.cabeza.grupo.position.y) * Math.min(1, dt * 8);
      // todas miran al frente y se mecen; la seleccionada un poco más
      const giro = Math.sin(t * (sel ? 1.6 : 0.9) + i * 1.3) * (sel ? 0.55 : 0.35);
      p.cabeza.grupo.rotation.y += (giro - p.cabeza.grupo.rotation.y) * Math.min(1, dt * 5);
      p.cabeza.brillo('#ffffff', hov && !sel ? 0.12 : 0);
      if (p.golpe) {
        p.golpe = Math.max(0, p.golpe - dt * 3);
        const k = 0.55 * (1 + p.golpe * 0.6);
        p.sello.scale.set(k, k, 1);
      }
    });
  }

  /** Ángulo de la cabeza normalizado, para que al seleccionarla quede de frente. */
  enfrentar(i) {
    const g = this.puestos[i].cabeza.grupo;
    g.rotation.y = Math.atan2(Math.sin(g.rotation.y), Math.cos(g.rotation.y));
  }
}

/* ---------------- oficina de asesoría ---------------- */

const ETIQUETAS_FICHA = [
  ['foto', 'Foto'],
  ['expresion', 'Expresión'],
  ['lentes', 'Lentes'],
  ['vello', 'Barba / bigote'],
  ['cabello', 'Cabello (cejas)'],
  ['ojos', 'Ojos'],
  ['detalles', 'Detalles'],
];

export class Oficina {
  constructor(scene, renderer, x) {
    this.x = x;
    const g = new THREE.Group();
    g.position.x = x;
    // pizarra
    g.add(caja(5.6, 3.7, 0.2, COLOR.marron, 0, 3.5, -2.6));
    this.lienzo = document.createElement('canvas');
    this.lienzo.width = 1024;
    this.lienzo.height = 640;
    this.tex = new THREE.CanvasTexture(this.lienzo);
    this.tex.colorSpace = THREE.SRGBColorSpace;
    this.tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
    const pizarra = new THREE.Mesh(new THREE.PlaneGeometry(5.3, 3.31), new THREE.MeshStandardMaterial({ map: this.tex, roughness: 0.85 }));
    pizarra.position.set(0, 3.5, -2.48);
    g.add(pizarra);
    for (const s of [-1, 1]) g.add(caja(0.16, 1.75, 0.16, COLOR.marron, s * 2.2, 0.875, -2.55));
    g.add(letrero('ASESORÍA', renderer, 2.8, 0, 5.9, -2.55, COLOR.verde));
    // escritorio con lámpara y papeles
    g.add(caja(3.2, 0.14, 1.4, COLOR.beige, -0.9, 1.25, 0.2));
    for (const [dx, dz] of [[-2.3, -0.3], [0.5, -0.3], [-2.3, 0.7], [0.5, 0.7]]) g.add(caja(0.14, 1.2, 0.14, COLOR.marron, dx, 0.6, dz));
    const hoja = caja(0.8, 0.02, 1.0, COLOR.blanco, -1.4, 1.33, 0.2);
    hoja.rotation.y = 0.2;
    g.add(hoja);
    const lapiz = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.7, 10), plastico(COLOR.amarillo));
    lapiz.rotation.set(0, 0.6, Math.PI / 2);
    lapiz.position.set(-0.6, 1.36, 0.35);
    g.add(lapiz);
    const banco = ladrillo(2, 2, 0.9, COLOR.azul);
    banco.position.set(-0.9, 0, 1.6);
    g.add(banco);
    const planta = new THREE.Group();
    planta.add(caja(0.7, 0.7, 0.7, COLOR.rojo, 0, 0.35, 0));
    for (let i = 0; i < 5; i++) {
      const hojaP = new THREE.Mesh(new THREE.ConeGeometry(0.2, 1.1, 8), plastico(COLOR.verde));
      hojaP.position.set(Math.cos(i * 1.3) * 0.15, 1.1, Math.sin(i * 1.3) * 0.15);
      hojaP.rotation.set(Math.sin(i) * 0.4, 0, Math.cos(i) * 0.4);
      planta.add(hojaP);
    }
    planta.position.set(2.9, 0, -1.6);
    g.add(planta);
    // maniquí sobre un pedestal, bajo el marco de la foto: muestra el peinado mientras se elige
    g.add(caja(1.0, 1.25, 1.0, COLOR.grisClaro, 1.75, 0.625, -1.5));
    this.maniqui = new Cabeza(renderer);
    this.maniqui.grupo.position.set(1.75, 1.25, -1.5);
    this.maniqui.grupo.scale.setScalar(1.2);
    g.add(this.maniqui.grupo);
    scene.add(g);
    this.dibujar({}, null);
    this.t = 0;
  }

  mostrarPeinado(peinado) {
    this.maniqui.ponerCabello(peinado);
  }

  update(dt) {
    this.t += dt;
    this.maniqui.grupo.rotation.y = Math.sin(this.t * 0.6) * 0.7;
  }

  /** Dibuja la ficha en la pizarra. valores: { foto, expresion, lentes, vello, cabello, ojos, detalles } */
  dibujar(valores, foto) {
    const c = this.lienzo.getContext('2d');
    c.fillStyle = '#23412f';
    c.fillRect(0, 0, 1024, 640);
    c.strokeStyle = 'rgba(255,255,255,0.08)';
    c.lineWidth = 2;
    for (let y = 60; y < 640; y += 48) {
      c.beginPath();
      c.moveTo(0, y);
      c.lineTo(1024, y);
      c.stroke();
    }
    c.fillStyle = '#f4f1e6';
    c.font = '600 52px Fredoka, sans-serif';
    c.fillText('Ficha de tu cara', 48, 82);
    c.font = '500 36px Fredoka, sans-serif';
    ETIQUETAS_FICHA.forEach(([k, et], i) => {
      const y = 158 + i * 66;
      const v = valores[k];
      c.fillStyle = 'rgba(244,241,230,0.65)';
      c.fillText(et, 48, y);
      c.fillStyle = v ? '#f2cd37' : 'rgba(244,241,230,0.35)';
      let txt = v || '—';
      if (txt.length > 26) txt = txt.slice(0, 25) + '…';
      c.fillText(txt, 360, y);
    });
    // marco de la foto
    c.strokeStyle = '#f4f1e6';
    c.lineWidth = 4;
    c.setLineDash([12, 10]);
    c.strokeRect(770, 130, 210, 210);
    c.setLineDash([]);
    if (foto) {
      const s = Math.min(foto.width, foto.height);
      c.drawImage(foto, (foto.width - s) / 2, (foto.height - s) / 2, s, s, 772, 132, 206, 206);
    } else {
      c.fillStyle = 'rgba(244,241,230,0.35)';
      c.font = '500 28px Fredoka, sans-serif';
      c.fillText('sin foto', 820, 245);
    }
    this.tex.needsUpdate = true;
  }
}

/* ---------------- fábrica completa ---------------- */

export function construirFabrica(scene, renderer) {
  // piso con pernos
  const piso = new THREE.Mesh(new THREE.PlaneGeometry(120, 90), plastico('#7d8287'));
  piso.rotation.x = -Math.PI / 2;
  piso.position.set(6, 0, 30);
  piso.receiveShadow = true;
  scene.add(piso);
  const pernos = [];
  for (let x = -22; x <= 28; x += 1.6) for (let z = -3.6; z <= 12; z += 1.6) pernos.push([x, z]);
  const inst = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.3, 0.3, 0.12, 16), plastico('#7d8287'), pernos.length);
  const m = new THREE.Matrix4();
  pernos.forEach(([x, z], i) => inst.setMatrixAt(i, m.makeTranslation(x, 0.06, z)));
  inst.receiveShadow = true;
  scene.add(inst);

  // pared
  const pared = texturaPared(renderer);
  pared.repeat.set(12, 3);
  const muro = new THREE.Mesh(new THREE.PlaneGeometry(56, 11), new THREE.MeshStandardMaterial({ map: pared, roughness: 0.9 }));
  muro.position.set(3, 5.5, -4.5);
  muro.receiveShadow = true;
  scene.add(muro);
  scene.add(caja(56, 0.6, 0.3, COLOR.grisOscuro, 3, 0.3, -4.4));
  scene.add(letrero('FÁBRICA DE LEGO', renderer, 7.5, 0, 6.2, -4.38));

  // recepción
  const mostrador = new THREE.Group();
  mostrador.add(caja(3.0, 1.4, 1.2, COLOR.rojo, 0, 0.7, 0));
  const tapa = ladrillo(4, 2, 0.16, COLOR.blanco);
  tapa.position.y = 1.4;
  mostrador.add(tapa);
  mostrador.position.set(-1.6, 0, 0.2);
  scene.add(mostrador);
  const pila = [
    [2, 2, COLOR.amarillo, -4.4, 0, 2.6, 0],
    [2, 2, COLOR.azul, -4.4, 1.15, 2.6, 0.4],
    [2, 1, COLOR.verde, -3.6, 0, 3.4, 0.2],
    [3, 2, COLOR.rojo, 3.4, 0, -2.6, 0.1],
    [2, 2, COLOR.amarillo, 3.4, 1.15, -2.6, -0.3],
  ];
  for (const [nx, nz, c, x, y, z, r] of pila) {
    const l = ladrillo(nx, nz, 0.96, c);
    l.position.set(x, y, z);
    l.rotation.y = r;
    scene.add(l);
  }

  for (const x of [0, -7, 8.4, 17]) lampara(scene, x, 0.6);

  for (const x of [-15]) lampara(scene, x, 0.6);
  const cabina = new Cabina(scene, renderer, -7);
  const oficina = new Oficina(scene, renderer, -15);
  const linea = new Linea(scene, renderer);
  const control = new Control(scene, renderer, 17.2);
  return { cabina, oficina, linea, control };
}
