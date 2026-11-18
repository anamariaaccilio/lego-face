import '@fontsource/fredoka/400.css';
import '@fontsource/fredoka/500.css';
import '@fontsource/fredoka/600.css';
import './estilos.css';
import * as THREE from 'three';
import { api, ErrorApi } from './api.js';
import { crearRecorte } from './recorte.js';
import { Cabeza } from './escena/minifig.js';
import { Mundo } from './escena/mundo.js';
import { descargar, glbCabeza, imagenCabeza } from './exportar.js';
import { sonido } from './sonido.js';
import { cargarCatalogo, COLORES_CABELLO } from './escena/cabello.js';

const $ = (s) => document.querySelector(s);

/* ---------------- sonido ---------------- */

// El audio solo puede arrancar tras un gesto del usuario.
for (const ev of ['pointerdown', 'keydown']) window.addEventListener(ev, () => sonido.activar(), { capture: true });
document.addEventListener('click', (ev) => {
  const b = ev.target.closest('button');
  if (b && !b.disabled && !b.closest('.decide') && b.id !== 'sonido') sonido.clic();
});
const botonSonido = $('#sonido');
function pintarSonido() {
  botonSonido.textContent = sonido.silencio ? '🔇' : '🔊';
  botonSonido.setAttribute('aria-label', sonido.silencio ? 'Activar sonido' : 'Silenciar');
  botonSonido.setAttribute('aria-pressed', String(sonido.silencio));
}
botonSonido.addEventListener('click', () => {
  sonido.ponerSilencio(!sonido.silencio);
  pintarSonido();
});
pintarSonido();

/** Crea un elemento: h('button.ladrillo.rojo', { onclick }, 'Texto') */
function h(sel, attrs = {}, ...hijos) {
  const [tag, ...clases] = sel.split('.');
  const el = document.createElement(tag || 'div');
  if (clases.length) el.className = clases.join(' ');
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'style') Object.assign(el.style, v);
    else if (v === true) el.setAttribute(k, '');
    else el.setAttribute(k, v);
  }
  for (const c of hijos.flat()) if (c != null && c !== false) el.append(c.nodeType ? c : String(c));
  return el;
}

const mundo = new Mundo($('#escena'));
const tito = mundo.tito;
tito.onPaso = () => sonido.paso();
mundo.alActualizar.push(() => {
  sonido.banda(mundo.linea.mueve);
  if (mundo.linea.espera) sonido.esperando();
});

const est = {
  sesion: null,
  info: null,
  generador: null,
  opciones: {},
  ronda: null,
  caras: [],
  decisiones: {},
  porPaquete: false,
  aprobadas: [], // de todas las rondas: { id, imagen, img }
  favorita: null,
  resumidor: null,
  foto: null,
};

/* ---------------- globo de diálogo ---------------- */

const globo = $('#globo');
const globoTexto = $('#globo .texto');
let tipeo = null;

function decir(texto) {
  if (tipeo) tipeo.cancelar();
  globo.hidden = false;
  globo.classList.remove('entra');
  void globo.offsetWidth;
  globo.classList.add('entra');
  globoTexto.textContent = '';
  tito.hablar(true);
  return new Promise((resolve) => {
    let i = 0;
    const vel = texto.length > 220 ? 90 : 42;
    let ultimo = performance.now();
    let vivo = true;
    const terminar = () => {
      vivo = false;
      globoTexto.textContent = texto;
      tito.hablar(false);
      tipeo = null;
      resolve();
    };
    tipeo = { cancelar: terminar };
    const paso = (ahora) => {
      if (!vivo) return;
      const antes = Math.floor(i);
      i = Math.min(texto.length, i + ((ahora - ultimo) / 1000) * vel);
      ultimo = ahora;
      if (Math.floor(i) > antes && /\w/.test(texto[Math.floor(i) - 1] || '')) sonido.voz();
      globoTexto.textContent = texto.slice(0, Math.floor(i));
      if (i >= texto.length) terminar();
      else requestAnimationFrame(paso);
    };
    requestAnimationFrame(paso);
  });
}
globo.addEventListener('click', () => tipeo?.cancelar());

const ancla = new THREE.Vector3();
mundo.alActualizar.push(() => {
  if (globo.hidden) return;
  const p = mundo.enPantalla(tito.puntoGlobo(ancla));
  const ancho = window.innerWidth;
  const movil = ancho < 720;
  const dentro = p && p.x > 40 && p.x < ancho - 40 && p.y > 60;
  if (!movil && dentro) {
    globo.classList.add('flotante');
    const w = globo.offsetWidth;
    // no montarse sobre el panel lateral
    const tope = !panel.hidden && panel.classList.contains('derecha') ? panel.getBoundingClientRect().left - 16 : ancho - 16;
    const x = Math.min(Math.max(p.x - 34, 16), tope - w);
    globo.style.left = `${x}px`;
    globo.style.top = `${Math.max(p.y, globo.offsetHeight + 80)}px`;
    globo.style.setProperty('--cola', `${Math.min(Math.max(p.x - x, 24), w - 24)}px`);
  } else {
    globo.classList.remove('flotante');
    globo.style.left = '';
    globo.style.top = '';
  }
});

/* ---------------- panel ---------------- */

const panel = $('#panel');
function mostrar(contenido, { lado = 'abajo', ancho = false } = {}) {
  panel.replaceChildren(...[contenido].flat().filter((x) => x != null && x !== false));
  panel.className = `panel ${lado}${ancho ? ' ancho' : ''}`;
  panel.hidden = false;
  panel.classList.remove('entra');
  void panel.offsetWidth;
  panel.classList.add('entra');
}
function ocultarPanel() {
  panel.hidden = true;
}
const boton = (texto, color, onclick, extra = {}) => h(`button.ladrillo.${color}`, { onclick, ...extra }, texto);
const fila = (...b) => h('div.fila', {}, ...b);

/* ---------------- pasos visibles ---------------- */

const PASOS = ['foto', 'maquina', 'fabricando', 'control', 'resumen'];
function paso(nombre) {
  const i = PASOS.indexOf(nombre);
  const etiqueta = document.querySelectorAll('#pasos li')[1];
  if (etiqueta) etiqueta.textContent = est.modo === 'asesoria' ? 'Asesoría' : 'Máquina';
  document.querySelectorAll('#pasos li').forEach((li, j) => {
    li.classList.toggle('hecho', i > j);
    li.classList.toggle('actual', i === j);
  });
}

/* ---------------- estado de la máquina ---------------- */

const luzEstado = $('#estado');
async function revisarEstado() {
  try {
    est.info = await api.estado();
    const g = est.info.generadores.find((x) => x.disponible);
    if (g || est.info.cabello_foto) {
      luzEstado.className = 'estado listo';
      luzEstado.textContent = 'Máquina lista';
    } else {
      luzEstado.className = 'estado calentando';
      luzEstado.textContent = 'Calentando motores';
    }
  } catch {
    luzEstado.className = 'estado apagado';
    luzEstado.textContent = 'Sin conexión';
  }
  return est.info;
}
revisarEstado();
setInterval(revisarEstado, 5000);

/* ---------------- utilidades ---------------- */

function cargarImagen(src) {
  return new Promise((ok, mal) => {
    const i = new Image();
    i.onload = () => ok(i);
    i.onerror = mal;
    i.src = src;
  });
}

function miniatura(src, clase = '') {
  return h(`div.mini${clase ? '.' + clase : ''}`, {}, h('img', { src, alt: '' }));
}

async function fallaServidor(e, reintento) {
  const sinConexion = e instanceof ErrorApi && e.status === 0;
  decir(sinConexion ? 'La máquina no responde. Revisa que el servidor esté encendido.' : `Algo salió mal: ${e.message}.`);
  mostrar(fila(boton('Reintentar', 'rojo', reintento), boton('Volver al inicio', 'blanco', reiniciar)));
}

