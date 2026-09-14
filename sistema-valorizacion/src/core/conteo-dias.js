// Capa 0 — convenciones de conteo de días y devengo (accrued).

import { desdeISO, diasCalendario } from './fechas.js';

export const BASES = ['30/360', 'ACT/ACT', 'ACT/365', 'ACT/360'];

export const FRECUENCIAS = {
  anual: { etiqueta: 'Anual', meses: 12, porAnio: 1 },
  semestral: { etiqueta: 'Semestral', meses: 6, porAnio: 2 },
  trimestral: { etiqueta: 'Trimestral', meses: 3, porAnio: 4 },
  mensual: { etiqueta: 'Mensual', meses: 1, porAnio: 12 },
  cero: { etiqueta: 'Cupón cero', meses: 0, porAnio: 0 },
};

/** Convención 30/360 US (bond basis). */
export function dias30_360(iso1, iso2) {
  const f1 = desdeISO(iso1);
  const f2 = desdeISO(iso2);
  const y1 = f1.getUTCFullYear();
  const m1 = f1.getUTCMonth() + 1;
  const y2 = f2.getUTCFullYear();
  const m2 = f2.getUTCMonth() + 1;
  let d1 = f1.getUTCDate();
  let d2 = f2.getUTCDate();
  if (d1 === 31) d1 = 30;
  if (d2 === 31 && d1 >= 30) d2 = 30;
  return 360 * (y2 - y1) + 30 * (m2 - m1) + (d2 - d1);
}

export function diasEntre(base, iso1, iso2) {
  return base === '30/360' ? dias30_360(iso1, iso2) : diasCalendario(iso1, iso2);
}

/**
 * Devengo del período corriente, expresado por cada 100 de nominal vigente.
 *
 * `inicioPeriodo` es la fecha del último cupón (o la emisión) anterior o igual a
 * la fecha de liquidación, y `finPeriodo` la del cupón siguiente. El devengo se
 * cuenta desde el inicio del período inclusive hasta la fecha de liquidación
 * exclusive, que es la convención de mercado.
 *
 * @returns {{diasTranscurridos:number, diasPeriodo:number, cuponPeriodo:number, accruedPor100:number}}
 */
export function devengo({ base, frecuencia, cuponAnual, inicioPeriodo, finPeriodo, fechaLiquidacion }) {
  const porAnio = FRECUENCIAS[frecuencia]?.porAnio ?? 0;
  if (!porAnio || !cuponAnual) {
    // Cupón cero: no devenga.
    return { diasTranscurridos: 0, diasPeriodo: 0, cuponPeriodo: 0, accruedPor100: 0 };
  }
  const diasTranscurridos = Math.max(0, diasEntre(base, inicioPeriodo, fechaLiquidacion));
  const diasPeriodo = Math.max(1, diasEntre(base, inicioPeriodo, finPeriodo));
  const cuponPeriodo = cuponAnual / porAnio;

  let accruedPor100;
  if (base === 'ACT/365') accruedPor100 = (cuponAnual * diasTranscurridos) / 365;
  else if (base === 'ACT/360') accruedPor100 = (cuponAnual * diasTranscurridos) / 360;
  else accruedPor100 = (cuponPeriodo * diasTranscurridos) / diasPeriodo; // 30/360 y ACT/ACT (ICMA)

  return { diasTranscurridos, diasPeriodo, cuponPeriodo, accruedPor100 };
}
