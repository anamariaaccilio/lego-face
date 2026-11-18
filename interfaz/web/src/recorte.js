/** El recuadro trabaja en píxeles de la foto; la escala de pantalla solo afecta el arrastre. */
export function crearRecorte(foto, espejo) {
  const { width, height } = foto;
  const minimo = Math.min(160, width, height);
  const limitar = (v, min, max) => Math.max(min, Math.min(max, v));
  const completo = () => ({ x: 0, y: 0, w: width, h: height });
  let marco = completo();
  let gesto = null;

  const vista = document.createElement('div');
  vista.className = 'recorte-vista';
  vista.style.width = `min(100%, 580px, max(160px, ${42 * width / height}dvh))`;
  const imagen = document.createElement('canvas');
  imagen.width = width;
  imagen.height = height;
  const ctx = imagen.getContext('2d');
  if (espejo) { ctx.translate(width, 0); ctx.scale(-1, 1); }
  ctx.drawImage(foto, 0, 0);
  imagen.setAttribute('aria-label', 'Foto completa');
  const borde = document.createElement('div');
  borde.className = 'recorte-marco';
  borde.tabIndex = 0;
  borde.setAttribute('aria-label', 'Mover recuadro con las flechas');
  vista.append(imagen, borde);

  function pintar() {
    Object.assign(borde.style, {
      left: `${100 * marco.x / width}%`, top: `${100 * marco.y / height}%`,
      width: `${100 * marco.w / width}%`, height: `${100 * marco.h / height}%`,
    });
  }

  for (const esquina of ['nw', 'ne', 'sw', 'se']) {
    const asa = document.createElement('button');
    asa.type = 'button';
    asa.className = `recorte-asa ${esquina}`;
    asa.dataset.esquina = esquina;
    asa.setAttribute('aria-label', `Redimensionar recuadro: esquina ${esquina}`);
    borde.append(asa);
  }

  function ajustar(base, esquina, dx, dy) {
    if (!esquina) {
      marco = { ...base, x: limitar(base.x + dx, 0, width - base.w),
        y: limitar(base.y + dy, 0, height - base.h) };
    } else {
      let { x, y } = base;
      let derecha = x + base.w;
      let abajo = y + base.h;
      if (esquina.includes('w')) x = limitar(x + dx, 0, derecha - minimo);
      else derecha = limitar(derecha + dx, x + minimo, width);
      if (esquina.includes('n')) y = limitar(y + dy, 0, abajo - minimo);
      else abajo = limitar(abajo + dy, y + minimo, height);
      marco = { x, y, w: derecha - x, h: abajo - y };
    }
    pintar();
  }

  borde.addEventListener('pointerdown', (e) => {
    if (gesto || e.button !== 0) return;
    e.preventDefault();
    borde.setPointerCapture(e.pointerId);
    gesto = { id: e.pointerId, x: e.clientX, y: e.clientY, base: { ...marco },
      esquina: e.target.dataset.esquina };
  });
  borde.addEventListener('pointermove', (e) => {
    if (gesto?.id !== e.pointerId) return;
    const caja = vista.getBoundingClientRect();
    ajustar(gesto.base, gesto.esquina,
      (e.clientX - gesto.x) * width / caja.width, (e.clientY - gesto.y) * height / caja.height);
  });
  borde.addEventListener('lostpointercapture', (e) => {
    if (gesto?.id === e.pointerId) gesto = null;
  });
  borde.addEventListener('keydown', (e) => {
    const direccion = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
    if (!direccion) return;
    e.preventDefault();
    const paso = e.shiftKey ? 20 : 5;
    ajustar(marco, e.target.dataset.esquina, direccion[0] * paso, direccion[1] * paso);
  });

  pintar();
  return {
    vista,
    restablecer() { marco = completo(); pintar(); },
    aplicar() {
      const { x, y, w, h } = marco;
      const salida = document.createElement('canvas');
      salida.width = Math.round(w);
      salida.height = Math.round(h);
      const izquierda = espejo ? width - x - w : x;
      salida.getContext('2d').drawImage(foto, izquierda, y, w, h, 0, 0, salida.width, salida.height);
      return salida;
    },
  };
}
