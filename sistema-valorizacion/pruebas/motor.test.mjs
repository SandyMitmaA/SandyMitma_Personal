import test from 'node:test';
import assert from 'node:assert/strict';

import { dias30_360, devengo } from '../src/core/conteo-dias.js';
import { sumarHabiles, siguienteHabil } from '../src/core/fechas.js';
import { generarCalendario } from '../src/core/calendario.js';
import { correrMotor, precioEn, CONFIG_POR_DEFECTO } from '../src/core/motor.js';
import { datosDemo } from '../src/datos/demo.js';

const BONO = {
  isin: 'TEST01', emisor: 'Emisor Prueba', moneda: 'USD', cupon: 6, frecuencia: 'semestral',
  fechaEmision: '2025-01-15', fechaVencimiento: '2030-01-15', baseDias: '30/360',
  convLiquidacion: 2, tipo: 'bullet', plaza: 'US',
};

function caso({ instrumentos = [BONO], operaciones = [], precios = [], fx = [], feriados = [], config = {} }) {
  const calendario = instrumentos.flatMap((i) => generarCalendario(i).map((f, n) => ({ id: `${i.isin}-${n}`, ...f })));
  return { instrumentos, calendario, operaciones, precios, fx, feriados, config: { ...CONFIG_POR_DEFECTO, ...config } };
}

const compra = (over = {}) => ({
  id: 'c1', tipo: 'compra', isin: 'TEST01', fechaOperacion: '2026-03-02', fechaLiquidacion: '2026-03-04',
  nominal: 1000000, precioOperacion: 100, monto: 0, moneda: 'USD', flujo: 'interno', reversaDe: null, ...over,
});

const px = (fecha, precioLimpio, isin = 'TEST01') => ({ id: `p-${isin}-${fecha}`, isin, fecha, precioLimpio, fuente: 'test' });

// ------------------------------------------------------- convenciones -------

test('30/360 aplica los ajustes de fin de mes', () => {
  assert.equal(dias30_360('2026-01-15', '2026-07-15'), 180);
  assert.equal(dias30_360('2026-01-31', '2026-02-28'), 28);
  assert.equal(dias30_360('2026-01-30', '2026-03-31'), 60);
  // 30/360 US (bond basis): d2 = 31 solo se lleva a 30 cuando d1 ya es 30 o 31,
  // por eso del 28-feb al 31-mar cuenta 33 días y no 32 (esa sería 30E/360).
  assert.equal(dias30_360('2026-02-28', '2026-03-31'), 33);
});

test('devengo 30/360 semestral a mitad de período', () => {
  const d = devengo({ base: '30/360', frecuencia: 'semestral', cuponAnual: 6, inicioPeriodo: '2026-01-15', finPeriodo: '2026-07-15', fechaLiquidacion: '2026-04-15' });
  assert.equal(d.diasPeriodo, 180);
  assert.equal(d.diasTranscurridos, 90);
  assert.equal(d.cuponPeriodo, 3);
  assert.equal(d.accruedPor100, 1.5);
});

test('ACT/365 devenga sobre el cupón anual y días calendario', () => {
  const d = devengo({ base: 'ACT/365', frecuencia: 'semestral', cuponAnual: 7.3, inicioPeriodo: '2026-01-01', finPeriodo: '2026-07-01', fechaLiquidacion: '2026-01-11' });
  assert.equal(d.diasTranscurridos, 10);
  assert.equal(Number(d.accruedPor100.toFixed(6)), 0.2);
});

test('el cupón cero no devenga', () => {
  const d = devengo({ base: '30/360', frecuencia: 'cero', cuponAnual: 0, inicioPeriodo: '2026-01-01', finPeriodo: '2026-07-01', fechaLiquidacion: '2026-04-01' });
  assert.equal(d.accruedPor100, 0);
});

test('T+2 y el +1 día de la Versión B saltan feriados', () => {
  const feriados = new Set(['2026-09-07']);
  assert.equal(sumarHabiles('2026-09-04', 2, feriados), '2026-09-09'); // vie → mar (lun feriado)
  assert.equal(siguienteHabil('2026-09-05', feriados), '2026-09-08');
});

