// Capa 2 — Motor de valorización (datos calculados, nunca editables a mano).
//
// Reglas que este módulo garantiza por construcción:
//  1. La posición vigente NUNCA se carga: se deriva de posición(t-1) ±
//     operaciones del día ± amortizaciones del Calendario_Cupones.
//  2. Cupones y amortizaciones se generan desde el calendario, jamás como
//     operación del usuario.
//  3. La caja es una posición más del portafolio (ISIN sintético CASH_<MON>).
//     Las compras/ventas entre fecha de operación y fecha de liquidación viven
//     en una posición sintética PEND_<MON>, de modo que el TMV total no salta
//     entre trade date y settlement date.
//  4. Todo flujo de caja nace marcado como interno o externo.
//  6. La serie BMV/EMV que se arrastra día a día es SIEMPRE la de Versión A.

import { comparar, rangoFechas, siguienteHabil, sumarDias, sumarHabiles, esHabil } from './fechas.js';
import { devengo, FRECUENCIAS } from './conteo-dias.js';
import { periodoVigente } from './calendario.js';
import { indexarFX, tipoCambio } from './fx.js';

export const CONFIG_POR_DEFECTO = {
  monedaReporte: 'USD',
  umbralBp: 1, // alerta si |TMV_A − TMV_B| supera este nº de bp del nominal
  politicaPrecio: 'stale', // 'stale' = arrastrar último precio marcado | 'error'
  versionBHabil: true, // Versión B = fecha de valorización + 1 día hábil
  plazaPorDefecto: 'US',
  fechaInicio: null, // null = primera fecha con actividad
};

const redondear = (x, d = 8) => (Number.isFinite(x) ? Number(x.toFixed(d)) : x);

// ---------------------------------------------------------------- índices ---

function indexarPrecios(precios = []) {
  const porISIN = new Map();
  for (const p of precios) {
    if (!porISIN.has(p.isin)) porISIN.set(p.isin, []);
    porISIN.get(p.isin).push(p);
  }
  for (const lista of porISIN.values()) lista.sort((a, b) => comparar(a.fecha, b.fecha));
  return porISIN;
}

function indexarFeriados(feriados = []) {
  const porPlaza = new Map();
  for (const f of feriados) {
    if (!porPlaza.has(f.plaza)) porPlaza.set(f.plaza, new Set());
    porPlaza.get(f.plaza).add(f.fecha);
  }
  return porPlaza;
}

function agrupar(filas, clave) {
  const mapa = new Map();
  for (const fila of filas) {
    const k = fila[clave];
    if (!mapa.has(k)) mapa.set(k, []);
    mapa.get(k).push(fila);
  }
  return mapa;
}

/** Precio limpio aplicando la política explícita de precio faltante (regla 9). */
export function precioEn(indice, isin, fecha, politica = 'stale') {
  const lista = indice.get(isin) || [];
  let ultimo = null;
  for (const p of lista) {
    if (comparar(p.fecha, fecha) <= 0) ultimo = p;
    else break;
  }
  if (ultimo && ultimo.fecha === fecha) {
    return { valor: Number(ultimo.precioLimpio), estado: 'oficial', fuente: ultimo.fuente, fechaPrecio: ultimo.fecha };
  }
  if (ultimo && politica === 'stale') {
    return { valor: Number(ultimo.precioLimpio), estado: 'stale', fuente: ultimo.fuente, fechaPrecio: ultimo.fecha };
  }
  return { valor: null, estado: 'faltante', fuente: null, fechaPrecio: null };
}

// --------------------------------------------------------------- devengo ----

/**
 * Devengo de un instrumento a una fecha de liquidación dada, por 100 de nominal.
 * Si la liquidación cae después de un cupón, el período rueda automáticamente.
 */
export function devengoInstrumento(instrumento, filasCalendario, fechaLiquidacion) {
  if (instrumento.tipo === 'cupon_cero' || !FRECUENCIAS[instrumento.frecuencia]?.porAnio) {
    return { diasTranscurridos: 0, diasPeriodo: 0, cuponPeriodo: 0, accruedPor100: 0, inicioPeriodo: null, finPeriodo: null };
  }
  const { inicioPeriodo, finPeriodo } = periodoVigente(filasCalendario, fechaLiquidacion, instrumento.fechaEmision);
  if (!finPeriodo) {
    // Ya venció: no hay período corriente.
    return { diasTranscurridos: 0, diasPeriodo: 0, cuponPeriodo: 0, accruedPor100: 0, inicioPeriodo, finPeriodo: null };
  }
  const d = devengo({
    base: instrumento.baseDias,
    frecuencia: instrumento.frecuencia,
    cuponAnual: Number(instrumento.cupon) || 0,
    inicioPeriodo,
    finPeriodo,
    fechaLiquidacion,
  });
  return { ...d, inicioPeriodo, finPeriodo };
}

