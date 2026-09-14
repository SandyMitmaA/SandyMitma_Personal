// Genera la página de publicación a partir de index.html.
//
// El visor de artefactos envuelve el archivo en su propio <!doctype>/<head>/
// <body>, así que la página publicada no puede traer esas etiquetas. En vez de
// mantener una segunda copia del shell —que tarde o temprano se desincroniza—
// se deriva de index.html: título y hoja de estilos arriba, y el contenido del
// body debajo.

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';

const RAIZ = resolve(new URL('..', import.meta.url).pathname);
const destino = process.argv[2] || resolve(RAIZ, '../artefacto.html');

const html = await readFile(resolve(RAIZ, 'index.html'), 'utf8');

const titulo = html.match(/<title>([\s\S]*?)<\/title>/)?.[1];
const hojas = [...html.matchAll(/<link rel="stylesheet"[^>]*>/g)].map((m) => m[0]);
const cuerpo = html.match(/<body>([\s\S]*)<\/body>/)?.[1];

if (!titulo || !cuerpo) throw new Error('index.html no tiene el <title> o el <body> esperados.');

const salida = [
  `<title>${titulo}</title>`,
  ...hojas,
  cuerpo.trim(),
  '',
].join('\n');

await mkdir(dirname(destino), { recursive: true });
await writeFile(destino, salida, 'utf8');
console.log(`Página de publicación escrita en ${destino} (${salida.length} bytes).`);