// ------------------------------------------- posición vigente derivada ------

test('la posición se arrastra sola cuando no hay operaciones', () => {
  const datos = caso({
    operaciones: [compra()],
    precios: ['2026-03-02', '2026-03-03', '2026-03-04', '2026-03-05'].map((f) => px(f, 100)),
  });
  const r = correrMotor(datos, { desde: '2026-03-02', hasta: '2026-03-06' });
  const nominalDe = (f) => r.porFecha[f].posiciones.find((p) => p.isin === 'TEST01').nominal;
  assert.equal(nominalDe('2026-03-02'), 1000000);
  assert.equal(nominalDe('2026-03-06'), 1000000, 'sin operaciones el nominal se mantiene');
  assert.ok(r.porFecha['2026-03-06'].posiciones.every((p) => p.A.tmv !== null));
});

test('el control de cuadre diario se cumple todos los días', () => {
  const datos = caso({
    operaciones: [compra(), compra({ id: 'c2', tipo: 'venta', fechaOperacion: '2026-03-05', fechaLiquidacion: '2026-03-09', nominal: 400000, precioOperacion: 101 })],
    precios: ['2026-03-02', '2026-03-03', '2026-03-04', '2026-03-05', '2026-03-06', '2026-03-09'].map((f) => px(f, 100)),
  });
  const r = correrMotor(datos, { desde: '2026-03-02', hasta: '2026-03-10' });
  for (const f of r.fechas) {
    for (const c of r.porFecha[f].cuadres) assert.ok(c.cuadra, `descuadre en ${f}: ${JSON.stringify(c)}`);
  }
  assert.equal(r.porFecha['2026-03-10'].posiciones.find((p) => p.isin === 'TEST01').nominal, 600000);
});

test('la reversa netea la operación original sin borrarla', () => {
  const original = compra();
  const datos = caso({
    operaciones: [original, { ...original, id: 'c1r', tipo: 'venta', reversaDe: 'c1' }],
    precios: [px('2026-03-02', 100), px('2026-03-03', 100), px('2026-03-04', 100)],
  });
  const r = correrMotor(datos, { desde: '2026-03-02', hasta: '2026-03-04' });
  const pos = r.porFecha['2026-03-02'].posiciones.find((p) => p.isin === 'TEST01');
  assert.equal(pos.nominal, 0, 'la compra y su reversa se netean el mismo día');
  for (const f of r.fechas) {
    assert.equal(r.porFecha[f].consolidado.tmvA, 0, `la reversa no debe dejar valor residual (${f})`);
  }
  assert.equal(datos.operaciones.length, 2, 'ambos registros siguen en la tabla append-only');
});

// -------------------------------------------------- cupón y amortización ----

test('el cupón entra a caja automáticamente sin operación cargada', () => {
  const datos = caso({
    operaciones: [compra({ fechaOperacion: '2026-07-10', fechaLiquidacion: '2026-07-10' })],
    precios: ['2026-07-10', '2026-07-14', '2026-07-15', '2026-07-16'].map((f) => px(f, 100)),
  });
  const r = correrMotor(datos, { desde: '2026-07-10', hasta: '2026-07-16' });
  const dia = r.porFecha['2026-07-15'];
  const cupon = dia.movimientos.find((m) => m.origen === 'cupon');
  assert.ok(cupon, 'debe generarse el movimiento de cupón del 15-jul');
  assert.equal(cupon.monto, 30000); // 1.000.000 × 3%
  assert.equal(cupon.flujo, 'interno');
  const cajaDe = (f) => r.porFecha[f].posiciones.find((p) => p.isin === 'CASH_USD').emv;
  assert.equal(Number((cajaDe('2026-07-15') - cajaDe('2026-07-14')).toFixed(2)), 30000,
    'la caja del día del cupón sube exactamente el monto del cupón');
  assert.ok(!dia.movimientos.some((m) => m.origen === 'neto_compra'),
    'el cupón no requiere ninguna operación cargada por el usuario');
});

