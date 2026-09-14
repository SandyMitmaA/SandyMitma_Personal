// Grilla numerica densa. Marca visualmente los datos imputados.
import { el, esColumnaNumerica, formatearCelda, formatearFecha, limpiar } from './nucleo.js';

const COLUMNAS_FECHA = new Set([
  'fecha', 'fecha_valorizacion', 'fecha_devengo', 'ultimo_cupon', 'proximo_cupon',
  'fecha_alta', 'fecha_vencimiento', 'fecha_emision', 'fecha_origen_precio',
  'fecha_origen_tipo_cambio', 'ultimo_cupon_t0', 'proximo_cupon_t0', 'desde', 'hasta',
]);

const ETIQUETAS = {
  fecha_valorizacion: 'Fecha', isin: 'ISIN', nominal: 'Nominal', vigente: 'Vig.',
  fecha_devengo: 'F. devengo', ultimo_cupon: 'Ult. cupon', proximo_cupon: 'Prox. cupon',
  dias_transcurridos: 'Dias transc.', dias_periodo: 'Dias periodo',
  cupon_por_periodo: 'Cupon/periodo', devengo_por_100: 'Devengo x100',
  precio_proveedor: 'Precio proveedor', precio_local: 'Precio moneda local',
  tipo_cambio: 'Tipo de cambio', security_mv_local: 'Security MV local',
  devengo_local: 'Devengo local', total_mv_local: 'Total MV local',
  security_mv_base: 'Security MV base', devengo_base: 'Devengo base',
  total_mv_base: 'Total MV base', total_mv_base_t0: 'Total MV T+0',
  quiebre_t0: 'Quiebre T+0', devengo_por_100_t0: 'Devengo x100 T+0',
  begin_mv: 'Begin MV', end_mv: 'End MV', efecto_precio_fx: 'Efecto precio y FX',
  devengo_dia: 'Devengo del dia', cupon_pagado: 'Cupon pagado',
  alta_posicion: 'Alta de posicion', baja_vencimiento: 'Baja por vencimiento',
  cobros_dia: 'Cobros del dia', efecto_fx_caja: 'Efecto FX caja',
  control: 'Control', caja_base: 'Caja base', caja_origen: 'Caja origen',
  evento: 'Evento', error: 'Error', version_calculo: 'Version', fx: 'FX',
  precio_imputado: 'P. imput.', tipo_cambio_imputado: 'TC imput.',
  dias_arrastre_precio: 'Dias arrastre', fecha_origen_precio: 'Origen precio',
  fecha_origen_tipo_cambio: 'Origen TC', estado_quiebre: 'Estado', residual: 'Residual',
  devengo_diario: 'Devengo diario', posiciones: 'Posiciones', eventos: 'Eventos',
};

export const etiqueta = (c) => ETIQUETAS[c] || c.replace(/_/g, ' ');

export function tabla(columnas, filas, opciones = {}) {
  const { alHacerClic, claseFila, totales, celdaClicable } = opciones;
  const t = el('table');
  const thead = el('thead');
  thead.appendChild(el('tr', {}, columnas.map((c) =>
    el('th', { class: esColumnaNumerica(c) ? 'num' : '', texto: etiqueta(c), title: c }))));
  t.appendChild(thead);

  const tbody = el('tbody');
  for (const fila of filas) {
    const tr = el('tr', { class: claseFila ? claseFila(fila) : '' });
    if (alHacerClic) {
      tr.style.cursor = 'pointer';
      tr.addEventListener('click', () => alHacerClic(fila, tr));
    }
    for (const c of columnas) tr.appendChild(celda(c, fila, celdaClicable));
    tbody.appendChild(tr);
  }
  t.appendChild(tbody);

  if (totales) {
    const tr = el('tr', { class: 'total' });
    for (const c of columnas) tr.appendChild(celda(c, totales, null));
    tbody.appendChild(tr);
  }
  return el('div', { class: 'envoltura-tabla' }, [t]);
}

function celda(columna, fila, celdaClicable) {
  let valor = fila[columna];
  const numerica = esColumnaNumerica(columna);
  const clases = [];
  let texto;

  if (COLUMNAS_FECHA.has(columna)) {
    texto = formatearFecha(valor);
  } else if (columna === 'vigente' || columna.endsWith('_imputado')) {
    texto = valor ? 'si' : '';
  } else if (numerica) {
    texto = formatearCelda(columna, valor);
    clases.push('num');
    if (valor === null || valor === undefined || Number(valor) === 0) clases.push('cero');
    else if (Number(valor) < 0) clases.push('negativo');
  } else {
    texto = valor === null || valor === undefined ? '' : String(valor);
  }

  // El dato imputado nunca se presenta igual que el observado.
  if ((columna === 'precio_proveedor' || columna === 'precio_local') && fila.precio_imputado) {
    clases.push('imputado');
  }
  if (columna === 'tipo_cambio' && fila.tipo_cambio_imputado) clases.push('imputado');

  if (columna === 'control' && Math.abs(Number(valor || 0)) > 0.01) {
    clases.push('negativo');
  }

  const td = el('td', { class: clases.join(' '), texto, title: texto });
  if (celdaClicable && celdaClicable(columna, fila)) {
    td.classList.add('clicable');
    td.addEventListener('click', (e) => { e.stopPropagation(); celdaClicable(columna, fila)(); });
  }
  return td;
}

export function estadoVacio(titulo, explicacion, accion) {
  return el('div', { class: 'vacio' }, [
    el('p', {}, [el('strong', { texto: titulo })]),
    el('p', { texto: explicacion }),
    accion || null,
  ]);
}

export function marca(texto, nivel = 'neutro') {
  return el('span', { class: `marca ${nivel}`, texto });
}

export function reemplazar(contenedor, nodo) { limpiar(contenedor); contenedor.appendChild(nodo); }
