// Capturas para la Fig. 4: inicio, asesoría (peinado con maniquí), cinco variaciones y resumen.
//   npm i playwright-core   (una vez; usa el Edge instalado)
//   node capturas_fig4.mjs http://127.0.0.1:8765 ../retratos/p09.png ../fig4
// Con el servidor de interfaz/servidor encendido.
import { chromium } from 'playwright-core';
import { mkdirSync } from 'node:fs';

const [url, foto, salida] = process.argv.slice(2);
mkdirSync(salida, { recursive: true });
const nav = await chromium.launch({ channel: 'msedge', headless: true, args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader'] });
const p = await nav.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const clic = (t) => p.getByRole('button', { name: t, exact: true }).click();
const sig = async (n) => { await p.getByText(`Pregunta ${n} de 7`).waitFor({ timeout: 30000 }); await p.waitForTimeout(500); };
const cap = async (n, espera = 3500) => { await p.waitForTimeout(espera); await p.screenshot({ path: `${salida}/${n}.png` }); console.log('captura', n); };

await p.goto(url);
await cap('a_inicio', 5000);
await clic('Quiero asesoría');
await p.waitForTimeout(1200);
await clic('Acepto');
await p.waitForTimeout(3500);
await clic('Tomar o subir una foto');
await p.waitForTimeout(3000);
await p.locator('input[type=file]').setInputFiles(foto);
await p.waitForTimeout(1500);
await clic('Usar esta');
await sig(1); await clic('Feliz');
await sig(2); await clic('No');
await sig(3); await clic('Ninguna');
await sig(4);
await p.getByRole('button', { name: 'Medio despeinado', exact: true }).hover();
await cap('b_asesoria', 3000);
await clic('Medio despeinado');
await sig(5); await clic('Pelirrojo');
await sig(6); await clic('Verdes');
await sig(7);
await p.locator('input.texto-libre').fill('tengo pecas');
await p.locator('input.texto-libre').press('Enter');
await p.getByText('Tu ficha', { exact: true }).waitFor({ timeout: 30000 });
await p.waitForFunction(() => [...document.querySelectorAll('button')].some((b) => b.textContent === 'Fabricar 5 caras' && !b.disabled), null, { timeout: 240000 });
await clic('Fabricar 5 caras');
await p.locator('.tarjetas').waitFor({ timeout: 240000 });
await p.waitForTimeout(2500);
const tarjeta = (i) => p.locator('.tarjeta').nth(i);
for (const i of [0, 2, 3]) await tarjeta(i).getByRole('button', { name: 'Aceptar' }).click();
for (const i of [1, 4]) await tarjeta(i).getByRole('button', { name: 'Rechazar' }).click();
await tarjeta(1).getByRole('button', { name: 'Expresión' }).click();
await tarjeta(2).click();
await cap('c_variaciones', 2500);
await clic('Listo');
await p.waitForTimeout(1500);
await clic('Terminar');
await p.waitForTimeout(2500);
await clic('Resumir mis decisiones');
await p.locator('.verif').waitFor({ timeout: 90000 });
await cap('d_resumen', 4000);
await nav.close();