test('un amortizable llega a nominal cero al vencimiento y paga principal a caja', () => {
  const amort = { ...BONO, isin: 'AMO01', tipo: 'amortizable', frecuencia: 'semestral', fechaEmision: '2025-07-15', fechaVencimiento: '2026-07-15' };
  const datos = caso({
    instrumentos: [amort],
    operaciones: [compra({ isin: 'AMO01', fechaOperacion: '2026-01-02', fechaLiquidacion: '2026-01-02' })],
    precios: ['2026-01-02', '2026-01-15', '2026-07-15', '2026-07-16'].map((f) => px(f, 100, 'AMO01')),
  });
  const r = correrMotor(datos, { desde: '2026-01-02', hasta: '2026-07-16' });
  assert.equal(r.porFecha['2026-01-14'].posiciones.find((p) => p.isin === 'AMO01').nominal, 1000000);
  assert.equal(r.porFecha['2026-01-15'].posiciones.find((p) => p.isin === 'AMO01').nominal, 500000);
  assert.equal(r.porFecha['2026-07-15'].posiciones.find((p) => p.isin === 'AMO01').nominal, 0);
  // Caja final = 2 cupones (30.000 + 15.000 sobre el nominal ya amortizado)
  // + 2 amortizaciones de 500.000 − precio y accrued pagados en la compra.
  const accruedCompra = 1000000 * devengo({ base: '30/360', frecuencia: 'semestral', cuponAnual: 6,
    inicioPeriodo: '2025-07-15', finPeriodo: '2026-01-15', fechaLiquidacion: '2026-01-02' }).accruedPor100 / 100;
  const esperado = -1000000 - accruedCompra + 30000 + 15000 + 1000000;
  const caja = r.porFecha['2026-07-16'].posiciones.find((p) => p.isin === 'CASH_USD').emv;
  assert.ok(Math.abs(caja - esperado) < 0.01, `caja esperada ${esperado.toFixed(2)}, obtenida ${caja}`);
});

// ----------------------------------------------------- Versión A vs B -------

test('la Versión B devenga un día más que la Versión A cuando su liquidación es posterior', () => {
  const t0 = { ...BONO, convLiquidacion: 0 };
  const datos = caso({
    instrumentos: [t0],
    operaciones: [compra({ fechaOperacion: '2026-03-02', fechaLiquidacion: '2026-03-02' })],
    precios: [px('2026-03-03', 100)],
  });
  const r = correrMotor(datos, { desde: '2026-03-03', hasta: '2026-03-03' });
  const p = r.porFecha['2026-03-03'].posiciones.find((x) => x.isin === 'TEST01');
  assert.equal(p.A.fechaLiquidacion, '2026-03-03', 'Versión A usa T+0');
  assert.equal(p.B.fechaLiquidacion, '2026-03-04', 'Versión B usa +1 día hábil');
  assert.equal(p.B.diasTranscurridos - p.A.diasTranscurridos, 1);
  assert.ok(p.B.tmv > p.A.tmv);
  // 1 día de cupón sobre 1.000.000 al 6% base 30/360 = 166,666...
  assert.ok(Math.abs(Math.abs(p.diferenciaTMV) - 1000000 * 0.06 / 360) < 0.01);
});

test('la serie BMV/EMV se alimenta solo de la Versión A', () => {
  const datos = caso({
    operaciones: [compra({ fechaOperacion: '2026-03-02', fechaLiquidacion: '2026-03-02' })],
    precios: [px('2026-03-02', 100), px('2026-03-03', 100.5), px('2026-03-04', 99.8)],
  });
  const r = correrMotor(datos, { desde: '2026-03-02', hasta: '2026-03-04' });
  const emvAyer = r.porFecha['2026-03-03'].posiciones.find((p) => p.isin === 'TEST01').emv;
  const bmvHoy = r.porFecha['2026-03-04'].posiciones.find((p) => p.isin === 'TEST01').bmv;
  assert.equal(bmvHoy, emvAyer, 'BMV(t) debe ser exactamente EMV(t-1)');
  for (const p of r.porFecha['2026-03-04'].posiciones) assert.equal(p.emv, p.A.tmv, 'EMV = TMV de Versión A');
  const c = r.porFecha['2026-03-02'].consolidado;
  assert.equal(c.cargaInicial, true);
  assert.equal(c.bmv, c.emv, 'el primer día el BMV es el TMV inicial de carga');
});

