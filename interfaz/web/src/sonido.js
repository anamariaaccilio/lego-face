/**
 * Sonidos sintetizados con Web Audio: no hay archivos de audio.
 * El navegador solo deja sonar después de un gesto del usuario, por eso activar() se llama en el primer clic.
 */
const CLAVE = 'fabrica.silencio';

function leerSilencio() {
  try {
    return localStorage.getItem(CLAVE) === '1';
  } catch {
    return false;
  }
}

class Sonido {
  constructor() {
    this.ctx = null;
    this.silencio = leerSilencio();
    this.ultimaVoz = 0;
    this.ultimaAlarma = 0;
  }

  activar() {
    if (!this.ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      const ctx = new AC();
      this.ctx = ctx;
      this.maestro = ctx.createGain();
      this.maestro.gain.value = this.silencio ? 0 : 0.7;
      const comp = ctx.createDynamicsCompressor();
      this.maestro.connect(comp).connect(ctx.destination);
      this._ruidoBuf = this._crearRuido();
      this._ambiente();
      this._banda();
    }
    if (this.ctx.state === 'suspended') this.ctx.resume();
  }

  ponerSilencio(si) {
    this.silencio = si;
    try {
      localStorage.setItem(CLAVE, si ? '1' : '0');
    } catch {
      /* sin almacenamiento */
    }
    if (this.ctx) this.maestro.gain.setTargetAtTime(si ? 0 : 0.7, this.ctx.currentTime, 0.05);
  }

  get listo() {
    return this.ctx && this.ctx.state === 'running' && !this.silencio;
  }

  /* ---------- piezas básicas ---------- */

  _crearRuido() {
    const n = this.ctx.sampleRate * 2;
    const b = this.ctx.createBuffer(1, n, this.ctx.sampleRate);
    const d = b.getChannelData(0);
    for (let i = 0; i < n; i++) d[i] = Math.random() * 2 - 1;
    return b;
  }

