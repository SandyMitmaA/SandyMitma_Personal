// Servidor estático mínimo, sin dependencias. Los módulos ES no se pueden
// cargar desde file:// (el navegador los bloquea por CORS), así que el sistema
// se abre siempre por http://localhost.

import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize, resolve } from 'node:path';

const RAIZ = resolve(new URL('..', import.meta.url).pathname);
const PUERTO = Number(process.env.PUERTO || process.argv[2] || 8123);

const TIPOS = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.md': 'text/markdown; charset=utf-8',
};

createServer(async (peticion, respuesta) => {
  const ruta = decodeURIComponent(new URL(peticion.url, 'http://localhost').pathname);
  const relativa = normalize(ruta === '/' ? 'index.html' : ruta.replace(/^\/+/, ''));
  const archivo = join(RAIZ, relativa);

  // Nunca se sirve nada fuera de la carpeta del proyecto.
  if (!archivo.startsWith(RAIZ)) {
    respuesta.writeHead(403).end('Prohibido');
    return;
  }
  try {
    const contenido = await readFile(archivo);
    respuesta.writeHead(200, {
      'Content-Type': TIPOS[extname(archivo)] || 'application/octet-stream',
      'Cache-Control': 'no-store',
    }).end(contenido);
  } catch {
    respuesta.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end(`No encontrado: ${relativa}`);
  }
}).listen(PUERTO, () => {
  console.log(`Sistema de Valorización disponible en http://localhost:${PUERTO}`);
});