/* ---------------- 1. recepción ---------------- */

async function inicio() {
  paso(null);
  globo.hidden = true;
  ocultarPanel();
  await mundo.irA('recepcion');
  tito.saludar();
  decir('¡Hola! Soy Tito. En esta fábrica convierto tu cara en una pieza LEGO. ¿Vamos directo a la máquina o prefieres que te asesore?');
  mostrar(fila(
    boton('Fabricar con la máquina', 'rojo', () => consentimiento('maquina')),
    boton('Quiero asesoría', 'azul', () => consentimiento('asesoria')),
  ));
}

function consentimiento(modo) {
  est.modo = modo;
  decir('Antes de empezar: tu foto solo sirve para fabricar tus caras. No la guardo y se borra cuando terminas.');
  mostrar([
    h('p.nota', {}, 'Si aceptas, la foto se procesa en este equipo. Lo que se guarda es tu decisión sobre cada cara, sin la foto.'),
    fila(
      boton('Acepto', 'verde', async () => {
        try {
          est.sesion = (await api.crearSesion(modo)).sesion;
          if (modo === 'asesoria') asesoria();
          else {
            est.trasFoto = elegirMaquina;
            tomarFoto();
          }
        } catch (e) {
          fallaServidor(e, () => consentimiento(modo));
        }
      }),
      boton('Mejor no', 'blanco', () => {
        decir('Sin foto no puedo fabricar nada. Si cambias de idea, aquí estoy.');
        mostrar(fila(boton('Volver al inicio', 'blanco', inicio)));
      }),
    ),
  ]);
}

/* ---------------- 2. cabina de fotos ---------------- */

const video = $('#video');
let flujo = null;

async function encenderCamara() {
  if (flujo) return true;
  try {
    flujo = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    video.srcObject = flujo;
    await video.play();
    if (!video.videoWidth) await new Promise((r) => video.addEventListener('loadedmetadata', r, { once: true }));
    return true;
  } catch {
    flujo = null;
    return false;
  }
}

function apagarCamara() {
  flujo?.getTracks().forEach((t) => t.stop());
  flujo = null;
}

async function tomarFoto() {
  paso('foto');
  ocultarPanel();
  mundo.irA('foto');
  const hay = await encenderCamara();
  const sinFoto = est.modo === 'asesoria' ? boton('Seguir sin foto', 'blanco', () => { apagarCamara(); asesoria(); }) : null;
  if (hay) {
    mundo.cabina.mostrarVideo(video);
    decir('Mira a la cámara y acomoda tu cara dentro del óvalo.');
    mostrar(fila(boton('Tomar foto', 'rojo', cuentaRegresiva), botonSubir(), sinFoto));
  } else {
    mundo.cabina.apagar();
    decir('No puedo usar la cámara. Sube una foto donde se vea bien tu cara.');
    mostrar(fila(botonSubir('rojo'), sinFoto));
  }
}

function botonSubir(color = 'blanco') {
  const input = h('input', { type: 'file', accept: 'image/jpeg,image/png,image/webp', hidden: true });
  input.addEventListener('change', async () => {
    const f = input.files[0];
    if (!f) return;
    try {
      const bmp = await createImageBitmap(f, { imageOrientation: 'from-image' });
      const c = lienzoDe(bmp, bmp.width, bmp.height);
      bmp.close();
      vistaPrevia(c, false);
    } catch {
      decir('No pude abrir ese archivo. Prueba con una foto JPG o PNG.');
    }
  });
  const b = boton('Subir una foto', color, () => input.click());
  return h('span', {}, b, input);
}

function lienzoDe(fuente, w, h0) {
  const k = Math.min(1, 1280 / Math.max(w, h0));
  const c = document.createElement('canvas');
  c.width = Math.round(w * k);
  c.height = Math.round(h0 * k);
  c.getContext('2d').drawImage(fuente, 0, 0, c.width, c.height);
  return c;
}

async function cuentaRegresiva() {
  ocultarPanel();
  const cuenta = $('#cuenta');
  for (const n of ['3', '2', '1']) {
    cuenta.textContent = n;
    sonido.bip(n === '1');
    cuenta.hidden = false;
    cuenta.classList.remove('late');
    void cuenta.offsetWidth;
    cuenta.classList.add('late');
    await new Promise((r) => setTimeout(r, 800));
  }
  cuenta.hidden = true;
  mundo.cabina.disparar();
  sonido.obturador();
  const fl = $('#flash');
  fl.classList.remove('dispara');
  void fl.offsetWidth;
  fl.classList.add('dispara');
  vistaPrevia(lienzoDe(video, video.videoWidth, video.videoHeight), true);
}

function vistaPrevia(canvas, espejo) {
  mundo.cabina.mostrarFoto(canvas, espejo);
  const recorte = crearRecorte(canvas, espejo);
  const confirmar = () => {
    est.foto = recorte.aplicar();
    enviarFoto(ajustar);
  };
  function ajustar(mensaje = 'Incluye toda la cabeza y el cabello.') {
    decir('Ajusta tu foto');
    mostrar([
      h('p.nota', {}, mensaje),
      recorte.vista,
      h('p.nota', {}, 'Arrastra el recuadro para moverlo y las esquinas para cambiar su tamaño.'),
      fila(boton('Usar esta', 'verde', confirmar),
        boton('Foto completa', 'blanco', recorte.restablecer),
        boton('Otra foto', 'blanco', tomarFoto)),
    ]);
    panel.classList.add('ajuste-foto');
  }
  ajustar();
}

async function enviarFoto(ajustar) {
  decir('Déjame revisarla…');
  mostrar(fila(boton('Revisando…', 'blanco', null, { disabled: true })));
  const blob = await new Promise((r) => est.foto.toBlob(r, 'image/jpeg', 0.92));
  try {
    await api.subirFoto(est.sesion, blob);
    apagarCamara();
    est.tieneFoto = true;
    est.verCabelloFoto = false;
    if (est.peinado?.malla) elegirPeinado(null);
    (est.trasFoto || elegirMaquina)();
  } catch (e) {
    if (e instanceof ErrorApi && e.status === 422) {
      ajustar(e.message);
    } else if (e instanceof ErrorApi && e.status === 404) {
      decir('Pasó mucho tiempo y se cerró la sesión. Empecemos de nuevo.');
      mostrar(fila(boton('Empezar', 'rojo', reiniciar)));
    } else {
      fallaServidor(e, () => enviarFoto(ajustar));
    }
  }
}

/* ---------------- 2b. asesoría con Tito ---------------- */

const FEM = { feliz: 'feliz', serio: 'seria', sorprendido: 'sorprendida', enojado: 'enojada' };
const fichaVacia = () => ({
  rasgos: { lentes: null, barba: null, bigote: null, expresion: null },
  cabello: { color: null, largo: null },
  ojos: null,
  detalles: '',
});