  _env(g, t, vol, ataque, dur) {
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol, t + ataque);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  }

  tono(f, dur, { tipo = 'sine', vol = 0.2, f2 = null, ataque = 0.005, retraso = 0, destino = null } = {}) {
    if (!this.listo) return;
    const t = this.ctx.currentTime + retraso;
    const o = this.ctx.createOscillator();
    const g = this.ctx.createGain();
    o.type = tipo;
    o.frequency.setValueAtTime(f, t);
    if (f2) o.frequency.exponentialRampToValueAtTime(f2, t + dur);
    this._env(g, t, vol, ataque, dur);
    o.connect(g).connect(destino || this.maestro);
    o.start(t);
    o.stop(t + dur + 0.05);
  }

  ruido(dur, { vol = 0.2, filtro = 'bandpass', f = 1000, q = 1, retraso = 0 } = {}) {
    if (!this.listo) return;
    const t = this.ctx.currentTime + retraso;
    const s = this.ctx.createBufferSource();
    s.buffer = this._ruidoBuf;
    const fl = this.ctx.createBiquadFilter();
    fl.type = filtro;
    fl.frequency.value = f;
    fl.Q.value = q;
    const g = this.ctx.createGain();
    this._env(g, t, vol, 0.003, dur);
    s.connect(fl).connect(g).connect(this.maestro);
    s.start(t, Math.random());
    s.stop(t + dur + 0.05);
  }

  /* ---------- sonidos de la fábrica ---------- */

  /** Sílaba de Tito. Se llama mientras se escribe su texto. */
  voz() {
    if (!this.listo) return;
    const ahora = performance.now();
    if (ahora - this.ultimaVoz < 70) return;
    this.ultimaVoz = ahora;
    const f = 300 + Math.random() * 140;
    const t = this.ctx.currentTime;
    const o = this.ctx.createOscillator();
    const fl = this.ctx.createBiquadFilter();
    const g = this.ctx.createGain();
    o.type = 'square';
    o.frequency.setValueAtTime(f, t);
    o.frequency.linearRampToValueAtTime(f * (0.9 + Math.random() * 0.25), t + 0.06);
    fl.type = 'bandpass';
    fl.frequency.value = 900 + Math.random() * 900;
    fl.Q.value = 3;
    this._env(g, t, 0.09, 0.006, 0.065);
    o.connect(fl).connect(g).connect(this.maestro);
    o.start(t);
    o.stop(t + 0.1);
  }

  clic() {
    this.tono(1900, 0.03, { tipo: 'triangle', vol: 0.08 });
    this.ruido(0.02, { vol: 0.06, f: 4000, q: 2 });
  }

  paso() {
    this.tono(170 + Math.random() * 40, 0.05, { tipo: 'triangle', vol: 0.05 });
    this.ruido(0.03, { vol: 0.03, f: 2500, q: 3 });
  }

  bip(alto = false) {
    this.tono(alto ? 1320 : 880, 0.14, { tipo: 'square', vol: 0.08 });
  }

  obturador() {
    this.ruido(0.035, { vol: 0.35, f: 3000, q: 1.2 });
    this.ruido(0.05, { vol: 0.25, f: 1800, q: 1.2, retraso: 0.07 });
    this.tono(2400, 0.25, { tipo: 'sine', vol: 0.05, f2: 600, retraso: 0.02 });
  }

  /** Golpe de la prensa: bombo grave + choque metálico. */
  prensa() {
    this.tono(110, 0.3, { vol: 0.5, f2: 42 });
    this.ruido(0.12, { vol: 0.25, filtro: 'lowpass', f: 700 });
    for (const [f, v] of [[523, 0.07], [1187, 0.05], [1679, 0.035], [2520, 0.02]]) {
      this.tono(f, 0.45, { tipo: 'triangle', vol: v, retraso: 0.01 });
    }
  }

  /** Aviso suave mientras la prensa espera la siguiente cara. */
  esperando() {
    const ahora = performance.now();
    if (ahora - this.ultimaAlarma < 1400) return;
    this.ultimaAlarma = ahora;
    this.tono(660, 0.12, { tipo: 'sine', vol: 0.05 });
    this.tono(550, 0.14, { tipo: 'sine', vol: 0.05, retraso: 0.16 });
  }

  aprobar() {
    this.tono(1047, 0.35, { vol: 0.14 });
    this.tono(1568, 0.5, { vol: 0.12, retraso: 0.08 });
  }

  rechazar() {
    this.tono(240, 0.22, { tipo: 'square', vol: 0.07, f2: 140 });
    this.ruido(0.06, { vol: 0.08, filtro: 'lowpass', f: 500 });
  }

  /** Arpegio corto cuando salen las 5 caras. */
  listoRonda() {
    [523, 659, 784, 1047].forEach((f, i) => this.tono(f, 0.3, { tipo: 'triangle', vol: 0.1, retraso: i * 0.09 }));
  }

  /* ---------- fondos continuos ---------- */

  _ambiente() {
    const ctx = this.ctx;
    // murmullo: ruido marrón muy filtrado
    const n = ctx.sampleRate * 4;
    const b = ctx.createBuffer(1, n, ctx.sampleRate);
    const d = b.getChannelData(0);
    let ultimo = 0;
    for (let i = 0; i < n; i++) {
      ultimo = (ultimo + 0.02 * (Math.random() * 2 - 1)) / 1.02;
      d[i] = ultimo * 3.5;
    }
    const s = ctx.createBufferSource();
    s.buffer = b;
    s.loop = true;
    const fl = ctx.createBiquadFilter();
    fl.type = 'lowpass';
    fl.frequency.value = 380;
    const g = ctx.createGain();
    g.gain.value = 0.05;
    s.connect(fl).connect(g).connect(this.maestro);
    s.start();
    // golpes lejanos de vez en cuando
    const lejano = () => {
      if (this.listo) {
        const f = [196, 262, 330][Math.floor(Math.random() * 3)];
        this.tono(f, 0.5, { tipo: 'triangle', vol: 0.012 });
        this.ruido(0.08, { vol: 0.015, filtro: 'lowpass', f: 600 });
      }
      setTimeout(lejano, 4000 + Math.random() * 6000);
    };
    setTimeout(lejano, 3000);
  }

  _banda() {
    const ctx = this.ctx;
    const o = ctx.createOscillator();
    o.type = 'sawtooth';
    o.frequency.value = 58;
    const fl = ctx.createBiquadFilter();
    fl.type = 'lowpass';
    fl.frequency.value = 220;
    const traqueteo = ctx.createOscillator();
    traqueteo.frequency.value = 9;
    const prof = ctx.createGain();
    prof.gain.value = 0.35;
    this.gBanda = ctx.createGain();
    this.gBanda.gain.value = 0;
    const mod = ctx.createGain();
    mod.gain.value = 0.65;
    traqueteo.connect(prof).connect(mod.gain);
    o.connect(fl).connect(mod).connect(this.gBanda).connect(this.maestro);
    o.start();
    traqueteo.start();
  }

  /** Enciende o apaga el zumbido de la banda. */
  banda(si) {
    if (!this.ctx || this._bandaSi === si) return;
    this._bandaSi = si;
    this.gBanda.gain.setTargetAtTime(si ? 0.09 : 0, this.ctx.currentTime, 0.12);
  }
}

export const sonido = new Sonido();