test('el TMV consolidado no salta entre fecha de operación y liquidación', () => {
  const datos = caso({
    operaciones: [
      { id: 'ap', tipo: 'aporte', isin: null, fechaOperacion: '2026-03-02', fechaLiquidacion: '2026-03-02', nominal: 0, precioOperacion: 0, monto: 2000000, moneda: 'USD', flujo: 'externo', reversaDe: null },
      compra({ fechaOperacion: '2026-03-03', fechaLiquidacion: '2026-03-05', precioOperacion: 100 }),
    ],
    precios: ['2026-03-02', '2026-03-03', '2026-03-04', '2026-03-05'].map((f) => px(f, 100)),
  });
  const r = correrMotor(datos, { desde: '2026-03-02', hasta: '2026-03-05' });
  const dame = (f, isin) => r.porFecha[f].posiciones.find((p) => p.isin === isin)?.emv ?? 0;

  // Entre la fecha de operación (03) y la de liquidación (05) el importe vive en
  // PEND_USD; al liquidar, lo que sale de PEND entra a caja por el mismo monto,
  // de modo que el par caja + pendiente no se mueve por la liquidación.
  assert.ok(dame('2026-03-04', 'PEND_USD') !== 0, 'el importe debe estar en PEND_USD antes de liquidar');
  assert.equal(dame('2026-03-05', 'PEND_USD'), 0, 'PEND_USD se descarga al liquidar');
  const parAntes = dame('2026-03-04', 'CASH_USD') + dame('2026-03-04', 'PEND_USD');
  const parDespues = dame('2026-03-05', 'CASH_USD') + dame('2026-03-05', 'PEND_USD');
  assert.ok(Math.abs(parAntes - parDespues) < 0.01, `caja + pendiente cambió al liquidar: ${parAntes} → ${parDespues}`);

  // Y todo el movimiento del TMV total entre esos dos días es devengo del bono,
  // no el asiento de liquidación.
  const total = (f) => r.porFecha[f].consolidado.tmvA;
  const bono = (f) => r.porFecha[f].posiciones.find((p) => p.isin === 'TEST01').A;
  const deltaDevengo = bono('2026-03-05').accrued - bono('2026-03-04').accrued;
  assert.ok(Math.abs(total('2026-03-05') - total('2026-03-04') - deltaDevengo) < 0.01);
});

test('el flujo externo del día queda separado del interno', () => {
  const datos = caso({
    operaciones: [
      { id: 'ap', tipo: 'aporte', isin: null, fechaOperacion: '2026-03-02', fechaLiquidacion: '2026-03-02', nominal: 0, precioOperacion: 0, monto: 500000, moneda: 'USD', flujo: 'externo', reversaDe: null },
      compra({ fechaOperacion: '2026-03-02', fechaLiquidacion: '2026-03-02', nominal: 100000 }),
    ],
    precios: [px('2026-03-02', 100)],
  });
  const r = correrMotor(datos, { desde: '2026-03-02', hasta: '2026-03-02' });
  assert.equal(r.porFecha['2026-03-02'].consolidado.flujoExterno, 500000);
});

// ----------------------------------------------------- política de precios --

test('la política de precio faltante arrastra con marca stale o marca error', () => {
  const indice = new Map([['TEST01', [px('2026-03-02', 99.5)]]]);
  assert.deepEqual(precioEn(indice, 'TEST01', '2026-03-02', 'stale').estado, 'oficial');
  const arrastrado = precioEn(indice, 'TEST01', '2026-03-05', 'stale');
  assert.equal(arrastrado.estado, 'stale');
  assert.equal(arrastrado.valor, 99.5);
  assert.equal(precioEn(indice, 'TEST01', '2026-03-05', 'error').estado, 'faltante');
  assert.equal(precioEn(indice, 'TEST01', '2026-03-01', 'stale').estado, 'faltante', 'nunca se usa un precio futuro');
});