const PREGUNTAS = [
  {
    id: 'expresion',
    texto: '¿Cómo quieres que se vea tu cara?',
    chips: [['Feliz', { expresion: 'feliz' }], ['Seria', { expresion: 'serio' }], ['Sorprendida', { expresion: 'sorprendido' }], ['Enojada', { expresion: 'enojado' }]],
  },
  { id: 'lentes', texto: '¿Usas lentes?', chips: [['Sí', { lentes: true }], ['No', { lentes: false }]] },
  {
    id: 'vello',
    texto: '¿Barba o bigote?',
    chips: [['Barba', { barba: true, bigote: false }], ['Bigote', { barba: false, bigote: true }], ['Las dos', { barba: true, bigote: true }], ['Ninguna', { barba: false, bigote: false }]],
  },
  {
    id: 'peinado',
    texto: '¿Cómo es tu peinado? Mira el maniquí del escritorio: te lo voy probando.',
    chips: () => [...(catalogoCabello || []).map((p) => [p.nombre, { peinado: p.id }]), ['Sin cabello', { peinado: null }]],
  },
  {
    id: 'color',
    texto: '¿De qué color? Pinto el cabello y las cejas.',
    chips: () => COLORES_CABELLO.map((c) => [c.nombre, { color: c.id }, c.hex]),
  },
  {
    id: 'ojos',
    texto: '¿Y tus ojos? Las caras LEGO suelen llevar ojos negros, pero puedo darles color.',
    chips: [['Negros, como LEGO', { ojos: null }], ['Café', { ojos: 'cafe' }], ['Verdes', { ojos: 'verdes' }], ['Azules', { ojos: 'azules' }], ['Grises', { ojos: 'grises' }]],
  },
  {
    id: 'detalles',
    texto: '¿Algo más que quieras contarme de tu cara? Pecas, una ceja levantada, lo que se te ocurra.',
    chips: [['Nada más', {}]],
  },
];

function aplicar(cambio) {
  const f = est.ficha;
  for (const k of ['lentes', 'barba', 'bigote', 'expresion']) if (k in cambio) f.rasgos[k] = cambio[k];
  if ('peinado' in cambio) elegirPeinado(cambio.peinado);
  if ('color' in cambio) pintarCabello(cambio.color);
  if ('ojos' in cambio) f.ojos = cambio.ojos;
}

/* ---------------- cabello (piezas de LDraw) ---------------- */

let catalogoCabello = null;
cargarCatalogo().then((c) => (catalogoCabello = c)).catch(() => (catalogoCabello = []));

const PEINADO_POR_LARGO = { corto: '3901', medio: '62711', largo: '40251' };
const PALABRAS_CABELLO = /\b(pelo|cabello|peinado|melena|cerquillo|flequillo|rulos|rizos|rizado|calv[oa]|rapad[oa]|trenza\w*|cola de caballo|moño|chasquilla)\b/i;
const COLOR_LIBRE = [
  ['rosa', /\b(rosad?[oa]?|fucsia|chicle)\b/i], ['azul', /\b(azul|celeste)\b/i], ['morado', /\b(morad[oa]|lila|violeta|purpura)\b/i],
  ['verde', /\bverde\b/i], ['rubio', /\b(rubi[oa]|amarill[oa]|dorad[oa])\b/i], ['pelirrojo', /\b(pelirroj[oa]|roj[oa]|naranja)\b/i],
  ['castaño', /\b(castañ[oa]|marr[oó]n|caf[eé])\b/i], ['negro', /\b(negr[oa]|oscur[oa])\b/i], ['gris', /\b(gris|canos[oa]|canas)\b/i],
  ['blanco', /\b(blanc[oa]|platinad[oa])\b/i],
];

function elegirPeinado(id) {
  const p = catalogoCabello?.find((x) => x.id === id);
  est.peinado = p ? { id: p.id, nombre: p.nombre, color: est.peinado?.color || est.ficha?.cabello.color || 'castaño' } : null;
  if (est.ficha) est.ficha.cabello.largo = p?.largo || null;
  mundo.oficina.mostrarPeinado(est.peinado);
}

// La primera foto puede incluir la carga de los pesos. Las siguientes usan el tiempo medido.
let segundosCabello = 20;
let modeloCabelloCaliente = false;
const segundosRonda = { completa: 45, caras: 30 };

function relojCabello(estimacionInicial = null, alMedir = null) {
  const texto = h('span', {}, '0%');
  const circulo = h('div.reloj-cabello', {
    role: 'progressbar', 'aria-label': 'Progreso estimado de la generación',
    'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': 0, hidden: true,
  }, texto);
  let inicio;
  let estimacion;
  let intervalo;
  function pintar(completo = false) {
    const transcurrido = (performance.now() - inicio) / 1000;
    const restante = Math.ceil(estimacion - transcurrido);
    const avance = completo ? 100 : Math.min(95, Math.floor(100 * transcurrido / estimacion));
    const etiqueta = completo ? 'Listo' : restante > 0 ? `~${restante} s` : '…';
    circulo.style.setProperty('--avance', `${avance}%`);
    circulo.setAttribute('aria-valuenow', avance);
    circulo.setAttribute('aria-valuetext', etiqueta);
    circulo.title = `${avance}% · ${etiqueta}`;
    texto.textContent = etiqueta;
  }
  return {
    circulo,
    iniciar() {
      inicio = performance.now();
      estimacion = estimacionInicial ?? segundosCabello;
      circulo.hidden = false;
      pintar();
      intervalo = setInterval(pintar, 150);
    },
    terminar(exito) {
      clearInterval(intervalo);
      if (!exito) {
        circulo.hidden = true;
        return;
      }
      const real = (performance.now() - inicio) / 1000;
      if (estimacionInicial != null) {
        alMedir?.(real);
        pintar(true);
        return;
      }
      if (!modeloCabelloCaliente) {
        modeloCabelloCaliente = true;
        segundosCabello = Math.max(3, Math.min(15, real / 2));
      } else if (real >= 0.6) {
        segundosCabello = Math.max(1, segundosCabello * 0.35 + real * 0.65);
      }
      pintar(true);
    },
  };
}

function botonCabelloFoto(alElegir) {
  if (!est.tieneFoto) return h('p.nota', {}, 'Sube una foto para generar tu cabello.');
  const reloj = relojCabello();
  const estado = h('p.nota', { role: 'status', hidden: true });
  const accion = boton('Desde mi foto', 'verde', async () => {
    if (est.info?.cabello_foto !== true) {
      estado.hidden = false;
      estado.textContent = 'El servidor no detecta el modelo de cabello. Reinícialo desde el proyecto actualizado y revisa interfaz/modelos_cabello.';
      return;
    }
    if (est.generandoCabello) return;
    const sid = est.sesion;
    reloj.iniciar();
    est.generandoCabello = true;
    accion.disabled = true;
    estado.hidden = false;
    estado.textContent = 'Generando cabello 3D…';
    try {
      const malla = await api.cabello(sid);
      reloj.terminar(true);
      await new Promise((resolve) => setTimeout(resolve, 250));
      if (est.sesion !== sid || !accion.isConnected) return;
      est.peinado = {
        id: 'desde-foto', nombre: 'Cabello desde foto',
        color: est.peinado?.color || est.ficha?.cabello.color || 'castaño',
        malla,
      };
      if (est.ficha) est.ficha.cabello.largo = null;
      est.verCabelloFoto = true;
      mundo.oficina.mostrarPeinado(est.peinado);
      alElegir();
    } catch (e) {
      reloj.terminar(false);
      if (est.sesion === sid && accion.isConnected) estado.textContent = e.message;
    } finally {
      if (est.sesion === sid) est.generandoCabello = false;
      accion.disabled = false;
    }
  });
  return h('div', {}, h('div.reloj-cabello-fila', {}, accion, reloj.circulo), estado);
}

function pintarCabello(color) {
  if (est.ficha) est.ficha.cabello.color = color;
  if (est.peinado) est.peinado = { ...est.peinado, color };
  mundo.oficina.mostrarPeinado(est.peinado);
}

