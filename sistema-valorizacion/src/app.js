// Shell de la aplicación: navegación entre frames y arranque.

import * as store from './datos/almacen.js';
import { el } from './ui/comunes.js';
import * as frameInstrumentos from './ui/frame-instrumentos.js';
import * as frameOperaciones from './ui/frame-operaciones.js';
import * as framePrecios from './ui/frame-precios.js';
import * as frameValorizacion from './ui/frame-valorizacion.js';
import * as frameConfig from './ui/frame-config.js';

const FRAMES = [
  { id: 'valorizacion', titulo: 'Valorización', capa: 'Reportes', modulo: frameValorizacion },
  { id: 'instrumentos', titulo: 'Maestro de Instrumentos', capa: 'Inputs', modulo: frameInstrumentos },
  { id: 'operaciones', titulo: 'Operaciones', capa: 'Inputs', modulo: frameOperaciones },
  { id: 'precios', titulo: 'Precios y FX', capa: 'Inputs', modulo: framePrecios },
  { id: 'config', titulo: 'Configuración', capa: 'Gobierno', modulo: frameConfig },
];

const contenido = document.getElementById('contenido');
const navegacion = document.getElementById('navegacion');

function frameActual() {
  const id = location.hash.replace('#/', '') || 'valorizacion';
  return FRAMES.find((f) => f.id === id) || FRAMES[0];
}

function pintarNavegacion() {
  const actual = frameActual();
  navegacion.replaceChildren(...FRAMES.map((f) =>
    el('a', { href: `#/${f.id}`, clase: `nav-item ${f.id === actual.id ? 'activo' : ''}` },
      el('span', { clase: 'nav-titulo' }, f.titulo),
      el('span', { clase: 'nav-capa' }, f.capa))));
}

function pintar() {
  const frame = frameActual();
  pintarNavegacion();
  document.title = `${frame.titulo} · Valorización de Portafolios de Renta Fija`;
  try {
    frame.modulo.render(contenido, pintar);
  } catch (error) {
    console.error(error);
    contenido.replaceChildren(
      el('section', { clase: 'panel' },
        el('h2', { clase: 'panel-titulo' }, 'Ocurrió un error al dibujar esta pantalla'),
        el('pre', { clase: 'traza' }, `${error.message}\n\n${error.stack || ''}`),
        el('p', { clase: 'nota nota-info' }, 'Los datos cargados no se perdieron. Si el error persiste, exporte el respaldo desde Configuración y revise la consola del navegador.')));
  }
  window.scrollTo({ top: 0, behavior: 'instant' });
}

store.cargar();
store.suscribir(() => { /* el guardado es automático; cada frame decide cuándo repintar */ });
window.addEventListener('hashchange', pintar);
pintar();