// ------------------------------------------------------------ motor diario --

export function correrMotor(datos, opciones = {}) {
  const config = { ...CONFIG_POR_DEFECTO, ...(datos.config || {}) };
  const instrumentos = datos.instrumentos || [];
  const operaciones = (datos.operaciones || []).slice().sort((a, b) => comparar(a.fechaOperacion, b.fechaOperacion));
  const calendario = agrupar(datos.calendario || [], 'isin');
  for (const filas of calendario.values()) filas.sort((a, b) => comparar(a.fechaPago, b.fechaPago));

  const idxPrecios = indexarPrecios(datos.precios);
  const idxFX = indexarFX(datos.fx);
  const idxFeriados = indexarFeriados(datos.feriados);
  const feriadosDe = (plaza) => idxFeriados.get(plaza || config.plazaPorDefecto) || new Set();

  const porISIN = new Map(instrumentos.map((i) => [i.isin, i]));

  const fechasActividad = [
    ...operaciones.map((o) => o.fechaOperacion),
    ...operaciones.map((o) => o.fechaLiquidacion).filter(Boolean),
  ].filter(Boolean).sort(comparar);

  // El motor SIEMPRE acumula desde el inicio real del portafolio: una operación
  // anterior a la ventana pedida no puede quedar fuera de la posición vigente.
  // `desde` solo recorta las fechas que se devuelven.
  const inicio = config.fechaInicio || fechasActividad[0];
  const desde = opciones.desde && comparar(opciones.desde, inicio || opciones.desde) >= 0 ? opciones.desde : inicio;
  const hasta = opciones.hasta || desde;
  if (!inicio || !hasta || comparar(inicio, hasta) > 0) {
    return { fechas: [], porFecha: {}, config, vacio: true, inicio: inicio || null };
  }

  // Operaciones indexadas por fecha de operación y por fecha de liquidación.
  const opsPorOperacion = agrupar(operaciones, 'fechaOperacion');
  const opsPorLiquidacion = agrupar(operaciones.filter((o) => o.fechaLiquidacion), 'fechaLiquidacion');
  const cupsPorFecha = new Map();
  for (const filas of calendario.values()) {
    for (const fila of filas) {
      if (!cupsPorFecha.has(fila.fechaPago)) cupsPorFecha.set(fila.fechaPago, []);
      cupsPorFecha.get(fila.fechaPago).push(fila);
    }
  }

  // Estado que se arrastra de un día al siguiente.
  const nominal = new Map();          // isin -> nominal vigente
  const factorPendiente = new Map();  // isin -> fracción del principal aún viva
  const caja = new Map();             // moneda -> saldo
  const pendiente = new Map();        // moneda -> neto por liquidar
  const emvAnterior = new Map();      // clave de posición -> EMV (Versión A) de ayer
  const emvAnteriorReporte = new Map();

  const monedas = new Set([config.monedaReporte, ...instrumentos.map((i) => i.moneda)]);
  for (const m of monedas) { caja.set(m, 0); pendiente.set(m, 0); }

  const recorrido = rangoFechas(inicio, hasta);
  const fechas = recorrido.filter((f) => comparar(f, desde) >= 0);
  const porFecha = {};
  let primeraFecha = true;

  for (const fecha of recorrido) {
    const movimientos = [];
    const alertas = [];
    const cuadres = [];
    const nominalInicioDia = new Map(nominal);
    const amortAplicada = new Map();

    // --- 1. Cupones y amortizaciones del calendario (automáticos) ----------
    for (const fila of cupsPorFecha.get(fecha) || []) {
      const inst = porISIN.get(fila.isin);
      if (!inst) continue;
      const nominalInicio = nominal.get(fila.isin) || 0;
      if (nominalInicio === 0) continue;

      const cupon = (nominalInicio * Number(fila.cuponPct || 0)) / 100;
      if (cupon) {
        caja.set(inst.moneda, (caja.get(inst.moneda) || 0) + cupon);
        movimientos.push({ fecha, moneda: inst.moneda, monto: redondear(cupon, 6), origen: 'cupon', flujo: 'interno', detalle: `Cupón ${fila.isin}` });
      }

      const pct = Number(fila.amortPct || 0);
      if (pct > 0) {
        const factorAntes = factorPendiente.get(fila.isin) ?? 1;
        const proporcion = factorAntes > 0 ? Math.min(1, pct / 100 / factorAntes) : 0;
        const amortNominal = nominalInicio * proporcion;
        nominal.set(fila.isin, redondear(nominalInicio - amortNominal, 6));
        factorPendiente.set(fila.isin, Math.max(0, redondear(factorAntes - pct / 100, 10)));
        amortAplicada.set(fila.isin, redondear((amortAplicada.get(fila.isin) || 0) + amortNominal, 6));
        if (amortNominal) {
          caja.set(inst.moneda, (caja.get(inst.moneda) || 0) + amortNominal);
          movimientos.push({ fecha, moneda: inst.moneda, monto: redondear(amortNominal, 6), origen: 'amortizacion', flujo: 'interno', detalle: `Amortización ${fila.isin} (${pct}%)` });
        }
      }
    }

    // --- 2. Liquidación de operaciones (caja) ------------------------------
    for (const op of opsPorLiquidacion.get(fecha) || []) {
      const mov = importeOperacion(op, porISIN, calendario);
      if (mov.monto === 0) continue;
      caja.set(mov.moneda, (caja.get(mov.moneda) || 0) + mov.monto);
      if ((op.tipo === 'compra' || op.tipo === 'venta') && comparar(op.fechaLiquidacion, op.fechaOperacion) > 0) {
        // Solo se descarga lo que se cargó en PEND_<MON> el día de la operación.
        pendiente.set(mov.moneda, redondear((pendiente.get(mov.moneda) || 0) - mov.monto, 6));
      }
      movimientos.push({ fecha, moneda: mov.moneda, monto: redondear(mov.monto, 6), origen: mov.origen, flujo: op.flujo || (op.tipo === 'aporte' || op.tipo === 'rescate' ? 'externo' : 'interno'), detalle: mov.detalle });
    }

    // --- 3. Operaciones del día (posición, trade date) ---------------------
    const netoOperaciones = new Map();
    for (const op of opsPorOperacion.get(fecha) || []) {
      if (op.tipo !== 'compra' && op.tipo !== 'venta') continue;
      const signo = op.tipo === 'compra' ? 1 : -1;
      const delta = signo * Number(op.nominal || 0);
      nominal.set(op.isin, redondear((nominal.get(op.isin) || 0) + delta, 6));
      netoOperaciones.set(op.isin, (netoOperaciones.get(op.isin) || 0) + delta);
      if (!factorPendiente.has(op.isin)) factorPendiente.set(op.isin, factorVigente(calendario.get(op.isin) || [], fecha));

      // Entre trade date y settlement date el importe vive en PEND_<MON>.
      if (op.fechaLiquidacion && comparar(op.fechaLiquidacion, fecha) > 0) {
        const mov = importeOperacion(op, porISIN, calendario);
        pendiente.set(mov.moneda, redondear((pendiente.get(mov.moneda) || 0) + mov.monto, 6));
      }
    }

    // --- 4. Valorización posición por posición -----------------------------
    const posiciones = [];

    for (const inst of instrumentos) {
      const nom = nominal.get(inst.isin) || 0;
      if (nom === 0 && !Math.abs(emvAnterior.get(inst.isin) || 0) && !netoOperaciones.has(inst.isin)) continue;

      const filas = calendario.get(inst.isin) || [];
      const precio = precioEn(idxPrecios, inst.isin, fecha, config.politicaPrecio);
      const feriados = feriadosDe(inst.plaza);

      const fechaLiqA = sumarHabiles(fecha, Number(inst.convLiquidacion ?? 2), feriados);
      const fechaLiqB = config.versionBHabil
        ? siguienteHabil(sumarDias(fecha, 1), feriados)
        : sumarDias(fecha, 1);

      const A = valorizar(inst, filas, nom, precio.valor, fechaLiqA, fecha);
      const B = valorizar(inst, filas, nom, precio.valor, fechaLiqB, fecha);

      const fx = tipoCambio(idxFX, fecha, inst.moneda, config.monedaReporte);
      const emv = A.tmv;
      const emvReporte = fx.tasa != null && emv != null ? emv * fx.tasa : null;
      const bmv = primeraFecha ? emv : (emvAnterior.get(inst.isin) ?? 0);
      const bmvReporte = primeraFecha ? emvReporte : (emvAnteriorReporte.get(inst.isin) ?? 0);

      const diferencia = A.tmv != null && B.tmv != null ? A.tmv - B.tmv : null;
      const umbral = (Math.abs(nom) * config.umbralBp) / 10000;
      const excedeUmbral = diferencia != null && Math.abs(diferencia) > umbral && umbral >= 0;

      posiciones.push({
        isin: inst.isin, nombre: inst.emisor, tipoPosicion: 'bono', moneda: inst.moneda,
        nominal: redondear(nom, 6), precio, A, B,
        diferenciaTMV: diferencia == null ? null : redondear(diferencia, 6),
        umbral: redondear(umbral, 6), excedeUmbral,
        fx, emv: redondear(emv, 6), bmv: redondear(bmv, 6),
        emvReporte: redondear(emvReporte, 6), bmvReporte: redondear(bmvReporte, 6),
        tmvReporte: redondear(emvReporte, 6),
      });

      if (precio.estado === 'faltante') alertas.push({ nivel: 'error', isin: inst.isin, mensaje: `Sin precio para ${inst.isin} al ${fecha} (política: ${config.politicaPrecio}).` });
      else if (precio.estado === 'stale') alertas.push({ nivel: 'aviso', isin: inst.isin, mensaje: `Precio arrastrado (stale) de ${inst.isin}: cotización del ${precio.fechaPrecio}.` });
      if (fx.estado === 'faltante') alertas.push({ nivel: 'error', isin: inst.isin, mensaje: `Sin tipo de cambio ${inst.moneda}/${config.monedaReporte} al ${fecha}.` });
      if (excedeUmbral) alertas.push({ nivel: 'aviso', isin: inst.isin, mensaje: `|TMV A − TMV B| = ${Math.abs(diferencia).toFixed(2)} supera el umbral de ${config.umbralBp} bp (${umbral.toFixed(2)}).` });
      if (nom < 0) alertas.push({ nivel: 'error', isin: inst.isin, mensaje: `Nominal vigente negativo (${nom}). Revise las operaciones.` });
      if (nom > 0 && comparar(fecha, inst.fechaVencimiento) > 0) alertas.push({ nivel: 'error', isin: inst.isin, mensaje: `Posición viva después del vencimiento (${inst.fechaVencimiento}). Revise el Calendario_Cupones.` });

      // Control de cuadre diario obligatorio (regla 7): la identidad se
      // recalcula desde los inputs crudos y se compara contra el nominal que
      // realmente arrastra el motor, para que el control detecte un doble
      // conteo en lugar de repetir la misma fórmula.
      const ops = (opsPorOperacion.get(fecha) || []).filter((o) => o.isin === inst.isin && (o.tipo === 'compra' || o.tipo === 'venta'));
      const netoOps = ops.reduce((acc, o) => acc + (o.tipo === 'compra' ? 1 : -1) * Number(o.nominal || 0), 0);
      const amort = amortAplicada.get(inst.isin) || 0;
      const anterior = nominalInicioDia.get(inst.isin) || 0;
      const esperado = redondear(anterior + netoOps - amort, 6);
      const cuadra = Math.abs(esperado - redondear(nom, 6)) < 1e-6;
      cuadres.push({ isin: inst.isin, nominalAnterior: redondear(anterior, 6), netoOps: redondear(netoOps, 6), amortizacion: redondear(amort, 6), esperado, nominalFinal: redondear(nom, 6), cuadra });
      if (!cuadra) alertas.push({ nivel: 'error', isin: inst.isin, mensaje: `Descuadre de posición: ${anterior} + ${netoOps} − ${amort} ≠ ${nom}.` });
    }

    // Posiciones sintéticas: caja y liquidaciones pendientes.
    for (const moneda of monedas) {
      const saldo = redondear(caja.get(moneda) || 0, 6);
      const pend = redondear(pendiente.get(moneda) || 0, 6);
      for (const [clave, valor, etiqueta, tipoPos] of [
        [`CASH_${moneda}`, saldo, `Caja ${moneda}`, 'caja'],
        [`PEND_${moneda}`, pend, `Liquidaciones pendientes ${moneda}`, 'pendiente'],
      ]) {
        if (valor === 0 && !(emvAnterior.get(clave))) continue;
        const fx = tipoCambio(idxFX, fecha, moneda, config.monedaReporte);
        const plano = { fechaLiquidacion: fecha, diasTranscurridos: 0, diasPeriodo: 0, cuponPeriodo: 0, accruedPor100: 0, accrued: 0, cobroPendiente: 0, precioLimpio: 100, precioSucio: 100, smv: valor, tmv: valor };
        const emvReporte = fx.tasa != null ? valor * fx.tasa : null;
        posiciones.push({
          isin: clave, nombre: etiqueta, tipoPosicion: tipoPos, moneda, nominal: valor,
          precio: { valor: 100, estado: 'sintetico', fuente: 'motor', fechaPrecio: fecha },
          A: plano, B: { ...plano }, diferenciaTMV: 0, umbral: 0, excedeUmbral: false, fx,
          emv: valor, bmv: primeraFecha ? valor : (emvAnterior.get(clave) ?? 0),
          emvReporte: redondear(emvReporte, 6),
          bmvReporte: primeraFecha ? redondear(emvReporte, 6) : (emvAnteriorReporte.get(clave) ?? 0),
          tmvReporte: redondear(emvReporte, 6),
        });
        if (tipoPos === 'caja' && valor < 0) alertas.push({ nivel: 'aviso', isin: clave, mensaje: `Caja ${moneda} negativa (${valor.toFixed(2)}): sobregiro implícito.` });
      }
    }

    // --- 5. Consolidado del portafolio ------------------------------------
    const suma = (f) => posiciones.reduce((s, p) => s + (Number(f(p)) || 0), 0);
    // Todo lo que se consolida a nivel de portafolio va en la moneda de reporte:
    // sumar importes de monedas distintas sin convertir no significa nada.
    const sumaReporte = (f) => posiciones.reduce((s, p) => {
      const valor = Number(f(p));
      const tasa = p.fx?.tasa;
      return s + (Number.isFinite(valor) && tasa != null ? valor * tasa : 0);
    }, 0);
    // F(t) alimenta la fórmula de retorno contra un V(t) expresado en la moneda
    // de reporte, así que cada flujo externo se convierte con el mismo criterio
    // de FX que las posiciones; si falta la cotización, se marca la alerta.
    let flujoExterno = 0;
    for (const m of movimientos) {
      if (m.flujo !== 'externo') continue;
      const fxMov = tipoCambio(idxFX, fecha, m.moneda, config.monedaReporte);
      if (fxMov.tasa == null) {
        alertas.push({ nivel: 'error', isin: `CASH_${m.moneda}`, mensaje: `Flujo externo de ${m.moneda} sin tipo de cambio al ${fecha}: no puede expresarse en ${config.monedaReporte}.` });
        continue;
      }
      flujoExterno += m.monto * fxMov.tasa;
    }

    const consolidado = {
      fecha,
      esHabil: esHabil(fecha, feriadosDe(config.plazaPorDefecto)),
      cargaInicial: primeraFecha,
      monedaReporte: config.monedaReporte,
      smvA: redondear(sumaReporte((p) => p.A.smv), 2),
      accruedA: redondear(sumaReporte((p) => p.A.accrued), 2),
      cobroPendienteA: redondear(sumaReporte((p) => p.A.cobroPendiente), 2),
      tmvA: redondear(sumaReporte((p) => p.A.tmv), 2),
      tmvB: redondear(sumaReporte((p) => p.B.tmv), 2),
      diferenciaAB: redondear(sumaReporte((p) => p.A.tmv) - sumaReporte((p) => p.B.tmv), 2),
      bmv: redondear(suma((p) => p.bmvReporte), 2),
      emv: redondear(suma((p) => p.emvReporte), 2),
      tmvReporte: redondear(suma((p) => p.tmvReporte), 2),
      flujoExterno: redondear(flujoExterno, 2),
      nPosiciones: posiciones.length,
    };

    if (comparar(fecha, desde) >= 0) {
      porFecha[fecha] = { fecha, posiciones, movimientos, alertas, cuadres, consolidado };
    }

    // El EMV de hoy es el BMV de mañana. Solo Versión A alimenta la serie.
    emvAnterior.clear();
    emvAnteriorReporte.clear();
    for (const p of posiciones) {
      emvAnterior.set(p.isin, p.emv ?? 0);
      emvAnteriorReporte.set(p.isin, p.emvReporte ?? 0);
    }
    primeraFecha = false;
  }

  return { fechas, porFecha, config, inicio, vacio: fechas.length === 0 };
}