/** Lee color y largo de un texto que habla del pelo. Devuelve qué entendió, o ''. */
function cabelloDeTexto(texto, r) {
  const partes = [];
  const color = r?.cabello?.color || COLOR_LIBRE.find(([, re]) => re.test(texto))?.[0];
  const largo = r?.cabello?.largo || (/\b(larg[oa]|melena)\b/i.test(texto) ? 'largo' : /\bcort[oa]\b/i.test(texto) ? 'corto' : /\b(medi[oa]|mediano)\b/i.test(texto) ? 'medio' : null);
  if (/\b(calv[oa]|sin (pelo|cabello)|rapad[oa])\b/i.test(texto)) {
    elegirPeinado(null);
    return 'sin cabello';
  }
  if (largo && (!est.peinado || catalogoCabello?.find((x) => x.id === est.peinado.id)?.largo !== largo)) {
    elegirPeinado(PEINADO_POR_LARGO[largo]);
    partes.push(`cabello ${largo}`);
  }
  if (color) {
    if (!est.peinado) elegirPeinado(PEINADO_POR_LARGO.corto);
    pintarCabello(color);
    partes.push(`cabello ${color}`);
  }
  return partes.join(' y ');
}

/** Saca del texto las partes que hablan del pelo (eso va a la pieza 3D, no a FLUX). */
function sinCabello(texto) {
  return texto.split(/[.;,]| y /).map((s) => s.trim()).filter((s) => s && !PALABRAS_CABELLO.test(s)).join(', ');
}

function valoresPizarra() {
  const f = est.ficha || fichaVacia();
  const r = f.rasgos;
  const sino = (v) => (v == null ? null : v ? 'sí' : 'no');
  const vello = r.barba == null && r.bigote == null ? null : [r.barba ? 'barba' : null, r.bigote ? 'bigote' : null].filter(Boolean).join(' y ') || 'ninguno';
  return {
    foto: est.tieneFoto ? 'sí' : est.preguntoFoto ? 'no' : null,
    expresion: r.expresion ? FEM[r.expresion] : null,
    lentes: sino(r.lentes),
    vello,
    cabello: est.peinado ? `${est.peinado.nombre}, ${est.peinado.color}` : est.preguntoPeinado ? 'sin cabello' : f.cabello.color,
    ojos: f.ojos === 'cafe' ? 'café' : f.ojos,
    detalles: f.detalles || null,
  };
}

function actualizarPizarra() {
  mundo.oficina.dibujar(valoresPizarra(), est.tieneFoto ? est.foto : null);
}

/** Lo que entendió el agente, en palabras: "lentes y expresión seria". */
function describirPedido(p) {
  const partes = [];
  for (const k of ['lentes', 'barba', 'bigote']) {
    if (p.rasgos[k] === true) partes.push(`con ${k}`);
    if (p.rasgos[k] === false) partes.push(`sin ${k}`);
  }
  if (p.rasgos.expresion) partes.push(`expresión ${FEM[p.rasgos.expresion]}`);
  if (p.cabello.color) partes.push(`cabello ${p.cabello.color}`);
  if (p.cabello.largo) partes.push(`cabello ${p.cabello.largo}`);
  return partes.length < 2 ? partes.join('') : partes.slice(0, -1).join(', ') + ' y ' + partes.at(-1);
}

const ACUSES = ['Anotado.', 'Perfecto.', 'Listo, lo apunto.', 'Me gusta.'];
const acuse = () => ACUSES[Math.floor(Math.random() * ACUSES.length)];

function asesoria() {
  clearInterval(vigilaEstado);
  est.generador = 'flux_klein';
  paso('maquina');
  if (!est.ficha) est.ficha = fichaVacia();
  mundo.irA('asesoria', { panelLateral: true });
  actualizarPizarra();
  if (!est.preguntoFoto && est.tieneFoto) {
    est.preguntoFoto = true;
    actualizarPizarra();
    tito.saludar();
    preguntar(0, 'Esta es la oficina de diseño. Ya tengo tu foto, así que vamos con unas preguntas. ');
  } else if (!est.preguntoFoto) {
    est.preguntoFoto = true;
    tito.saludar();
    decir('Esta es la oficina de diseño. Para empezar, ¿me mandas una foto tuya? Con ella tu cara LEGO se te parece más.');
    mostrar(
      [
        h('h2', {}, 'Tu foto'),
        h('p.nota', {}, 'Es opcional. Sin foto, armo la cara solo con lo que me cuentes.'),
        boton('Tomar o subir una foto', 'rojo', () => {
          est.trasFoto = () => {
            paso('maquina');
            mundo.irA('asesoria', { panelLateral: true });
            actualizarPizarra();
            preguntar(0, '¡Buena foto! ');
          };
          tomarFoto();
        }),
        boton('Seguir sin foto', 'blanco', () => {
          actualizarPizarra();
          preguntar(0, 'Sin problema. ');
        }),
      ],
      { lado: 'derecha' },
    );
    panel.dataset.vista = 'asesoria';
  } else {
    actualizarPizarra();
    preguntar(0, '');
  }
}

function preguntar(i, antes) {
  if (i >= PREGUNTAS.length) return revisarFicha(antes);
  const q = PREGUNTAS[i];
  decir(antes + q.texto);
  const campo = h('input.texto-libre', { type: 'text', maxlength: 300, placeholder: 'O escríbelo con tus palabras' });
  const enviar = async () => {
    const texto = campo.value.trim();
    if (!texto) return;
    campo.disabled = true;
    try {
      await responderLibre(i, texto);
    } finally {
      campo.disabled = false;
    }
  };
  campo.addEventListener('keydown', (ev) => ev.key === 'Enter' && enviar());
  mostrar(
    [
      h('h2', {}, `Pregunta ${i + 1} de ${PREGUNTAS.length}`),
      h('p.pregunta', {}, q.texto),
      h('div.respuestas', {}, (typeof q.chips === 'function' ? q.chips() : q.chips).map(([etq, cambio, hex]) => h('button.opcion.corta', {
        onclick: () => {
          if (q.id === 'peinado') est.preguntoPeinado = true;
          aplicar(cambio);
          actualizarPizarra();
          preguntar(i + 1, `${acuse()} `);
        },
        onpointerenter: q.id === 'peinado' ? () => mundo.oficina.mostrarPeinado(cambio.peinado ? { id: cambio.peinado, color: est.peinado?.color || 'castaño' } : null) : null,
        onpointerleave: q.id === 'peinado' ? () => mundo.oficina.mostrarPeinado(est.peinado) : null,
      }, hex ? h('span.muestra', { style: { background: hex } }) : null, h('strong', {}, etq)))),
      q.id === 'peinado' ? botonCabelloFoto(() => {
        est.preguntoPeinado = true;
        actualizarPizarra();
        preguntar(i + 1, 'Ya tengo tu peinado. ');
      }) : null,
      h('div.libre', {}, campo, boton('Enviar', 'blanco', enviar)),
      h('div.pie.dos', {},
        i > 0 ? boton('Atrás', 'blanco', () => preguntar(i - 1, '')) : null,
        boton('Saltar', 'blanco', () => preguntar(i + 1, ''))),
    ],
    { lado: 'derecha' },
  );
  panel.dataset.vista = 'asesoria';
  setTimeout(() => campo.focus({ preventScroll: true }), 50);
}

