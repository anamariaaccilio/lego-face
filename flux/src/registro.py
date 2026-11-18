"""Un solo reporte y un solo zip para todo el notebook.

    registro.iniciar()            # al comienzo: todo lo impreso va también a flux_cara/reporte.txt
    registro.seccion("1.1 ...")   # títulos
    registro.mostrar(df)          # display() que además deja la tabla en el reporte
    registro.empaquetar()         # flux_cara/entregar.zip con todo lo que hay hasta ahora (se llama al final de cada etapa)

Si una celda falla, el error se escribe en el reporte y el zip se arma igual (para mandarlo tal cual).
"""
import sys
import traceback
import zipfile
from datetime import datetime

import config as C

EXTENSIONES = (".txt", ".json", ".csv", ".jpg", ".png", ".ldr", ".dat", ".md")
EXCLUIR = ("src", "crudas")            # carpetas que no van al zip (código y generaciones crudas de 512 px)


class _Tee:
    def __init__(self, original, archivo):
        self.original, self.archivo = original, archivo

    def write(self, texto):
        self.original.write(texto)
        try:
            self.archivo.write(texto)
            self.archivo.flush()
        except ValueError:                        # archivo cerrado
            pass
        return len(texto)

    def flush(self):
        self.original.flush()

    def __getattr__(self, nombre):                # isatty, encoding, etc.
        return getattr(self.original, nombre)


def detener():
    if isinstance(sys.stdout, _Tee):
        sys.stdout.archivo.close()
        sys.stdout = sys.stdout.original


def _al_fallar(shell, etype, evalue, tb, tb_offset=None):
    texto = "".join(traceback.format_exception(etype, evalue, tb))
    if isinstance(sys.stdout, _Tee):
        sys.stdout.archivo.write("\n" + "!" * 80 + "\n❌ ERROR en la celda:\n" + texto + "!" * 80 + "\n")
        sys.stdout.archivo.flush()
    try:
        empaquetar()
    except Exception as e:                        # nunca tapar el error original
        sys.__stdout__.write(f"(no se pudo armar el zip: {e})\n")
    shell.showtraceback((etype, evalue, tb), tb_offset=tb_offset)


def iniciar(nombre="reporte"):
    """Empieza el reporte (flux_cara/reporte.txt) y engancha los errores de celda."""
    detener()
    C.SALIDA.mkdir(parents=True, exist_ok=True)
    f = open(C.SALIDA / f"{nombre}.txt", "w", encoding="utf-8")
    sys.stdout = _Tee(sys.stdout, f)
    print(f"# Reporte · {datetime.now():%Y-%m-%d %H:%M}")
    try:
        from IPython import get_ipython
        ip = get_ipython()
        if ip is not None:
            ip.set_custom_exc((Exception,), _al_fallar)
    except ImportError:
        pass


def seccion(titulo):
    print("\n" + "=" * 80 + f"\n{titulo}\n" + "=" * 80)


def mostrar(obj, filas=12):
    """Muestra en el notebook y deja una versión en texto en el reporte."""
    try:
        from IPython.display import display
        display(obj)
    except ImportError:
        pass
    if hasattr(obj, "to_string"):
        texto = obj.head(filas).to_string(max_colwidth=70)
    else:
        texto = f"[{type(obj).__name__} {getattr(obj, 'size', '')}]"
    if isinstance(sys.stdout, _Tee):
        sys.stdout.archivo.write(texto + "\n")
        sys.stdout.archivo.flush()


def empaquetar(nombre="entregar", max_mb=20):
    """flux_cara/entregar.zip con reporte + imágenes + tablas + archivos LDraw (sin src/ ni crudas/)."""
    destino = C.SALIDA / f"{nombre}.zip"
    incluidos, omitidos = [], []
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for r in sorted(C.SALIDA.rglob("*")):
            rel = r.relative_to(C.SALIDA)
            if not r.is_file() or r.suffix.lower() not in EXTENSIONES or r.name == "reporte.txt":
                continue
            if any(p in EXCLUIR for p in rel.parts[:-1]):
                continue
            if r.stat().st_size > max_mb * 2**20:
                omitidos.append(str(rel))
                continue
            z.write(r, rel.as_posix())
            incluidos.append(rel.as_posix())
        print(f"\n📦 {destino} · {len(incluidos)} archivos + reporte.txt"
              + (f" · omitidos por tamaño: {omitidos}" if omitidos else ""))
        print("   → Descárgalo desde el panel Output (flux_cara/entregar.zip) y mándamelo.")
        if isinstance(sys.stdout, _Tee):
            sys.stdout.archivo.flush()
        if (C.SALIDA / "reporte.txt").exists():
            z.write(C.SALIDA / "reporte.txt", "reporte.txt")   # al final, para que incluya todo lo impreso
    return destino