test('sin precio y con política de error la valorización no falla en silencio', () => {
  const datos = caso({
    operaciones: [compra({ fechaOperacion: '2026-03-02', fechaLiquidacion: '2026-03-02' })],
    precios: [],
    config: { politicaPrecio: 'error' },
  });
  const r = correrMotor(datos, { desde: '2026-03-02', hasta: '2026-03-02' });
  const p = r.porFecha['2026-03-02'].posiciones.find((x) => x.isin === 'TEST01');
  assert.equal(p.A.tmv, null);
  assert.ok(r.porFecha['2026-03-02'].alertas.some((a) => a.nivel === 'error' && /Sin precio/.test(a.mensaje)));
});

// ---------------------------------------------------------------- FX --------

test('el FX convierte a moneda de reporte y avisa si falta', () => {
  const pen = { ...BONO, isin: 'PEN01', moneda: 'PEN' };
  const datos = caso({
    instrumentos: [pen],
    operaciones: [compra({ isin: 'PEN01', fechaOperacion: '2026-03-02', fechaLiquidacion: '2026-03-02' })],
    precios: [px('2026-03-02', 100, 'PEN01'), px('2026-03-03', 100, 'PEN01')],
    fx: [{ id: 'f1', par: 'USD/PEN', fecha: '2026-03-02', tipo: 4, fuente: 'test' }],
    config: { monedaReporte: 'USD' },
  });
  const r = correrMotor(datos, { desde: '2026-03-02', hasta: '2026-03-02' });
  const p = r.porFecha['2026-03-02'].posiciones.find((x) => x.isin === 'PEN01');
  assert.equal(p.fx.estado, 'inverso');
  assert.ok(Math.abs(p.emvReporte - p.emv / 4) < 1e-6);
});

// -------------------------------------------------------------- demo --------

test('el portafolio de demostración corre limpio y cuadra', () => {
  const datos = datosDemo();
  const r = correrMotor(datos, { desde: '2026-09-01', hasta: '2026-09-14' });
  assert.equal(r.fechas.length, 14);
  for (const f of r.fechas) {
    for (const c of r.porFecha[f].cuadres) assert.ok(c.cuadra, `descuadre en ${f}`);
    assert.ok(!r.porFecha[f].alertas.some((a) => a.nivel === 'error'), `alerta de error en ${f}: ${JSON.stringify(r.porFecha[f].alertas)}`);
  }
  const ult = r.porFecha['2026-09-14'].consolidado;
  assert.ok(ult.emv > 0 && ult.bmv > 0);
  assert.ok(r.porFecha['2026-09-08'].movimientos.some((m) => m.origen === 'cupon'));
  assert.ok(r.porFecha['2026-09-10'].movimientos.some((m) => m.origen === 'amortizacion'));
  assert.equal(r.porFecha['2026-09-01'].consolidado.flujoExterno, 15000000);
  assert.ok(datos.instrumentos.every((i) => i.moneda === 'USD'), 'el portafolio de demostración es íntegramente en dólares');
});

// ------------------------------------------ continuidad alrededor del cupón --

test('la liquidación que cruza una fecha de cupón no crea un salto ficticio de valor', () => {
  // Con el precio congelado y sin flujos externos, el valor del portafolio solo
  // puede subir por devengo. Si el accrued se reinicia al cruzar el cupón sin
  // puentear el cobro, aparece una caída del tamaño del cupón y, días después,
  // un rebote: dos retornos diarios falsos que contaminarían el TWRR.
  const datos = caso({
    operaciones: [compra({ fechaOperacion: '2026-07-01', fechaLiquidacion: '2026-07-01' })],
    precios: [...Array(30)].map((_, i) => px(`2026-07-${String(i + 1).padStart(2, '0')}`, 100)),
  });
  const r = correrMotor(datos, { desde: '2026-07-08', hasta: '2026-07-22' });
  const cuponDiario = 1000000 * 0.06 / 360; // 166,67 por día

  let previo = null;
  for (const f of r.fechas) {
    const total = r.porFecha[f].consolidado.emv;
    if (previo !== null) {
      const delta = total - previo;
      assert.ok(delta >= -0.01, `el valor cayó ${delta.toFixed(2)} el ${f} sin que se moviera el precio`);
      assert.ok(delta <= cuponDiario * 5, `salto de ${delta.toFixed(2)} el ${f}: excede lo que puede devengarse en un día`);
    }
    previo = total;
  }

  // El cupón ya devengado y aún no cobrado se muestra explícitamente.
  const cruce = r.fechas.find((f) => r.porFecha[f].posiciones.find((p) => p.isin === 'TEST01')?.A.cobroPendiente > 0);
  assert.ok(cruce, 'debe existir al menos un día con cupón devengado pendiente de cobro');
  const p = r.porFecha[cruce].posiciones.find((x) => x.isin === 'TEST01');
  assert.equal(p.A.cobroPendiente, 30000, 'el puente vale exactamente el cupón del período');
  assert.ok(Math.abs(p.A.tmv - (p.A.smv + p.A.accrued + p.A.cobroPendiente)) < 0.01, 'TMV = SMV + accrued + cobro pendiente');
});