async function responderLibre(i, texto) {
  const q = PREGUNTAS[i];
  let r;
  try {
    r = await api.interpretar(est.sesion, texto, q.id);
  } catch (e) {
    return fallaServidor(e, () => preguntar(i, ''));
  }
  if (!r.permitido) {
    decir(r.motivo);
    return;
  }
  // el agente entiende lentes, barba, bigote y expresión; el pelo va a la pieza 3D; ojos y detalles los leo aquí
  for (const k of ['lentes', 'barba', 'bigote', 'expresion']) if (r.rasgos[k] != null) est.ficha.rasgos[k] = r.rasgos[k];
  const hablaDePelo = PALABRAS_CABELLO.test(texto) || ['peinado', 'color'].includes(q.id);
  const pelo = hablaDePelo || r.cabello.color || r.cabello.largo ? cabelloDeTexto(texto, r) : '';
  if (q.id === 'peinado') est.preguntoPeinado = true;
  let entendido = [describirPedido({ ...r, cabello: { color: null, largo: null } }), pelo].filter(Boolean).join(' y ');
  if (q.id === 'ojos') {
    const t = texto.toLowerCase();
    const ojos = /verde/.test(t) ? 'verdes' : /azul/.test(t) ? 'azules' : /gris/.test(t) ? 'grises' : /caf|marr|casta/.test(t) ? 'cafe' : null;
    if (ojos) {
      est.ficha.ojos = ojos;
      entendido = entendido || `ojos ${ojos === 'cafe' ? 'café' : ojos}`;
    }
  }
  if (q.id === 'detalles') {
    const resto = sinCabello(texto); // lo del pelo ya está en la pieza; a FLUX solo va el resto
    if (resto) est.ficha.detalles = [est.ficha.detalles, resto].filter(Boolean).join('; ').slice(0, 300);
    entendido = [entendido, resto ? `"${resto}"` : ''].filter(Boolean).join(' y ');
  }
  actualizarPizarra();
  if (!entendido) {
    decir('No te entendí bien. Elige una opción o dilo de otra forma.');
    return;
  }
  preguntar(i + 1, `Entendí: ${entendido}. `);
}

function revisarFicha(antes = '') {
  const g = est.info?.generadores.find((x) => x.id === 'flux_klein');
  const listo = g?.disponible;
  decir(antes + (listo ? 'Esta es tu ficha. ¿La mando a fabricar?' : 'Esta es tu ficha. La máquina de asesoría todavía se está preparando.'));
  const v = valoresPizarra();
  const filas = [['Foto', v.foto], ['Expresión', v.expresion], ['Lentes', v.lentes], ['Barba / bigote', v.vello],
    ['Cabello', v.cabello], ['Ojos', v.ojos], ['Detalles', v.detalles]];
  const alterno = est.info?.generadores.find((x) => x.id === 'lego_face' && x.disponible);
  mostrar(
    [
      h('h2', {}, 'Tu ficha'),
      h('dl.ficha', {}, filas.flatMap(([k, x]) => [h('dt', {}, k), h('dd', {}, x || '—')])),
      g && !listo && g.detalle && !g.detalle.startsWith('cargando') ? h('p.nota', {}, `FLUX.2 no está disponible: ${g.detalle}`) : null,
      h('div.pie.dos', {},
        boton('Cambiar respuestas', 'blanco', () => preguntar(0, '')),
        boton(listo ? 'Fabricar 5 caras' : 'Preparando…', 'rojo', () => {
          est.generador = 'flux_klein';
          est.opciones = { ficha: est.ficha };
          fabricar('nueva');
        }, { disabled: !listo })),
      !listo && alterno && est.tieneFoto ? boton('Usar el modelo entrenado', 'blanco', () => cambiarMetodo(alterno)) : null,
    ],
    { lado: 'derecha' },
  );
  panel.dataset.vista = 'ficha';
  clearInterval(vigilaEstado);
  if (!listo) {
    vigilaEstado = setInterval(async () => {
      await revisarEstado();
      if (panel.dataset.vista === 'ficha' && est.info?.generadores.find((x) => x.id === 'flux_klein')?.disponible) {
        clearInterval(vigilaEstado);
        revisarFicha('');
      }
    }, 3000);
  }
}

/* ---------------- 3. máquina: método y opciones ---------------- */

let vigilaEstado = null;

async function elegirMaquina() {
  paso('maquina');
  mundo.irA('maquina', { panelLateral: true });
  decir('Elige cómo quieres que la máquina haga tus caras.');
  const info = est.info || (await revisarEstado());
  if (!info) return fallaServidor(new ErrorApi('sin conexión', 0), elegirMaquina);
  if (!est.generador || !info.generadores.find((g) => g.id === est.generador && g.disponible)) {
    est.generador = (info.generadores.find((g) => g.disponible) || info.generadores[0]).id;
  }
  dibujarMaquina();
  clearInterval(vigilaEstado);
  vigilaEstado = setInterval(async () => {
    const firma = () => JSON.stringify([est.info?.generadores, est.info?.cabello_foto]);
    const antes = firma();
    await revisarEstado();
    if (firma() !== antes && !est.generandoCabello && !panel.hidden && panel.dataset.vista === 'maquina') dibujarMaquina();
  }, 2500);
}

function dibujarMaquina() {
  const gens = est.info.generadores;
  const g = gens.find((x) => x.id === est.generador);
  const metodos = h(
    'div.opciones',
    { role: 'radiogroup', 'aria-label': 'Método' },
    gens.map((x) =>
      h(
        'button.opcion',
        {
          role: 'radio',
          'aria-checked': String(x.id === est.generador),
          disabled: !x.disponible,
          onclick: () => {
            est.generador = x.id;
            est.opciones = {};
            dibujarMaquina();
          },
        },
        h('strong', {}, x.nombre),
        h('span', {}, x.disponible ? x.descripcion : `No disponible: ${x.detalle}`),
      ),
    ),
  );
  const campos = (g?.opciones || []).map((op) => {
    if (op.tipo === 'texto') {
      const ta = h('textarea', { rows: 3, placeholder: op.ayuda || '', maxlength: 300 }, est.opciones[op.id] || '');
      ta.addEventListener('input', () => (est.opciones[op.id] = ta.value));
      return h('label.campo', {}, h('span.etiqueta', {}, op.nombre), ta);
    }
    const actual = est.opciones[op.id] ?? op.defecto;
    return h(
      'div.campo',
      {},
      h('span.etiqueta', {}, op.nombre),
      h(
        'div.segmentos',
        { role: 'radiogroup', 'aria-label': op.nombre },
        op.valores.map((v) =>
          h(
            'button.segmento',
            {
              role: 'radio',
              'aria-checked': String(v.id === actual),
              onclick: () => {
                est.opciones[op.id] = v.id;
                dibujarMaquina();
              },
            },
            h('strong', {}, v.nombre),
            h('span', {}, v.descripcion),
          ),
        ),
      ),
    );
  });
  const listo = g?.disponible;
  let accion;
  if (g?.acepta_texto) {
    accion = boton('Ir a la asesoría', 'rojo', () => {
      est.modo = 'asesoria';
      asesoria();
    }, { disabled: !listo });
  } else if (g?.necesita_foto && !est.tieneFoto) {
    accion = boton('Primero tu foto', 'rojo', () => {
      est.trasFoto = elegirMaquina;
      tomarFoto();
    });
  } else {
    accion = boton(listo ? (g.id === 'lego_face' ? 'Generar 5 cabellos y 5 caras' : 'Fabricar 5 caras') : 'Calentando…', 'rojo', () => fabricar('nueva'), { disabled: !listo });
  }
  mostrar(
    [
      h('h2', {}, 'Método'),
      metodos,
      ...campos,
      g?.acepta_texto ? h('p.nota', {}, 'Con este método Tito te hace unas preguntas antes de fabricar.') : selectorPeinado(dibujarMaquina),
      h('div.pie', {}, accion),
    ],
    { lado: 'derecha' },
  );
  panel.dataset.vista = 'maquina';
}

