# Render de la minifig (3626bp39_09)

Archivos (deja todos juntos en la misma carpeta):
- `minifig_3626bp39_09.ldr`: modelo principal (piezas oficiales de LDraw + la cabeza con cara).
- `cabeza_3626bp39_09.dat`: cabeza con la cara aplicada con `!TEXMAP START PLANAR` (igual que la cabeza oficial con textura `3626cpx0.dat`).
- `textures/cara_3626bp39_09.png` (y una copia `cara_3626bp39_09.png` al lado): la cara RGBA. El estándar busca primero en `textures/`.
- `vista_previa_3626bp39_09.png`: vista frontal aproximada hecha en Python, solo para comprobar que las piezas encajan.

Necesitas la librería oficial de piezas: https://library.ldraw.org/library/updates/complete.zip (descomprímela, p. ej. en `C:\LDraw`).

## LDView
1. Instala LDView. Usa la 4.4 o una más nueva: la 4.4 agregó las texturas CYLINDRICAL/SPHERICAL y arregló varios errores de texturas; la 4.6 y la 4.7 trajeron más arreglos.
2. La primera vez te pide la carpeta de la librería LDraw: elige la carpeta `ldraw` descomprimida.
3. Abre `minifig_3626bp39_09.ldr`. Si no ves la cara, revisa que `textures/cara_3626bp39_09.png` esté junto al `.ldr`.
4. Imagen desde la línea de comandos: `LDView minifig_3626bp39_09.ldr -SaveSnapshot=render.png` (las demás opciones están en la ayuda de LDView).

## Blender (complemento ImportLDraw de TobyLobster)
1. Instala el complemento desde https://github.com/TobyLobster/ImportLDraw (Blender 4.0 o más nuevo).
   Su README dice que importa las piezas con `!TEXMAP` (planar, cilíndrico y esférico) junto con sus imágenes.
2. *File → Import → LDraw*, elige `minifig_3626bp39_09.ldr` y, en las opciones, la carpeta de la librería LDraw.
3. Deja marcada la opción *Import textures*.
4. Renderiza con Cycles o EEVEE.

Visores sin `!TEXMAP` dibujan la cabeza lisa (sección FALLBACK); no es un error del archivo.
