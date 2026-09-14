// Frame 1 — Maestro de Instrumentos y su Calendario_Cupones.

import * as store from '../datos/almacen.js';
import { TIPOS_INSTRUMENTO } from '../datos/almacen.js';
import { BASES, FRECUENCIAS } from '../core/conteo-dias.js';
import { hoyISO } from '../core/fechas.js';
import { el, fmt, tabla, campo, entrada, seleccion, boton, panel, nota, aviso, listaErrores, etiqueta, confirmar } from './comunes.js';

let seleccionado = null;
let editando = null;

const VACIO = () => ({
  isin: '', emisor: '', moneda: 'USD', cupon: 5, frecuencia: 'semestral',
  fechaEmision: '', fechaVencimiento: '', baseDias: '30/360', convLiquidacion: 2,
  tipo: 'bullet', plaza: 'US', fuente: '', fechaUltimaVerificacion: hoyISO(),
});

export function render(contenedor, refrescar) {
  const datos = store.estado();
  contenedor.replaceChildren(
    el('div', { clase: 'encabezado-frame' },
      el('div', {},
        el('h1', {}, 'Maestro de Instrumentos'),
        el('p', { clase: 'subtitulo' }, 'Capa de inputs: características del instrumento y calendario de pagos. Se carga al alta y solo se toca cuando cambian las características del papel.')),
      boton('+ Nuevo instrumento', () => { editando = VACIO(); refrescar(); }, 'primario')),

    editando ? formulario(datos, refrescar) : null,

    panel('Instrumentos registrados',
      tabla([
        { titulo: 'ISIN', render: (i) => el('code', {}, i.isin) },
        { clave: 'emisor', titulo: 'Emisor' },
        { clave: 'moneda', titulo: 'Moneda' },
        { titulo: 'Cupón', alinear: 'der', render: (i) => (i.tipo === 'cupon_cero' ? etiqueta('cero', 'neutro') : fmt.tasa(i.cupon)) },
        { titulo: 'Frecuencia', render: (i) => FRECUENCIAS[i.frecuencia]?.etiqueta || i.frecuencia },
        { titulo: 'Emisión', render: (i) => fmt.fecha(i.fechaEmision) },
        { titulo: 'Vencimiento', render: (i) => fmt.fecha(i.fechaVencimiento) },
        { clave: 'baseDias', titulo: 'Base días' },
        { titulo: 'Liquidación', render: (i) => `T+${i.convLiquidacion}` },
        { titulo: 'Tipo', render: (i) => TIPOS_INSTRUMENTO[i.tipo] || i.tipo },
        { clave: 'plaza', titulo: 'Plaza' },
        { titulo: 'Fuente', render: (i) => el('span', { clase: 'tenue', title: `Última verificación: ${fmt.fecha(i.fechaUltimaVerificacion)}` }, i.fuente || '—') },
        { titulo: 'Cupones', alinear: 'der', render: (i) => String(store.calendarioDe(i.isin).length) },
        {
          titulo: '', render: (i) => el('div', { clase: 'acciones' },
            boton('Calendario', () => { seleccionado = seleccionado === i.isin ? null : i.isin; refrescar(); }),
            boton('Editar', () => { editando = { ...i }; refrescar(); }),
            boton('Eliminar', () => {
              if (!confirmar(`¿Eliminar ${i.isin} del maestro? Se borran también su calendario y sus precios.`)) return;
              const r = store.eliminarInstrumento(i.isin);
              aviso(r.ok ? `${i.isin} eliminado.` : r.errores[0], r.ok ? 'ok' : 'error');
            }, 'peligro')),
        },
      ], datos.instrumentos, { vacio: 'Aún no hay instrumentos. Cargue uno con «Nuevo instrumento» o use el portafolio de demostración desde Configuración.' })),

    seleccionado ? panelCalendario(seleccionado, refrescar) : null,
  );
}