test('el portafolio de demostración tampoco salta si se congelan los precios', () => {
  const datos = datosDemo();
  for (const p of datos.precios) p.precioLimpio = 100;
  for (const o of datos.operaciones) if (o.precioOperacion) o.precioOperacion = 100;
  const r = correrMotor(datos, { desde: '2026-09-01', hasta: '2026-09-14' });

  let previo = null;
  for (const f of r.fechas) {
    const c = r.porFecha[f].consolidado;
    const total = c.emv - c.flujoExterno;
    if (previo !== null) {
      assert.ok(total - previo >= -0.01, `el portafolio cayó ${(total - previo).toFixed(2)} el ${f} con precios congelados`);
      assert.ok(total - previo < 5000, `salto de ${(total - previo).toFixed(2)} el ${f}: parece un cupón mal puenteado`);
    }
    previo = c.emv;
  }
});

test('el consolidado no mezcla monedas: todo va convertido a la moneda de reporte', () => {
  const pen = { ...BONO, isin: 'PEN01', moneda: 'PEN' };
  const datos = caso({
    instrumentos: [BONO, pen],
    operaciones: [
      compra({ fechaOperacion: '2026-03-02', fechaLiquidacion: '2026-03-02' }),
      compra({ id: 'c2', isin: 'PEN01', fechaOperacion: '2026-03-02', fechaLiquidacion: '2026-03-02' }),
    ],
    precios: [px('2026-03-02', 100), px('2026-03-02', 100, 'PEN01')],
    fx: [{ id: 'f1', par: 'USD/PEN', fecha: '2026-03-02', tipo: 4, fuente: 'test' }],
    config: { monedaReporte: 'USD' },
  });
  const c = correrMotor(datos, { desde: '2026-03-02', hasta: '2026-03-02' }).porFecha['2026-03-02'].consolidado;

  // El bono en soles vale lo mismo en nominal que el de dólares, así que su
  // aporte al consolidado debe ser exactamente la cuarta parte.
  const posiciones = correrMotor(datos, { desde: '2026-03-02', hasta: '2026-03-02' }).porFecha['2026-03-02'].posiciones;
  const esperadoTMV = posiciones.reduce((s, p) => s + (p.A.tmv || 0) * (p.fx.tasa ?? 0), 0);
  assert.ok(Math.abs(c.tmvA - esperadoTMV) < 0.01, `TMV consolidado sin convertir: ${c.tmvA} vs ${esperadoTMV}`);
  assert.ok(Math.abs(c.tmvA - c.emv) < 0.01, 'el TMV de Versión A consolidado es el EMV del portafolio');
  const smvConvertido = posiciones.reduce((s, p) => s + (p.A.smv || 0) * (p.fx.tasa ?? 0), 0);
  const smvCrudo = posiciones.reduce((s, p) => s + (p.A.smv || 0), 0);
  assert.ok(Math.abs(c.smvA - smvConvertido) < 0.01, 'el SMV consolidado debe venir convertido');
  assert.ok(Math.abs(c.smvA - smvCrudo) > 0.01, 'y no puede coincidir con la suma cruda de dólares y soles');
  assert.ok(Math.abs(c.accruedA - posiciones.reduce((s, p) => s + (p.A.accrued || 0) * (p.fx.tasa ?? 0), 0)) < 0.01);
});