// ------------------------------------------------------------- auxiliares ---

/**
 * Cupón ya devengado en su totalidad pero todavía no cobrado.
 *
 * Cuando la fecha de liquidación de una versión cruza una fecha de pago que aún
 * no ocurrió, el devengo se reinicia en el período nuevo (así lo manda la
 * convención de mercado) pero el efectivo del cupón todavía no entró a caja. Sin
 * este puente el valor del portafolio muestra una caída ficticia el día que la
 * liquidación cruza el cupón y un salto ficticio el día del pago — es decir, un
 * retorno diario falso que en la Fase 2 se encadenaría al TWRR oficial.
 *
 * Solo se puentea el cupón: el principal de una amortización sigue reflejado en
 * el SMV mientras el nominal no se reduzca, así que incluirlo sería duplicarlo.
 */
function cobroPendiente(filasCalendario, nominal, fechaValorizacion, fechaLiquidacion) {
  let total = 0;
  for (const fila of filasCalendario) {
    if (comparar(fila.fechaPago, fechaValorizacion) > 0 && comparar(fila.fechaPago, fechaLiquidacion) <= 0) {
      total += (nominal * Number(fila.cuponPct || 0)) / 100;
    }
  }
  return total;
}

function valorizar(instrumento, filasCalendario, nominal, precioLimpio, fechaLiquidacion, fechaValorizacion) {
  const d = devengoInstrumento(instrumento, filasCalendario, fechaLiquidacion);
  const accrued = (nominal * d.accruedPor100) / 100;
  const cobro = cobroPendiente(filasCalendario, nominal, fechaValorizacion, fechaLiquidacion);
  if (precioLimpio == null) {
    return { fechaLiquidacion, ...d, accrued: redondear(accrued, 6), cobroPendiente: redondear(cobro, 6), precioLimpio: null, precioSucio: null, smv: null, tmv: null };
  }
  const smv = (nominal * precioLimpio) / 100;
  return {
    fechaLiquidacion,
    diasTranscurridos: d.diasTranscurridos,
    diasPeriodo: d.diasPeriodo,
    cuponPeriodo: redondear(d.cuponPeriodo, 8),
    accruedPor100: redondear(d.accruedPor100, 8),
    inicioPeriodo: d.inicioPeriodo,
    finPeriodo: d.finPeriodo,
    accrued: redondear(accrued, 6),
    cobroPendiente: redondear(cobro, 6),
    precioLimpio,
    precioSucio: redondear(precioLimpio + d.accruedPor100, 8),
    smv: redondear(smv, 6),
    tmv: redondear(smv + accrued + cobro, 6),
  };
}

