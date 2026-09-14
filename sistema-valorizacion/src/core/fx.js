// Capa 1 — tipo de cambio. Se busca el par directo, luego el inverso, y si no
// hay cotización del día se arrastra la última disponible con marca 'stale'.

import { comparar } from './fechas.js';

export function indexarFX(filas = []) {
  const porPar = new Map();
  for (const f of filas) {
    if (!porPar.has(f.par)) porPar.set(f.par, []);
    porPar.get(f.par).push(f);
  }
  for (const lista of porPar.values()) lista.sort((a, b) => comparar(a.fecha, b.fecha));
  return porPar;
}

function ultimaHasta(lista, fecha) {
  let hallado = null;
  for (const f of lista || []) {
    if (comparar(f.fecha, fecha) <= 0) hallado = f;
    else break;
  }
  return hallado;
}

/**
 * @returns {{tasa:number|null, estado:'identidad'|'directo'|'inverso'|'stale'|'faltante', fuente?:string, fecha?:string}}
 */
export function tipoCambio(indice, fecha, de, a) {
  if (!de || !a || de === a) return { tasa: 1, estado: 'identidad' };

  const directo = ultimaHasta(indice.get(`${de}/${a}`), fecha);
  if (directo) {
    const estado = directo.fecha === fecha ? 'directo' : 'stale';
    return { tasa: Number(directo.tipo), estado, fuente: directo.fuente, fecha: directo.fecha };
  }
  const inverso = ultimaHasta(indice.get(`${a}/${de}`), fecha);
  if (inverso && Number(inverso.tipo)) {
    const estado = inverso.fecha === fecha ? 'inverso' : 'stale';
    return { tasa: 1 / Number(inverso.tipo), estado, fuente: inverso.fuente, fecha: inverso.fecha };
  }
  return { tasa: null, estado: 'faltante' };
}
