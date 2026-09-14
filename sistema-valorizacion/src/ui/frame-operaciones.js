// Frame 2 — Carga de Operaciones del día (tabla append-only).
//
// Si un día no hay operaciones, aquí no se carga nada: el motor sigue derivando
// la posición vigente y devengando cupones por su cuenta.

import * as store from '../datos/almacen.js';
import { hoyISO, sumarHabiles } from '../core/fechas.js';
import { el, fmt, tabla, campo, entrada, seleccion, boton, panel, nota, aviso, listaErrores, etiqueta, confirmar } from './comunes.js';

const TIPOS = [
  ['compra', 'Compra'],
  ['venta', 'Venta'],
  ['aporte', 'Aporte de cliente (flujo externo)'],
  ['rescate', 'Rescate de cliente (flujo externo)'],
];

let borrador = null;
let filtro = '';

const VACIO = () => ({
  tipo: 'compra', isin: '', fechaOperacion: hoyISO(), fechaLiquidacion: '',
  nominal: '', precioOperacion: '', monto: '', moneda: 'USD', flujo: 'interno', comentario: '',
});

export function render(contenedor, refrescar) {
  const datos = store.estado();
  if (!borrador) borrador = VACIO();

  const operaciones = datos.operaciones
    .slice()
    .sort((a, b) => (a.fechaOperacion === b.fechaOperacion ? (a.ts < b.ts ? 1 : -1) : (a.fechaOperacion < b.fechaOperacion ? 1 : -1)))
    .filter((o) => !filtro || (o.isin || o.moneda || '').toLowerCase().includes(filtro.toLowerCase()) || o.fechaOperacion.includes(filtro));

  contenedor.replaceChildren(
    el('div', { clase: 'encabezado-frame' },
      el('div', {},
        el('h1', {}, 'Operaciones del día'),
        el('p', { clase: 'subtitulo' }, 'Tabla append-only: un registro no se edita ni se borra nunca. Para corregir se emite una reversa, que se agrega al final y netea la original.'))),

    formulario(datos, refrescar),

    panel('Historial de operaciones',
      el('div', { clase: 'barra' },
        campo('Buscar por ISIN o fecha', entrada({ value: filtro, placeholder: 'XS2456… o 2026-09', oninput: (e) => { filtro = e.target.value; refrescar(); } }))),
      tabla([
        { titulo: 'Registro', render: (o) => el('div', {}, el('code', { clase: 'tenue' }, o.id), el('div', { clase: 'tenue mini-texto' }, new Date(o.ts).toLocaleString('es-PE'))) },
        { titulo: 'F. operación', render: (o) => fmt.fecha(o.fechaOperacion) },
        { titulo: 'F. liquidación', render: (o) => fmt.fecha(o.fechaLiquidacion) },
        { titulo: 'Tipo', render: (o) => etiqueta(TIPOS.find(([k]) => k === o.tipo)?.[1].split(' ')[0] || o.tipo, o.tipo === 'compra' || o.tipo === 'aporte' ? 'ok' : 'alerta') },
        { titulo: 'Instrumento', render: (o) => (o.isin ? el('code', {}, o.isin) : el('span', { clase: 'tenue' }, `caja ${o.moneda}`)) },
        { titulo: 'Nominal', alinear: 'der', render: (o) => (o.nominal ? fmt.nominal(o.nominal) : '—') },
        { titulo: 'Precio', alinear: 'der', render: (o) => (o.precioOperacion ? fmt.precio(o.precioOperacion) : '—') },
        { titulo: 'Monto', alinear: 'der', render: (o) => (o.monto ? fmt.monto(o.monto) : '—') },
        { titulo: 'Flujo', render: (o) => etiqueta(o.flujo, o.flujo === 'externo' ? 'aviso' : 'neutro') },
        { titulo: 'Estado', render: (o) => (o.reversaDe ? etiqueta('reversa', 'alerta') : store.estaReversada(o.id) ? etiqueta('reversada', 'alerta') : etiqueta('vigente', 'ok')) },
        { titulo: 'Comentario', render: (o) => el('span', { clase: 'tenue mini-texto' }, o.comentario || '—') },
        {
          titulo: '', render: (o) => (o.reversaDe || store.estaReversada(o.id) ? el('span', { clase: 'tenue' }, '—')
            : boton('Reversar', () => {
                const motivo = window.prompt('Motivo de la reversa (queda en el registro):', '');
                if (motivo === null) return;
                const r = store.reversarOperacion(o.id, motivo);
                aviso(r.ok ? 'Reversa registrada.' : r.errores[0], r.ok ? 'ok' : 'error');
              }, 'peligro')),
        },
      ], operaciones, { vacio: 'No hay operaciones registradas. El motor igual valoriza: no se carga nada en los días sin movimiento.' })),
  );
}