/** Peinado y color como chips (panel de la máquina). */
function selectorPeinado(redibujar) {
  const actual = est.peinado?.id || null;
  const opciones = [['Sin cabello', null], ...(catalogoCabello || []).map((p) => [p.nombre, p.id])];
  return h('div.campo', {},
    h('span.etiqueta', {}, 'Peinado'),
    botonCabelloFoto(redibujar),
    est.peinado?.malla ? accionesCabelloFoto() : null,
    h('div.chips', { role: 'radiogroup', 'aria-label': 'Peinado' }, opciones.map(([nombre, id]) => h('button.chip', {
      role: 'radio',
      'aria-checked': String(id === actual),
      'aria-pressed': String(id === actual),
      onclick: () => {
        elegirPeinado(id);
        redibujar();
      },
    }, nombre))),
    est.peinado ? h('div.chips.colores', { role: 'radiogroup', 'aria-label': 'Color del cabello' }, COLORES_CABELLO.map((c) => h('button.color', {
      role: 'radio',
      title: c.nombre,
      'aria-label': c.nombre,
      'aria-checked': String(est.peinado.color === c.id),
      style: { background: c.hex },
      onclick: () => {
        pintarCabello(c.id);
        redibujar();
      },
    }))) : null,
  );
}

function accionesCabelloFoto() {
  const peinado = est.peinado;
  const sid = est.sesion;
  const vista = h('div', { role: 'status' });
  const vigente = () => est.sesion === sid && est.peinado === peinado && vista.isConnected;
  const ver = async () => {
    est.verCabelloFoto = true;
    try {
      const imagen = await imagenCabeza(null, peinado, 420);
      if (vigente()) vista.replaceChildren(h('img', {
        src: imagen, alt: 'Vista 3D del cabello sobre la cabeza', width: 170,
      }));
    } catch {
      if (vigente()) vista.textContent = 'No se pudo mostrar la vista 3D.';
    }
  };
  if (est.verCabelloFoto) queueMicrotask(ver);
  return h('div', {},
    h('p.nota', {}, 'Cabello generado desde tu foto'),
    est.verCabelloFoto ? null : boton('Ver en 3D', 'blanco', ver),
    boton('Descargar cabeza con cabello (.glb)', 'blanco', async () => {
      try {
        const glb = await glbCabeza(null, peinado);
        if (vigente()) descargar(glb, 'cabeza_con_cabello.glb');
      } catch {
        if (vigente()) vista.textContent = 'No se pudo exportar el archivo 3D.';
      }
    }),
    vista,
  );
}

/* ---------------- 4. línea de estampado ---------------- */

async function fabricar(modo, instruccion = null) {
  clearInterval(vigilaEstado);
  paso('fabricando');
  const linea = mundo.linea;
  est.rondaPeinado = est.peinado ? { ...est.peinado } : null;
  est.cabellosRonda = [];
  const muestrear = modo === 'nueva' && est.generador === 'lego_face';
  const tipoRonda = muestrear ? 'completa' : 'caras';
  const reloj = relojCabello(segundosRonda[tipoRonda], (real) => {
    segundosRonda[tipoRonda] = Math.max(2, real);
  });
  const fase = h('p.nota', { role: 'status' });
  const etapas = h('div.reloj-cabello-fila', {},
    boton('Generando…', 'verde', null, { disabled: true }), reloj.circulo);
  reloj.iniciar();
  mundo.irA('fabricando');
  decir(modo === 'variar' ? 'Conservo la forma de las que aceptaste y les cambio el color.' : 'Encendiendo la máquina…');

  const ranuras = Array.from({ length: 5 }, () => h('div.ranura'));
  const contador = h('span.contador', {}, '0 de 5');
  mostrar([etapas, fase, h('div.progreso', {}, h('div.ranuras', {}, ranuras), contador)]);
  panel.dataset.vista = 'fabricando';

  let estampadas = 0;
  linea.onEstampada = (k) => {
    sonido.prensa();
    estampadas++;
    contador.textContent = `${estampadas} de 5`;
    ranuras[k].classList.add('lista');
    ranuras[k].replaceChildren(h('img', { src: est.caras[k].imagen, alt: `Cara ${k + 1}` }));
  };
  const terminada = new Promise((r) => (linea.onFin = () => {
    sonido.listoRonda();
    r();
  }));

  try {
    if (muestrear) {
      fase.textContent = '1 de 2 · Calculando cabello…';
      decir('Calculando cabello…');
      const { variantes } = await api.cabellos(est.sesion);
      if (variantes.length !== 5) throw new Error('Se necesitan cinco variantes de cabello.');
      est.cabellosRonda = variantes.map(({ malla, semilla }, i) => ({
        id: 'desde-foto', nombre: `Cabello ${i + 1}`,
        color: est.rondaPeinado?.color || 'castaño', malla, semilla,
      }));
      fase.textContent = 'Cabello calculado · 2 de 2 · Calculando caras…';
      decir('Cabello calculado. Calculando caras…');
    } else {
      fase.textContent = 'Calculando caras…';
    }
    linea.iniciar(5, muestrear ? est.cabellosRonda : est.rondaPeinado);
    let recibidas = 0;
    const peinado = muestrear ? null : est.rondaPeinado;
    const opciones = { ...est.opciones, peinado: peinado && { id: peinado.id, nombre: peinado.nombre, color: peinado.color } };
    for await (const ev of api.ronda(est.sesion, { generador: est.generador, opciones, modo, instruccion })) {
      if (ev.tipo === 'inicio') {
        est.ronda = ev.ronda;
        est.caras = ev.caras.map((c) => ({ ...c }));
        est.decisiones = {};
        est.porPaquete = false;
        if (!muestrear && ev.explicacion) decir(ev.explicacion);
      } else if (ev.tipo === 'cara') {
        const i = est.caras.findIndex((c) => c.id === ev.id);
        est.caras[i].imagen = ev.imagen;
        est.caras[i].img = await cargarImagen(ev.imagen);
        linea.entregar(i, est.caras[i].img);
        recibidas++;
        fase.textContent = `${muestrear ? 'Cabello calculado · ' : ''}Caras: ${recibidas} de 5`;
      } else if (ev.tipo === 'error') {
        throw new ErrorApi(ev.mensaje, 500);
      }
    }
    if (recibidas !== 5) throw new Error('La generación terminó antes de recibir las cinco caras.');
    reloj.terminar(true);
  } catch (e) {
    reloj.terminar(false);
    linea.activo = false;
    if (e instanceof ErrorApi && e.status === 404) {
      decir('Se cerró la sesión por inactividad. Empecemos de nuevo.');
      return mostrar(fila(boton('Empezar', 'rojo', reiniciar)));
    }
    if (!muestrear && e instanceof ErrorApi && e.status === 422) {
      // el agente bloqueó el pedido: se explica y se puede escribir otro
      mundo.irA('control');
      return queSigue(e.message, instruccion);
    }
    return fallaServidor(e, () => fabricar(modo, instruccion));
  }
  await terminada;
  controlCalidad();
}

/* ---------------- 5. control de calidad ---------------- */

let tarjetas = [];

function controlCalidad() {
  paso('control');
  mundo.irA('control');
  mundo.control.cargar(est.caras.map((c) => c.img), est.cabellosRonda.length ? est.cabellosRonda : est.rondaPeinado);
  decir('Revisa cada cara. Acepta las que te gusten y rechaza las que no.');
  dibujarControl();
}

function seleccionar(i) {
  if (i != null) mundo.control.enfrentar(i);
  mundo.control.seleccion = i;
  tarjetas.forEach((t, j) => t.classList.toggle('sel', i === j));
  if (i != null) tarjetas[i].scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
}

function decidir(i, decision, porPaquete = false, conSonido = true) {
  if (conSonido) decision === 'aceptada' ? sonido.aprobar() : sonido.rechazar();
  const c = est.caras[i];
  const previo = est.decisiones[c.id];
  est.decisiones[c.id] = decision === 'rechazada'
    ? { decision, motivos: previo?.motivos || [], comentario: previo?.comentario || '' }
    : { decision, motivos: [], comentario: '' };
  est.porPaquete = porPaquete;
  mundo.control.decidir(i, decision);
}

