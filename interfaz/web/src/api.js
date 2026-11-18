export class ErrorApi extends Error {
  constructor(mensaje, status, datos) {
    super(mensaje);
    this.status = status;
    this.datos = datos;
  }
}

async function pedir(url, opts) {
  let r;
  try {
    r = await fetch(url, opts);
  } catch {
    throw new ErrorApi('sin conexión', 0);
  }
  let d = null;
  try {
    d = await r.json();
  } catch {
    /* sin cuerpo */
  }
  if (!r.ok) throw new ErrorApi(d?.mensaje || d?.detail || `error ${r.status}`, r.status, d);
  return d;
}

const post = (body) => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body ?? {}),
});

export const api = {
  estado: () => pedir('/api/estado'),
  crearSesion: (modo) => pedir('/api/sesion', post({ consentimiento: true, modo })),
  interpretar: (sid, texto, pregunta) => pedir(`/api/sesion/${sid}/interpretar`, post({ texto, pregunta })),
  subirFoto(sid, blob) {
    const fd = new FormData();
    fd.append('foto', blob, 'foto.jpg');
    return pedir(`/api/sesion/${sid}/foto`, { method: 'POST', body: fd });
  },
  /** Recibe las caras una por una (NDJSON). */
  async *ronda(sid, body) {
    let r;
    try {
      r = await fetch(`/api/sesion/${sid}/ronda`, post(body));
    } catch {
      throw new ErrorApi('sin conexión', 0);
    }
    if (!r.ok) {
      let d = null;
      try {
        d = await r.json();
      } catch {
        /* nada */
      }
      throw new ErrorApi(d?.mensaje || d?.detail || `error ${r.status}`, r.status, d);
    }
    const lector = r.body.getReader();
    const dec = new TextDecoder();
    let resto = '';
    for (;;) {
      const { value, done } = await lector.read();
      if (done) break;
      resto += dec.decode(value, { stream: true });
      let i;
      while ((i = resto.indexOf('\n')) >= 0) {
        const linea = resto.slice(0, i).trim();
        resto = resto.slice(i + 1);
        if (linea) yield JSON.parse(linea);
      }
    }
  },
  decisiones: (sid, body) => pedir(`/api/sesion/${sid}/decisiones`, post(body)),
  resumen: (sid, body) => pedir(`/api/sesion/${sid}/resumen`, post(body)),
  registroUrl: (sid) => `/api/sesion/${sid}/registro`,
  cerrar: (sid) => pedir(`/api/sesion/${sid}/cerrar`, post({})).catch(() => {}),
};
