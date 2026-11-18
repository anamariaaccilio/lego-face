import * as THREE from 'three';
import { geometriaCabello, mallaCabello } from './cabello.js';
import { CABEZA, COLOR, texturaCaraImagen, texturaCaraTito, texturaTorsoTito } from './texturas.js';

const plastico = (color, extra = {}) =>
  new THREE.MeshStandardMaterial({ color, roughness: 0.32, metalness: 0, ...extra });

function sombra(obj) {
  obj.traverse((o) => {
    if (o.isMesh) {
      o.castShadow = true;
      o.receiveShadow = true;
    }
  });
  return obj;
}

/** Cabeza con perno arriba y cuello abajo. Su origen está en la base del cuello. */
export class Cabeza {
  constructor(renderer) {
    this.renderer = renderer;
    const { r, h, bisel } = CABEZA;
    const amarillo = plastico(COLOR.amarillo);
    this.material = plastico('#ffffff', { map: texturaCaraImagen(null, renderer) });
    this.grupo = new THREE.Group();
    const y0 = 0.12 + h / 2; // centro de la cabeza sobre el cuello

    // Lado recto con la cara. thetaStart = -π deja el centro del lienzo mirando a +z.
    const lado = new THREE.Mesh(
      new THREE.CylinderGeometry(r, r, h - 2 * bisel, 72, 1, true, -Math.PI, Math.PI * 2),
      this.material,
    );
    lado.position.y = y0;
    const anillo = new THREE.TorusGeometry(r - bisel, bisel, 12, 72);
    for (const s of [1, -1]) {
      const a = new THREE.Mesh(anillo, amarillo);
      a.rotation.x = Math.PI / 2;
      a.position.y = y0 + s * (h / 2 - bisel);
      const tapa = new THREE.Mesh(new THREE.CircleGeometry(r - bisel, 48), amarillo);
      tapa.rotation.x = -s * Math.PI / 2;
      tapa.position.y = y0 + s * (h / 2);
      this.grupo.add(a, tapa);
    }
    const perno = new THREE.Mesh(new THREE.CylinderGeometry(0.29, 0.29, 0.17, 40), amarillo);
    perno.position.y = y0 + h / 2 + 0.085;
    const cuello = new THREE.Mesh(new THREE.CylinderGeometry(0.27, 0.27, 0.12, 40), amarillo);
    cuello.position.y = 0.06;
    this.grupo.add(lado, perno, cuello);
    this.lado = lado;
    sombra(this.grupo);
  }

  ponerTextura(tex) {
    if (this.material.map && this.material.map !== tex && !this.material.map.userData.compartida) {
      this.material.map.dispose();
    }
    this.material.map = tex;
    this.material.needsUpdate = true;
  }

  ponerImagen(img) {
    this.ponerTextura(texturaCaraImagen(img, this.renderer));
  }

  vaciar() {
    this.ponerTextura(texturaCaraImagen(null, this.renderer));
  }

  /** peinado: { id, color } o null. Carga la pieza la primera vez; las llamadas viejas se descartan. */
  async ponerCabello(peinado) {
    const turno = (this._turnoCabello = (this._turnoCabello || 0) + 1);
    const previo = this.grupo.getObjectByName('cabello');
    if (!peinado?.id) {
      if (previo) this.grupo.remove(previo);
      return;
    }
    const geo = await geometriaCabello(peinado.id);
    if (turno !== this._turnoCabello) return;
    const viejo = this.grupo.getObjectByName('cabello');
    if (viejo) this.grupo.remove(viejo);
    this.grupo.add(mallaCabello(geo, peinado.color));
  }

  brillo(color, intensidad) {
    this.material.emissive.set(color);
    this.material.emissiveIntensity = intensidad;
  }
}