function formulario(datos, refrescar) {
  const b = borrador;
  const set = (k) => (e) => { b[k] = e.target.value; };
  const esFlujo = b.tipo === 'aporte' || b.tipo === 'rescate';
  const inst = datos.instrumentos.find((i) => i.isin === b.isin);
  const contenedorErrores = el('div');
  const monedas = [...new Set([...datos.instrumentos.map((i) => i.moneda), datos.config.monedaReporte])];

  // Sugerencia de fecha de liquidación según la convención del instrumento.
  const feriados = new Set(datos.feriados.filter((h) => h.plaza === (inst?.plaza || datos.config.plazaPorDefecto)).map((h) => h.fecha));
  const sugerida = inst && b.fechaOperacion ? sumarHabiles(b.fechaOperacion, Number(inst.convLiquidacion), feriados) : '';

  return panel('Registrar operación',
    el('div', { clase: 'rejilla' },
      campo('Tipo de operación', seleccion({ onchange: (e) => { b.tipo = e.target.value; b.flujo = (e.target.value === 'aporte' || e.target.value === 'rescate') ? 'externo' : 'interno'; refrescar(); } }, TIPOS, b.tipo)),
      campo('Fecha de operación', entrada({ type: 'date', value: b.fechaOperacion, onchange: (e) => { b.fechaOperacion = e.target.value; refrescar(); } })),
      esFlujo ? null : campo('Instrumento', seleccion({ onchange: (e) => { b.isin = e.target.value; refrescar(); } },
        [['', '— seleccione —'], ...datos.instrumentos.map((i) => [i.isin, `${i.isin} · ${i.emisor}`])], b.isin)),
      esFlujo
        ? campo('Moneda', seleccion({ onchange: set('moneda') }, monedas.map((m) => [m, m]), b.moneda))
        : campo('Nominal', entrada({ type: 'number', step: '0.01', value: b.nominal, oninput: set('nominal'), placeholder: '1000000' })),
      esFlujo
        ? campo('Monto', entrada({ type: 'number', step: '0.01', value: b.monto, oninput: set('monto'), placeholder: '5000000' }))
        : campo('Precio de operación (limpio)', entrada({ type: 'number', step: '0.000001', value: b.precioOperacion, oninput: set('precioOperacion'), placeholder: '98.4062' })),
      campo('Fecha de liquidación',
        entrada({ type: 'date', value: b.fechaLiquidacion || sugerida, oninput: set('fechaLiquidacion') }),
        inst ? `Convención del papel: T+${inst.convLiquidacion} → ${fmt.fecha(sugerida)}` : 'Si se deja vacío, liquida el mismo día.'),
      campo('Flujo', seleccion({ onchange: set('flujo'), disabled: esFlujo || null },
        [['interno', 'Interno (rebalanceo del gestor)'], ['externo', 'Externo (aporte/rescate del cliente)']], b.flujo),
        'Solo el flujo externo rompe el período de retorno en la Fase 2.'),
      campo('Comentario', entrada({ value: b.comentario, oninput: set('comentario'), placeholder: 'Motivo / referencia de la orden' })),
    ),
    nota('Los cupones y las amortizaciones NO se cargan aquí: el motor los genera desde el Calendario_Cupones en su fecha de pago.', 'info'),
    contenedorErrores,
    el('div', { clase: 'acciones' },
      boton('Registrar operación', () => {
        if (!b.fechaLiquidacion) b.fechaLiquidacion = sugerida || b.fechaOperacion;
        const r = store.agregarOperacion(b);
        if (!r.ok) { contenedorErrores.replaceChildren(listaErrores(r.errores)); return; }
        aviso('Operación registrada (append-only).');
        borrador = VACIO();
        borrador.fechaOperacion = r.operacion.fechaOperacion;
        refrescar();
      }, 'primario'),
      boton('Limpiar', () => { borrador = VACIO(); refrescar(); })));
}
