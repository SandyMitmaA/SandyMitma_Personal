// Portafolio de demostración: 4 instrumentos, dos monedas, un cupón y una
// amortización dentro de la ventana de valorización, y un feriado en cada plaza.
// Sirve para recorrer el sistema de punta a punta sin cargar nada a mano.

import { esHabil, rangoFechas } from '../core/fechas.js';
import { generarCalendario } from '../core/calendario.js';

const INSTRUMENTOS = [
  { isin: 'US91282CJT89', emisor: 'Tesoro EE. UU. 3.50% 2028', moneda: 'USD', cupon: 3.5, frecuencia: 'semestral', fechaEmision: '2023-08-15', fechaVencimiento: '2028-08-15', baseDias: 'ACT/ACT', convLiquidacion: 1, tipo: 'bullet', plaza: 'US', fuente: 'TreasuryDirect' },
  { isin: 'XS2456789012', emisor: 'Corporativo LatAm 6.25% 2029', moneda: 'USD', cupon: 6.25, frecuencia: 'semestral', fechaEmision: '2022-09-08', fechaVencimiento: '2029-09-08', baseDias: '30/360', convLiquidacion: 2, tipo: 'bullet', plaza: 'US', fuente: 'Bloomberg BVAL' },
  { isin: 'PE1234567890', emisor: 'Perú Global 5.40% 2031', moneda: 'USD', cupon: 5.4, frecuencia: 'anual', fechaEmision: '2024-03-12', fechaVencimiento: '2031-03-12', baseDias: '30/360', convLiquidacion: 1, tipo: 'bullet', plaza: 'PE', fuente: 'MEF / Datos Técnicos' },
  { isin: 'XS9876543210', emisor: 'Titulizado Andino 5.00% 2027', moneda: 'USD', cupon: 5.0, frecuencia: 'trimestral', fechaEmision: '2024-09-10', fechaVencimiento: '2027-09-10', baseDias: '30/360', convLiquidacion: 2, tipo: 'amortizable', plaza: 'US', fuente: 'Prospecto del emisor' },
];

const PRECIO_BASE = { US91282CJT89: 98.42, XS2456789012: 101.85, PE1234567890: 96.30, XS9876543210: 99.55 };

/** Generador congruencial lineal: los precios de demo son siempre los mismos. */
function aleatorio(semilla) {
  let s = semilla;
  return () => ((s = (s * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
}

export function datosDemo({ desde = '2026-09-01', hasta = '2026-09-14' } = {}) {
  const feriados = [
    { id: 'fer-us-1', plaza: 'US', fecha: '2026-09-07', descripcion: 'Labor Day' },
    { id: 'fer-pe-1', plaza: 'PE', fecha: '2026-08-30', descripcion: 'Santa Rosa' },
    { id: 'fer-pe-2', plaza: 'PE', fecha: '2026-10-08', descripcion: 'Combate de Angamos' },
  ];
  const feriadosUS = new Set(['2026-09-07']);

  const calendario = [];
  for (const inst of INSTRUMENTOS) {
    for (const [i, fila] of generarCalendario(inst).entries()) {
      calendario.push({ id: `cal-${inst.isin}-${i}`, ...fila });
    }
  }

  const precios = [];
  // Portafolio de una sola moneda: sin tipos de cambio que cargar.
  const fx = [];
  const rnd = aleatorio(20260914);
  const deriva = { ...PRECIO_BASE };

  for (const fecha of rangoFechas(desde, hasta)) {
    if (!esHabil(fecha, feriadosUS)) continue;
    for (const inst of INSTRUMENTOS) {
      deriva[inst.isin] += (rnd() - 0.48) * 0.18;
      precios.push({
        id: `px-${inst.isin}-${fecha}`, isin: inst.isin, fecha,
        precioLimpio: Number(deriva[inst.isin].toFixed(4)),
        fuente: inst.fuente, ts: `${fecha}T18:00:00.000Z`,
      });
    }
  }

  const operaciones = [
    { id: 'op-001', ts: '2026-09-01T14:00:00.000Z', tipo: 'aporte', isin: null, fechaOperacion: '2026-09-01', fechaLiquidacion: '2026-09-01', nominal: 0, precioOperacion: 0, monto: 15000000, moneda: 'USD', flujo: 'externo', reversaDe: null, comentario: 'Aporte inicial del cliente' },
    { id: 'op-002', ts: '2026-09-01T14:30:00.000Z', tipo: 'compra', isin: 'US91282CJT89', fechaOperacion: '2026-09-01', fechaLiquidacion: '2026-09-02', nominal: 4000000, precioOperacion: 98.4062, monto: 0, moneda: 'USD', flujo: 'interno', reversaDe: null, comentario: 'Armado inicial del portafolio' },
    { id: 'op-003', ts: '2026-09-01T14:35:00.000Z', tipo: 'compra', isin: 'XS2456789012', fechaOperacion: '2026-09-01', fechaLiquidacion: '2026-09-03', nominal: 3000000, precioOperacion: 101.8750, monto: 0, moneda: 'USD', flujo: 'interno', reversaDe: null, comentario: 'Armado inicial del portafolio' },
    { id: 'op-004', ts: '2026-09-02T15:00:00.000Z', tipo: 'compra', isin: 'XS9876543210', fechaOperacion: '2026-09-02', fechaLiquidacion: '2026-09-04', nominal: 2000000, precioOperacion: 99.5000, monto: 0, moneda: 'USD', flujo: 'interno', reversaDe: null, comentario: 'Tramo amortizable' },
    { id: 'op-004b', ts: '2026-09-02T15:20:00.000Z', tipo: 'compra', isin: 'PE1234567890', fechaOperacion: '2026-09-02', fechaLiquidacion: '2026-09-03', nominal: 4500000, precioOperacion: 96.2500, monto: 0, moneda: 'USD', flujo: 'interno', reversaDe: null, comentario: 'Tramo soberano' },
    { id: 'op-005', ts: '2026-09-09T16:00:00.000Z', tipo: 'venta', isin: 'US91282CJT89', fechaOperacion: '2026-09-09', fechaLiquidacion: '2026-09-10', nominal: 1000000, precioOperacion: 98.7500, monto: 0, moneda: 'USD', flujo: 'interno', reversaDe: null, comentario: 'Rebalanceo del gestor (flujo interno)' },
  ];

  return {
    esquema: 1,
    config: {
      monedaReporte: 'USD', umbralBp: 1, politicaPrecio: 'stale',
      versionBHabil: true, plazaPorDefecto: 'US', fechaInicio: desde,
    },
    instrumentos: INSTRUMENTOS.map((i) => ({ ...i, fechaUltimaVerificacion: '2026-09-01' })),
    calendario, operaciones, precios, fx, feriados,
    bitacora: [{ id: 'bit-0', ts: '2026-09-01T12:00:00.000Z', accion: 'demo', detalle: 'Portafolio de demostración cargado' }],
  };
}