/** Torso de LEGO: caja más angosta arriba. La cara +z puede llevar estampa. */
function torso(color, frente) {
  const geo = new THREE.BoxGeometry(1.6, 1.3, 0.8, 1, 1, 1);
  const p = geo.attributes.position;
  for (let i = 0; i < p.count; i++) {
    if (p.getY(i) > 0) p.setX(i, p.getX(i) * 0.76);
  }
  geo.computeVertexNormals();
  const base = plastico(color);
  const mats = [base, base, base, base, frente ? plastico('#ffffff', { map: frente }) : base, base];
  return new THREE.Mesh(geo, mats);
}

function brazo(color, lado) {
  const g = new THREE.Group();
  const sup = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.24, 0.95, 24), plastico(color));
  sup.position.set(0, -0.42, 0.06);
  sup.rotation.x = -0.12;
  const mano = new THREE.Mesh(
    new THREE.TorusGeometry(0.15, 0.075, 10, 24, Math.PI * 1.55),
    plastico(COLOR.amarillo),
  );
  mano.position.set(0, -0.98, 0.16);
  mano.rotation.set(Math.PI / 2, 0, Math.PI * 0.73);
  g.add(sup, mano);
  g.rotation.z = lado * 0.1;
  return g;
}

function pierna(color) {
  const g = new THREE.Group();
  const muslo = new THREE.Mesh(new THREE.BoxGeometry(0.76, 0.95, 0.78), plastico(color));
  muslo.position.set(0, -0.5, 0);
  const pie = new THREE.Mesh(new THREE.BoxGeometry(0.76, 0.26, 0.98), plastico(color));
  pie.position.set(0, -1.07, 0.08);
  g.add(muslo, pie);
  return g;
}

function casco(color) {
  const g = new THREE.Group();
  const m = plastico(color);
  const cupula = new THREE.Mesh(new THREE.SphereGeometry(0.6, 40, 20, 0, Math.PI * 2, 0, Math.PI / 2), m);
  const ala = new THREE.Mesh(new THREE.CylinderGeometry(0.72, 0.72, 0.06, 48), m);
  ala.position.set(0, 0.0, 0.06);
  const cresta = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.12, 1.0), m);
  cresta.position.y = 0.52;
  cresta.scale.z = 0.95;
  g.add(cupula, ala, cresta);
  return g;
}