/** Importe y signo de caja de una operación, con su accrued de liquidación. */
export function importeOperacion(op, porISIN, calendario) {
  if (op.tipo === 'aporte' || op.tipo === 'rescate') {
    const signo = op.tipo === 'aporte' ? 1 : -1;
    return { moneda: op.moneda, monto: signo * Number(op.monto || 0), origen: op.tipo, detalle: op.tipo === 'aporte' ? 'Aporte de cliente' : 'Rescate de cliente' };
  }
  const inst = porISIN.get(op.isin);
  if (!inst) return { moneda: op.moneda || '', monto: 0, origen: 'desconocido', detalle: `ISIN no encontrado: ${op.isin}` };
  const filas = calendario.get(op.isin) || [];
  const d = devengoInstrumento(inst, filas, op.fechaLiquidacion || op.fechaOperacion);
  const bruto = (Number(op.nominal || 0) * Number(op.precioOperacion || 0)) / 100 + (Number(op.nominal || 0) * d.accruedPor100) / 100;
  const signo = op.tipo === 'compra' ? -1 : 1;
  return {
    moneda: inst.moneda,
    monto: signo * bruto,
    origen: op.tipo === 'compra' ? 'neto_compra' : 'neto_venta',
    detalle: `${op.tipo === 'compra' ? 'Compra' : 'Venta'} ${op.isin} · ${Number(op.nominal).toLocaleString('es-PE')} @ ${op.precioOperacion}`,
  };
}

/** Fracción del principal aún viva a una fecha (para amortizables). */
function factorVigente(filas, fecha) {
  let pagado = 0;
  for (const f of filas) if (comparar(f.fechaPago, fecha) <= 0) pagado += Number(f.amortPct || 0);
  return Math.max(0, 1 - pagado / 100);
}