function formulario(datos, refrescar) {
  const f = editando;
  const set = (k) => (e) => { f[k] = e.target.value; };
  const existente = datos.instrumentos.some((i) => i.isin === f.isin);
  const monedas = [...new Set([...datos.instrumentos.map((i) => i.moneda), 'USD', 'PEN', 'EUR'])];
  const plazas = [...new Set([...datos.feriados.map((h) => h.plaza), ...datos.instrumentos.map((i) => i.plaza), 'US', 'PE', 'EU'])].filter(Boolean);
  const contenedorErrores = el('div');

  return panel(existente ? `Editar ${f.isin}` : 'Nuevo instrumento',
    el('div', { clase: 'rejilla' },
      campo('ISIN', entrada({ value: f.isin, oninput: set('isin'), readonly: existente || null, placeholder: 'US91282CJT89' })),
      campo('Emisor / descripción', entrada({ value: f.emisor, oninput: set('emisor'), placeholder: 'Tesoro EE. UU. 3.50% 2028' })),
      campo('Moneda base', seleccion({ onchange: set('moneda') }, monedas.map((m) => [m, m]), f.moneda)),
      campo('Tipo', seleccion({ onchange: (e) => { f.tipo = e.target.value; refrescar(); } }, Object.entries(TIPOS_INSTRUMENTO), f.tipo)),
      campo('Cupón anual (%)', entrada({ type: 'number', step: '0.0001', value: f.cupon, oninput: set('cupon'), disabled: f.tipo === 'cupon_cero' || null })),
      campo('Frecuencia de pago', seleccion({ onchange: set('frecuencia') }, Object.entries(FRECUENCIAS).map(([k, v]) => [k, v.etiqueta]), f.tipo === 'cupon_cero' ? 'cero' : f.frecuencia)),
      campo('Fecha de emisión', entrada({ type: 'date', value: f.fechaEmision, oninput: set('fechaEmision') })),
      campo('Fecha de vencimiento', entrada({ type: 'date', value: f.fechaVencimiento, oninput: set('fechaVencimiento') })),
      campo('Convención de días', seleccion({ onchange: set('baseDias') }, BASES.map((b) => [b, b]), f.baseDias), 'Define el devengo del accrued.'),
      campo('Liquidación de mercado', seleccion({ onchange: set('convLiquidacion') }, [0, 1, 2, 3].map((n) => [n, `T+${n}`]), f.convLiquidacion), 'Versión A usa esta convención.'),
      campo('Plaza de liquidación', seleccion({ onchange: set('plaza') }, plazas.map((p) => [p, p]), f.plaza), 'Determina el calendario de feriados.'),
      campo('Fuente de datos', entrada({ value: f.fuente, oninput: set('fuente'), placeholder: 'Bloomberg BVAL / prospecto' })),
      campo('Última verificación', entrada({ type: 'date', value: f.fechaUltimaVerificacion, oninput: set('fechaUltimaVerificacion') })),
    ),
    contenedorErrores,
    nota('Al guardar se regenera el Calendario_Cupones hacia atrás desde el vencimiento. Si el papel tiene un calendario irregular o una corporate action, guarde primero y luego ajuste las filas a mano.', 'info'),
    el('div', { clase: 'acciones' },
      boton('Guardar instrumento', () => {
        if (f.tipo === 'cupon_cero') { f.frecuencia = 'cero'; f.cupon = 0; }
        const r = store.guardarInstrumento(f);
        if (!r.ok) { contenedorErrores.replaceChildren(listaErrores(r.errores)); return; }
        aviso(`${f.isin} guardado y calendario generado.`);
        seleccionado = f.isin;
        editando = null;
        refrescar();
      }, 'primario'),
      boton('Cancelar', () => { editando = null; refrescar(); })));
}

function panelCalendario(isin, refrescar) {
  const filas = store.calendarioDe(isin);
  const inst = store.estado().instrumentos.find((i) => i.isin === isin);
  const sumaAmort = filas.reduce((s, f) => s + Number(f.amortPct || 0), 0);

  return panel(`Calendario_Cupones — ${isin}`,
    nota(`Cupón por período expresado por cada 100 de nominal vigente; amortización como porcentaje del nominal original. Los pagos de este calendario entran a caja automáticamente: nunca se cargan como operación.`, 'info'),
    Math.abs(sumaAmort - 100) > 0.001
      ? nota(`La amortización acumulada suma ${sumaAmort.toFixed(4)} % y debería sumar 100 %: el nominal no llegaría a cero al vencimiento.`, 'alerta')
      : nota(`Amortización acumulada: 100 %. El nominal se extingue al vencimiento.`, 'ok'),
    tabla([
      { titulo: '#', render: (_f, i) => String(i + 1) },
      { titulo: 'Fecha de pago', render: (f) => entrada({ type: 'date', value: f.fechaPago, onchange: (e) => { store.guardarFilaCalendario({ ...f, fechaPago: e.target.value }); refrescar(); } }) },
      { titulo: 'Cupón del período (%)', alinear: 'der', render: (f) => entrada({ type: 'number', step: '0.00000001', clase: 'mini', value: f.cuponPct, onchange: (e) => { store.guardarFilaCalendario({ ...f, cuponPct: e.target.value }); refrescar(); } }) },
      { titulo: 'Amortización de principal (%)', alinear: 'der', render: (f) => entrada({ type: 'number', step: '0.00000001', clase: 'mini', value: f.amortPct, onchange: (e) => { store.guardarFilaCalendario({ ...f, amortPct: e.target.value }); refrescar(); } }) },
      { titulo: 'Último pago', render: (f) => (f.esUltimoPago ? etiqueta('sí', 'ok') : '—') },
      { titulo: '', render: (f) => boton('Quitar', () => { store.quitarFilaCalendario(f.id); refrescar(); }, 'peligro') },
    ], filas, { vacio: 'Sin calendario generado.' }),
    el('div', { clase: 'acciones' },
      boton('Regenerar desde el maestro', () => {
        if (!confirmar(`Se descartan los ajustes manuales del calendario de ${isin}. ¿Continuar?`)) return;
        store.regenerarCalendario(isin);
        aviso('Calendario regenerado.');
        refrescar();
      }),
      boton('Agregar fila', () => {
        store.guardarFilaCalendario({ isin, fechaPago: inst?.fechaVencimiento || hoyISO(), cuponPct: 0, amortPct: 0, esUltimoPago: false });
        refrescar();
      }),
      boton('Cerrar', () => { seleccionado = null; refrescar(); })));
}