function dibujarControl() {
  const motivos = est.info?.motivos || [];
  tarjetas = est.caras.map((c, i) => {
    const d = est.decisiones[c.id];
    return h(
      `div.tarjeta${d ? '.' + d.decision : ''}`,
      { onclick: () => seleccionar(i), tabindex: 0, 'aria-label': `Cara ${c.id}` },
      h('div.cab', {}, h('strong', {}, c.id), h('span', {}, c.origen)),
      h(
        'div.cuerpo',
        {},
        miniatura(c.imagen),
        h(
          'div.decide',
          {},
          h('button.si', {
            'aria-pressed': String(d?.decision === 'aceptada'),
            onclick: (ev) => { ev.stopPropagation(); decidir(i, 'aceptada'); dibujarControl(); seleccionar(i); },
          }, 'Aceptar'),
          h('button.no', {
            'aria-pressed': String(d?.decision === 'rechazada'),
            onclick: (ev) => { ev.stopPropagation(); decidir(i, 'rechazada'); dibujarControl(); seleccionar(i); },
          }, 'Rechazar'),
        ),
      ),
      d?.decision === 'rechazada'
        ? h(
            'div.motivos',
            {},
            motivos.map((m) =>
              h('button.chip', {
                'aria-pressed': String(d.motivos.includes(m)),
                onclick: (ev) => {
                  ev.stopPropagation();
                  d.motivos = d.motivos.includes(m) ? d.motivos.filter((x) => x !== m) : [...d.motivos, m];
                  dibujarControl();
                  seleccionar(i);
                },
              }, m),
            ),
            comentarioDe(d),
          )
        : null,
    );
  });
  const decididas = Object.keys(est.decisiones).length;
  const todas = (dec) => () => {
    est.caras.forEach((_, i) => decidir(i, dec, true, i === 0));
    dibujarControl();
  };
  mostrar(
    [
      h('div.tarjetas', {}, tarjetas),
      est.cabellosRonda.length ? boton('Ver las 25 combinaciones', 'azul', abrirCatalogoCombinaciones) : null,
      h(
        'div.barra',
        {},
        h('span.contador', {}, `${decididas} de 5 decididas`),
        h('div.fila', {},
          boton('Aceptar todas', 'blanco', todas('aceptada')),
          boton('Rechazar todas', 'blanco', todas('rechazada')),
          boton('Listo', 'rojo', guardarDecisiones, { disabled: decididas < 5 }),
        ),
      ),
    ],
    { ancho: true },
  );
  panel.dataset.vista = 'control';
  if (mundo.control.seleccion != null) tarjetas[mundo.control.seleccion]?.classList.add('sel');
}

/** Comentario libre al rechazar (hasta 200 caracteres). Se guarda sin redibujar, para no perder el foco. */
function comentarioDe(d) {
  const campo = h('input.comentario', { type: 'text', maxlength: 200, placeholder: 'Comentario (opcional)', 'aria-label': 'Comentario' });
  campo.value = d.comentario || '';
  campo.addEventListener('click', (ev) => ev.stopPropagation());
  campo.addEventListener('input', () => (d.comentario = campo.value));
  return campo;
}

async function abrirCatalogoCombinaciones() {
  const dialogo = h('dialog.catalogo-combinaciones', { 'aria-label': '25 combinaciones' });
  const estado = h('p.nota', { role: 'status' }, 'Preparando vistas…');
  const cuadricula = h('div.combinaciones-grid');
  const combinaciones = est.caras.flatMap((cara, i) => est.cabellosRonda.map((pelo, j) => ({
    cara, pelo, titulo: `Cara ${i + 1} · Cabello ${j + 1}`,
  })));
  const cajas = combinaciones.map(({ titulo }) => h('figure', {},
    h('div.combinacion-vista'), h('figcaption', {}, titulo)));
  cuadricula.append(...cajas);
  dialogo.append(h('div.catalogo-encabezado', {}, h('h2', {}, '25 combinaciones'),
    boton('Cerrar', 'blanco', () => dialogo.close())), estado, cuadricula);
  dialogo.addEventListener('close', () => dialogo.remove(), { once: true });
  document.body.append(dialogo);
  dialogo.showModal();
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    for (const [i, { cara, pelo, titulo }] of combinaciones.entries()) {
      if (!dialogo.open) break;
      const imagen = await imagenCabeza(cara.img, pelo, 220, renderer);
      if (!dialogo.open) break;
      cajas[i].firstChild.append(h('img', { src: imagen, alt: titulo }));
      estado.textContent = `${i + 1} de 25 combinaciones`;
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
  } catch {
    if (dialogo.open) estado.textContent = 'No se pudieron mostrar todas las combinaciones.';
  } finally {
    renderer?.dispose();
    renderer?.forceContextLoss();
  }
}

const lienzo = mundo.renderer.domElement;
lienzo.addEventListener('pointermove', (ev) => {
  if (panel.dataset.vista !== 'control' || panel.hidden) return (mundo.control.hover = null);
  mundo.control.hover = mundo.puestoBajo(ev);
  lienzo.style.cursor = mundo.control.hover != null ? 'pointer' : '';
});
lienzo.addEventListener('click', (ev) => {
  if (panel.dataset.vista !== 'control' || panel.hidden) return;
  const i = mundo.puestoBajo(ev);
  if (i != null) seleccionar(i);
});
window.addEventListener('keydown', (ev) => {
  if (panel.dataset.vista !== 'control' || panel.hidden || ['TEXTAREA', 'INPUT'].includes(ev.target.tagName)) return;
  const sel = mundo.control.seleccion;
  if (/^[1-5]$/.test(ev.key)) seleccionar(Number(ev.key) - 1);
  else if (ev.key === 'ArrowRight') seleccionar(sel == null ? 0 : Math.min(4, sel + 1));
  else if (ev.key === 'ArrowLeft') seleccionar(sel == null ? 0 : Math.max(0, sel - 1));
  else if (sel != null && (ev.key === 'a' || ev.key === 'A')) { decidir(sel, 'aceptada'); dibujarControl(); seleccionar(sel); }
  else if (sel != null && (ev.key === 'r' || ev.key === 'R')) { decidir(sel, 'rechazada'); dibujarControl(); seleccionar(sel); }
});

async function guardarDecisiones() {
  const decisiones = est.caras.map((c) => ({ id: c.id, ...est.decisiones[c.id] }));
  try {
    await api.decisiones(est.sesion, { ronda: est.ronda, decisiones, por_paquete: est.porPaquete });
  } catch (e) {
    return fallaServidor(e, guardarDecisiones);
  }
  mundo.control.seleccion = null;
  for (const c of est.caras) {
    if (est.decisiones[c.id].decision === 'aceptada') est.aprobadas.push({ id: c.id, imagen: c.imagen, img: c.img, peinado: est.cabellosRonda[est.caras.indexOf(c)] ?? est.rondaPeinado });
  }
  queSigue();
}