/** Minifigura completa. Origen en los pies. */
export class Minifig {
  constructor(renderer, { torsoColor = COLOR.rojo, piernas = COLOR.azul, brazos, tito = false } = {}) {
    this.raiz = new THREE.Group();
    this.cuerpo = new THREE.Group();
    this.raiz.add(this.cuerpo);

    this.piernas = [-1, 1].map((s) => {
      const p = pierna(piernas);
      p.position.set(s * 0.4, 1.22, 0);
      this.cuerpo.add(p);
      return p;
    });
    const cadera = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.28, 0.8), plastico(piernas));
    cadera.position.y = 1.36;

    this.superior = new THREE.Group();
    this.superior.position.y = 1.5;
    const t = torso(torsoColor, tito ? texturaTorsoTito(renderer) : null);
    t.position.y = 0.65;
    this.brazos = [-1, 1].map((s) => {
      const b = brazo(brazos || torsoColor, s);
      b.position.set(s * 0.8, 1.12, 0);
      this.superior.add(b);
      return b;
    });
    this.cabeza = new Cabeza(renderer);
    this.cabeza.grupo.position.y = 1.3;
    this.superior.add(t, this.cabeza.grupo);
    this.cuerpo.add(cadera, this.superior);

    if (tito) {
      this.caras = { sonrisa: texturaCaraTito('sonrisa', renderer), abierta: texturaCaraTito('abierta', renderer) };
      for (const tx of Object.values(this.caras)) tx.userData.compartida = true;
      this.cabeza.ponerTextura(this.caras.sonrisa);
      const c = casco(COLOR.naranja);
      c.position.y = 0.12 + CABEZA.h * 0.78;
      this.cabeza.grupo.add(c);
    }
    sombra(this.raiz);

    this.t = Math.random() * 10;
    this.saludo = 0;
    this.hablando = false;
    this.bocaT = 0;
    this.destino = null;
    this.mirar = null; // punto del mundo al que gira la cabeza
  }

  saludar(seg = 2.4) {
    this.saludo = seg;
  }

  hablar(si) {
    this.hablando = si;
    if (!si && this.caras) this.cabeza.ponerTextura(this.caras.sonrisa);
  }

  caminarA(x, z) {
    return new Promise((resolve) => {
      this.destino = { x, z, resolve };
    });
  }

  ponerEn(x, z) {
    this.raiz.position.set(x, 0, z);
    this.destino = null;
  }

  update(dt, camara) {
    this.t += dt;
    const r = this.raiz;
    let paso = 0;

    if (this.destino) {
      const dx = this.destino.x - r.position.x;
      const dz = this.destino.z - r.position.z;
      const d = Math.hypot(dx, dz);
      if (d < 0.05) {
        r.position.x = this.destino.x;
        r.position.z = this.destino.z;
        const fin = this.destino.resolve;
        this.destino = null;
        fin();
      } else {
        const v = Math.min(d, 3.4 * dt);
        r.position.x += (dx / d) * v;
        r.position.z += (dz / d) * v;
        girarHacia(r, Math.atan2(dx, dz), dt * 10);
        paso = 1;
      }
    }
    if (!this.destino && camara) {
      girarHacia(r, Math.atan2(camara.position.x - r.position.x, camara.position.z - r.position.z), dt * 4);
    }

    const fase = Math.sin(this.t * 11);
    if (paso && Math.sign(fase) !== Math.sign(this._fase || 0)) this.onPaso?.();
    this._fase = fase;
    const sw = fase * 0.55 * paso;
    this.piernas[0].rotation.x = sw;
    this.piernas[1].rotation.x = -sw;
    this.cuerpo.position.y = paso ? Math.abs(Math.sin(this.t * 11)) * 0.08 : 0;
    this.superior.position.y = 1.5 + Math.sin(this.t * 2.2) * 0.012;

    // brazo izquierdo acompaña el paso; el derecho saluda
    this.brazos[1].rotation.x = sw * 0.8;
    if (this.saludo > 0) {
      this.saludo -= dt;
      const sube = Math.min(1, this.saludo * 3, (2.4 - this.saludo) * 4 + 0.2);
      this.brazos[0].rotation.z = -0.1 - sube * (2.3 + Math.sin(this.t * 13) * 0.3);
      this.brazos[0].rotation.x = 0;
    } else {
      this.brazos[0].rotation.z += (-0.1 - this.brazos[0].rotation.z) * Math.min(1, dt * 8);
      this.brazos[0].rotation.x = -sw * 0.8;
    }

    // la cabeza busca a la cámara o al punto indicado
    const objetivo = this.mirar || camara?.position;
    if (objetivo) {
      const local = r.worldToLocal(objetivo.clone());
      const giro = THREE.MathUtils.clamp(Math.atan2(local.x, local.z), -0.7, 0.7);
      const g = this.cabeza.grupo;
      g.rotation.y += (giro - g.rotation.y) * Math.min(1, dt * 5);
    }

    if (this.hablando && this.caras) {
      this.bocaT -= dt;
      if (this.bocaT <= 0) {
        this.bocaT = 0.09 + Math.random() * 0.08;
        const abierta = this.cabeza.material.map === this.caras.sonrisa;
        this.cabeza.ponerTextura(abierta ? this.caras.abierta : this.caras.sonrisa);
      }
      this.cabeza.grupo.position.y = 1.3 + Math.abs(Math.sin(this.t * 14)) * 0.025;
    } else {
      this.cabeza.grupo.position.y = 1.3;
    }
  }

  /** Punto sobre la cabeza, para colgar el globo de diálogo. */
  puntoGlobo(v = new THREE.Vector3()) {
    return this.raiz.localToWorld(v.set(0, 4.1, 0));
  }
}

function girarHacia(obj, ang, k) {
  let d = ang - obj.rotation.y;
  d = Math.atan2(Math.sin(d), Math.cos(d));
  obj.rotation.y += d * Math.min(1, k);
}
