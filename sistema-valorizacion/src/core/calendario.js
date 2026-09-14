// Capa 1 — generación del Calendario_Cupones a partir del maestro.
//
// El calendario se genera hacia atrás desde el vencimiento (convención de
// mercado) para que las fechas de pago caigan siempre en el mismo día de mes
// que el vencimiento. Queda como dato explícito y editable: ante una corporate
// action se corrige la fila, no la fórmula.

import { comparar, sumarMeses } from './fechas.js';
import { FRECUENCIAS } from './conteo-dias.js';

/**
 * `cuponPct` es el cupón del período por cada 100 de nominal vigente.
 * `amortPct` es el porcentaje del nominal ORIGINAL que amortiza en esa fecha.
 */
export function generarCalendario(instrumento) {
  const { isin, fechaEmision, fechaVencimiento, cupon = 0, frecuencia, tipo } = instrumento;
  const porAnio = FRECUENCIAS[frecuencia]?.porAnio ?? 0;
  const meses = FRECUENCIAS[frecuencia]?.meses ?? 0;

  if (!porAnio || !meses || tipo === 'cupon_cero') {
    return [{ isin, fechaPago: fechaVencimiento, cuponPct: 0, amortPct: 100, esUltimoPago: true }];
  }

  const fechas = [];
  let f = fechaVencimiento;
  let guarda = 0;
  while (comparar(f, fechaEmision) > 0) {
    fechas.unshift(f);
    f = sumarMeses(f, -meses);
    if (++guarda > 2000) break;
  }

  const cuponPct = cupon / porAnio;
  const amortizable = tipo === 'amortizable';
  const cuota = amortizable ? 100 / fechas.length : 0;

  return fechas.map((fechaPago, i) => {
    const ultimo = i === fechas.length - 1;
    let amortPct;
    if (!amortizable) amortPct = ultimo ? 100 : 0;
    else if (ultimo) amortPct = redondear(100 - cuota * (fechas.length - 1));
    else amortPct = redondear(cuota);
    return { isin, fechaPago, cuponPct: redondear(cuponPct, 10), amortPct, esUltimoPago: ultimo };
  });
}

function redondear(x, decimales = 8) {
  return Number(x.toFixed(decimales));
}

/** Último pago con fecha <= ref, y primer pago con fecha > ref. */
export function periodoVigente(filas, referencia, fechaEmision) {
  let inicio = fechaEmision;
  let fin = null;
  for (const fila of filas) {
    if (comparar(fila.fechaPago, referencia) <= 0) inicio = fila.fechaPago;
    else { fin = fila.fechaPago; break; }
  }
  return { inicioPeriodo: inicio, finPeriodo: fin };
}