/** Después de decidir: otra ronda (con pedido en texto si el método lo entiende), el otro método o terminar. */
function queSigue(aviso = null, textoPrevio = '') {
  const ap = est.caras.filter((c) => est.decisiones[c.id]?.decision === 'aceptada').length;
  const g = est.info.generadores.find((x) => x.id === est.generador);
  const otro = est.info.generadores.find((x) => x.id !== est.generador && x.id !== 'simulado');
  decir(aviso || (ap === 0
    ? 'No te convenció ninguna. ¿Probamos otra ronda?'
    : `Anotado: aceptaste ${ap} y rechazaste ${5 - ap}. ¿Qué hacemos ahora?`));
  const bloque = [];
  if (g?.acepta_texto) {
    const campo = h('input.texto-libre', { type: 'text', maxlength: 300, placeholder: 'Por ejemplo: ponle lentes y que se vea más seria' });
    campo.value = textoPrevio || '';
    const otraRonda = () => fabricar('nueva', campo.value.trim() || null);
    campo.addEventListener('keydown', (ev) => ev.key === 'Enter' && otraRonda());
    bloque.push(h('div.campo', {},
      h('span.etiqueta', {}, '¿Qué le cambio en la próxima ronda?'),
      h('div.libre', {}, campo, boton('Otra ronda', 'rojo', otraRonda))));
  }
  const botones = [];
  if (ap > 0 && g?.conserva_forma) botones.push(boton('Variar las aceptadas', 'rojo', () => fabricar('variar')));
  if (!g?.acepta_texto) botones.push(boton('Otra ronda desde cero', ap > 0 ? 'blanco' : 'rojo', elegirMaquina));
  if (otro) {
    botones.push(boton(otro.acepta_texto ? 'Probar con asesoría' : 'Probar con el modelo entrenado', 'blanco',
      () => cambiarMetodo(otro), { disabled: !otro.disponible, title: otro.disponible ? null : otro.detalle }));
  }
  botones.push(boton('Terminar', 'blanco', resumenFinal));
  bloque.push(fila(...botones));
  mostrar(bloque, { ancho: !!g?.acepta_texto });
  panel.dataset.vista = 'despues';
}

/** Pasa al otro modelo sin perder la sesión: sus rondas se suman al mismo registro. */
function cambiarMetodo(g) {
  est.generador = g.id;
  est.opciones = {};
  if (g.acepta_texto) {
    est.modo = 'asesoria';
    asesoria();
  } else {
    est.modo = 'maquina';
    if (g.necesita_foto && !est.tieneFoto) {
      est.trasFoto = elegirMaquina;
      tomarFoto();
    } else {
      elegirMaquina();
    }
  }
}

/* ---------------- 6. resumen y descarga ---------------- */

let trofeo = null;
function ponerTrofeo(img, peinado = null) {
  if (!trofeo) {
    trofeo = new Cabeza(mundo.renderer);
    trofeo.grupo.position.set(-1.6, 1.58, 0.2);
    trofeo.grupo.scale.setScalar(1.25);
    mundo.scene.add(trofeo.grupo);
    mundo.alActualizar.push((dt) => (trofeo.grupo.rotation.y += dt * 0.8));
  }
  trofeo.grupo.visible = !!img;
  if (img) trofeo.ponerImagen(img);
  trofeo.ponerCabello(img ? peinado : null);
}

function resumenFinal() {
  paso('resumen');
  mundo.irA('resumen', { panelLateral: true });
  if (!est.favorita && est.aprobadas.length) est.favorita = est.aprobadas[est.aprobadas.length - 1].id;
  const fav = est.aprobadas.find((a) => a.id === est.favorita);
  ponerTrofeo(fav?.img, fav?.peinado);
  decir(est.aprobadas.length ? 'Elige tu favorita y te armo el resumen de tu sesión.' : 'No aceptaste ninguna cara. Igual te armo el resumen.');
  dibujarResumen(null);
}

/** El resumen del agente viene en cuatro apartados ("Aceptadas:", "- v1 (ronda 1): …"). */
function textoResumen(texto) {
  const caja = h('div.resumen');
  let lista = null;
  for (const linea of texto.split('\n').map((l) => l.trim()).filter(Boolean)) {
    if (linea.startsWith('-')) {
      if (!lista) caja.append((lista = h('ul')));
      lista.append(h('li', {}, linea.replace(/^-\s*/, '')));
    } else {
      lista = null;
      caja.append(h('h3', {}, linea.replace(/:$/, '')));
    }
  }
  return caja;
}

function dibujarResumen(resultado) {
  const fav = est.aprobadas.find((a) => a.id === est.favorita);
  const favoritas = est.aprobadas.length
    ? h(
        'div.favoritas',
        { role: 'radiogroup', 'aria-label': 'Favorita' },
        est.aprobadas.map((a) =>
          h('button.fav', {
            role: 'radio',
            'aria-checked': String(a.id === est.favorita),
            title: a.id,
            onclick: () => {
              est.favorita = a.id;
              ponerTrofeo(a.img, a.peinado);
              dibujarResumen(resultado);
            },
          }, h('img', { src: a.imagen, alt: a.id }), h('span', {}, a.id)),
        ),
      )
    : h('p.nota', {}, 'Sin caras aceptadas.');

  const bloque = [h('h2', {}, 'Tu favorita'), favoritas, h('h2', {}, 'Resumen del agente')];
  if (resultado) {
    const v = resultado.verificacion;
    bloque.push(
      textoResumen(resultado.texto),
      h(`div.verif.${v.ok ? 'ok' : 'mal'}`, {},
        h('strong', {}, v.ok ? 'Verificado contra tu registro' : 'El verificador encontró problemas'),
        h('span', {}, v.ok
          ? 'Cada cara está en su apartado y los conteos coinciden con lo que decidiste.'
          : v.errores.slice(0, 3).join(' ')),
        h('span.fuente', {}, `${resultado.origen === 'llm' ? `LLM: ${resultado.llm}` : 'Plantilla del agente (sin LLM)'}`
          + ` · ${(resultado.ms / 1000).toFixed(1)} s`),
      ),
    );
  }
  bloque.push(
    boton(resultado ? 'Resumir de nuevo' : 'Resumir mis decisiones', resultado ? 'blanco' : 'rojo', pedirResumen),
    h('h2', {}, 'Llévatela'),
    h('div.descargas', {},
      boton('Estampa PNG', 'blanco', () => descargar(fav.imagen, `cara_${fav.id}.png`), { disabled: !fav }),
      boton('Cabeza 3D', 'blanco', async () => descargar(await glbCabeza(fav.img, fav.peinado), `cabeza_${fav.id}.glb`), { disabled: !fav }),
      boton('Foto 3D', 'blanco', async () => descargar(await imagenCabeza(fav.img, fav.peinado), `cabeza_${fav.id}.png`), { disabled: !fav }),
      boton('Registro', 'blanco', () => descargar(api.registroUrl(est.sesion), `registro_${est.sesion}.json`)),
    ),
    h('div.pie', {}, boton('Empezar de nuevo', 'rojo', reiniciar)),
  );
  mostrar(bloque, { lado: 'derecha' });
  panel.dataset.vista = 'resumen';
}

async function pedirResumen() {
  decir('Déjame repasar lo que elegiste…');
  try {
    const r = await api.resumen(est.sesion, { favorita: est.favorita });
    dibujarResumen(r);
    const fav = est.favorita ? ` Tu favorita es ${est.favorita}.` : '';
    decir(`Listo, te dejé el resumen al lado y lo revisé contra lo que decidiste.${fav}`);
  } catch (e) {
    fallaServidor(e, pedirResumen);
  }
}

async function reiniciar() {
  clearInterval(vigilaEstado);
  apagarCamara();
  if (est.sesion) api.cerrar(est.sesion);
  Object.assign(est, {
    sesion: null, ronda: null, caras: [], decisiones: {}, aprobadas: [], favorita: null, foto: null, opciones: {},
    modo: null, ficha: null, tieneFoto: false, preguntoFoto: false, trasFoto: null, generador: null,
    peinado: null, preguntoPeinado: false, rondaPeinado: null, cabellosRonda: [], verCabelloFoto: false, generandoCabello: false,
  });
  mundo.oficina.mostrarPeinado(null);
  mundo.cabina.apagar();
  mundo.oficina.dibujar({}, null);
  ponerTrofeo(null);
  inicio();
}

window.addEventListener('beforeunload', () => {
  if (est.sesion) navigator.sendBeacon(`/api/sesion/${est.sesion}/cerrar`);
});

inicio();
