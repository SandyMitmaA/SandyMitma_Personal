// Puente Begin MV a End MV. Responde: por que cambio el valor entre dos dias.
import {
  API, aviso, el, enlaceModulo, estadoGlobal, formatearFecha, guardarFiltros, limpiar,
  monto, pedir,
} from '../componentes/nucleo.js';
import { estadoVacio, marca, tabla } from '../componentes/tabla.js';

const columnasConsolidado = (conCaja) => [
  'fecha', 'begin_mv', 'efecto_precio_fx', 'devengo_dia', 'cupon_pagado',
  'alta_posicion', 'baja_vencimiento',
  ...(conCaja ? ['cobros_dia', 'efecto_fx_caja'] : []),
  'end_mv', 'control', 'eventos',
];

export async function render(raiz) {
  raiz.appendChild(el('div', { class: 'encabezado-modulo' }, [
    el('h1', { texto: 'Begin MV a End MV' }),
    el('span', { class: 'pregunta',
      texto: 'Por que el portafolio vale hoy algo distinto de ayer.' }),
  ]));

  const desde = el('input', { type: 'date', value: estadoGlobal.desde });
  const hasta = el('input', { type: 'date', value: estadoGlobal.hasta });
  const isin = el('input', { size: 16, value: estadoGlobal.isin, placeholder: 'todos' });
  const cuerpo = el('div');

  const q = () => {
    const p = new URLSearchParams({ desde: desde.value, hasta: hasta.value });
    if (isin.value.trim()) p.set('isines', isin.value.trim().toUpperCase());
    return p;
  };

  raiz.appendChild(el('div', { class: 'filtros' }, [
    el('div', { class: 'campo' }, [el('label', { texto: 'Desde' }), desde]),
    el('div', { class: 'campo' }, [el('label', { texto: 'Hasta' }), hasta]),
    el('div', { class: 'campo' }, [el('label', { texto: 'Instrumento' }), isin]),
    el('button', { texto: 'Aplicar', onclick: () => {
      estadoGlobal.desde = desde.value; estadoGlobal.hasta = hasta.value;
      estadoGlobal.isin = isin.value.trim().toUpperCase(); guardarFiltros(); refrescar(); } }),
    el('button', { class: 'secundario', texto: 'Exportar CSV',
      onclick: () => { const p = q(); p.set('formato', 'csv');
        window.open(`${API}/exportar/puente?${p}`, '_blank'); } }),
    el('button', { class: 'secundario', texto: 'Exportar Excel',
      onclick: () => { const p = q(); p.set('formato', 'xlsx');
        window.open(`${API}/exportar/puente?${p}`, '_blank'); } }),
  ]));
  raiz.appendChild(cuerpo);

  async function refrescar() {
    limpiar(cuerpo);
    const datos = await pedir('/puente?' + q());
    if (!datos.filas.length) {
      cuerpo.appendChild(el('div', { class: 'panel' }, [estadoVacio(
        'No hay puente para este rango.',
        'El puente se construye con la valorizacion. Ejecuta el reproceso del rango.',
        enlaceModulo('Ir a Reproceso', 'reproceso', { desde: desde.value, hasta: hasta.value }))]));
      return;
    }

    const rotas = datos.filas_con_control_no_cero;
    cuerpo.appendChild(rotas.length
      ? aviso(`${rotas.length} fila(s) con control distinto de cero. Es un error de `
            + 'construccion del puente y debe investigarse antes de usar estas cifras.', 'alert')
      : aviso(`El control da cero en las ${datos.filas.length} combinaciones de fecha e `
            + 'instrumento: End MV menos Begin MV menos la suma de componentes.', 'ok'));

    cuerpo.appendChild(el('div', { class: 'panel' }, [
      el('h2', {}, ['Puente consolidado del portafolio']),
      tabla(columnasConsolidado(datos.incluir_caja), datos.consolidado, {
        claseFila: (f) => (Math.abs(Number(f.control || 0)) > 0.01 ? 'negativo' : '') }),
    ]));

    cuerpo.appendChild(el('div', { class: 'panel' }, [
      el('h2', {}, ['Puente por instrumento']),
      tabla(datos.incluir_caja ? datos.columnas
        : datos.columnas.filter((c) => !['cobros_dia', 'efecto_fx_caja', 'caja_origen',
                                         'caja_base'].includes(c)),
        datos.filas,
        { claseFila: (f) => (Math.abs(Number(f.control || 0)) > 0.01 ? 'negativo' : '') }),
      el('div', { class: 'leyenda' }, [
        'Begin MV = End MV del dia anterior. La columna de control debe dar cero en todas '
        + 'las filas; es el mecanismo de deteccion de errores de construccion.',
        marca('CUPON / VENCIMIENTO', 'neutro'),
        'Sin caja activa el Total MV cae el dia del cupon y el del vencimiento: la columna '
        + 'de evento explica el salto.',
      ]),
    ]));
  }

  await refrescar();
}
