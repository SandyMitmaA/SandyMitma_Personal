// Frame 4 — Resultado de Valorización (capa de reportes).

import * as store from '../datos/almacen.js';
import { correrMotor } from '../core/motor.js';
import { FRECUENCIAS } from '../core/conteo-dias.js';
import { comparar, hoyISO, sumarDias } from '../core/fechas.js';
import { aCSV } from '../datos/csv.js';
import { el, fmt, tabla, campo, entrada, boton, panel, nota, etiqueta, descargar, aviso } from './comunes.js';

let fecha = null;
let detalle = null;
let diasSerie = 10;

export function render(contenedor, refrescar) {
  const datos = store.estado();
  if (!datos.instrumentos.length) {
    contenedor.replaceChildren(panel('Resultado de Valorización',
      nota('No hay instrumentos cargados. Empiece por el Maestro de Instrumentos, o cargue el portafolio de demostración desde Configuración.', 'alerta')));
    return;
  }

  if (!fecha) fecha = ultimaFechaUtil(datos);
  const resultado = correrMotor(datos, { desde: sumarDias(fecha, -Math.max(diasSerie, 1)), hasta: fecha });
  const dia = resultado.porFecha[fecha];

  if (!dia) {
    contenedor.replaceChildren(
      selectorFecha(refrescar, datos, resultado),
      panel('Resultado de Valorización',
        nota(resultado.inicio
          ? `La fecha elegida es anterior al inicio del portafolio (${fmt.fecha(resultado.inicio)}). Elija una fecha igual o posterior.`
          : 'No hay operaciones registradas todavía: sin una primera operación o aporte no hay portafolio que valorizar.', 'alerta')));
    return;
  }

  const bonos = dia.posiciones.filter((p) => p.tipoPosicion === 'bono');
  const sinteticas = dia.posiciones.filter((p) => p.tipoPosicion !== 'bono');
  if (detalle && !bonos.some((b) => b.isin === detalle)) detalle = null;

  contenedor.replaceChildren(
    selectorFecha(refrescar, datos, resultado),
    tarjetas(dia.consolidado, datos),
    dia.alertas.length ? panelAlertas(dia.alertas) : panel(null, nota('Sin alertas de control para esta fecha: precios oficiales, cuadre correcto y diferencias A vs. B dentro del umbral.', 'ok')),
    panelPosiciones(bonos, sinteticas, dia, datos, refrescar),
    detalle ? panelDetalle(bonos.find((b) => b.isin === detalle), datos) : null,
    panelConsolidado(dia, datos),
    panelMovimientos(dia),
    panelCuadre(dia),
    panelSerie(resultado, refrescar),
  );
}

// ------------------------------------------------------------------ cabecera -

function selectorFecha(refrescar, datos, resultado) {
  return el('div', { clase: 'encabezado-frame' },
    el('div', {},
      el('h1', {}, 'Resultado de Valorización'),
      el('p', { clase: 'subtitulo' }, 'Capa de reportes. Todo lo que sigue es calculado: no hay ningún campo cargado a mano. La Versión A es la oficial; la B es control interno de diferencias.')),
    el('div', { clase: 'barra' },
      campo('Fecha de valorización', entrada({
        type: 'date', value: fecha,
        min: resultado.inicio || null,
        onchange: (e) => { fecha = e.target.value; refrescar(); },
      })),
      boton('◀ Día anterior', () => { fecha = sumarDias(fecha, -1); refrescar(); }),
      boton('Día siguiente ▶', () => { fecha = sumarDias(fecha, 1); refrescar(); }),
      boton('Hoy', () => { fecha = hoyISO(); refrescar(); })));
}

function tarjetas(c, datos) {
  const moneda = c.monedaReporte;
  const items = [
    ['BMV del portafolio', fmt.monto(c.bmv), `Valor al inicio del día = EMV del día anterior (${moneda})`, ''],
    ['EMV del portafolio', fmt.monto(c.emv), `Valor al cierre del día, Versión A (${moneda})`, 'destacado'],
    ['Variación del día', fmt.monto(c.emv - c.bmv - c.flujoExterno), 'EMV − BMV − flujo externo', c.emv - c.bmv - c.flujoExterno >= 0 ? 'positivo' : 'negativo'],
    ['Flujo externo del día', fmt.monto(c.flujoExterno), `Aportes − rescates convertidos a ${moneda} (F_t de la Fase 2)`, c.flujoExterno ? 'aviso' : ''],
    ['SMV (precio limpio)', fmt.monto(c.smvA), `Nominal × precio ÷ 100, convertido a ${moneda}`, ''],
    ['Accrued devengado', fmt.monto(c.accruedA), `Devengo de todas las posiciones en ${moneda}`, ''],
    ['Cupones por cobrar', fmt.monto(c.cobroPendienteA), `Devengados con pago dentro del plazo de liquidación (${moneda})`, c.cobroPendienteA ? 'aviso' : ''],
    ['TMV Versión B', fmt.monto(c.tmvB), `Solo control interno en ${moneda}: no alimenta retornos`, ''],
    ['Diferencia A − B', fmt.monto(c.diferenciaAB), 'Control de la fecha de liquidación alternativa', Math.abs(c.diferenciaAB) > 0.005 ? 'aviso' : ''],
  ];
  return el('div', { clase: 'tarjetas' }, items.map(([titulo, valor, pie, tono]) =>
    el('div', { clase: `tarjeta ${tono}` },
      el('div', { clase: 'tarjeta-titulo' }, titulo),
      el('div', { clase: 'tarjeta-valor' }, valor),
      el('div', { clase: 'tarjeta-pie' }, pie))),
    c.cargaInicial ? el('p', { clase: 'nota nota-info ancho-total' }, 'Primer día de la serie (carga inicial): el BMV se toma igual al TMV inicial, por eso la variación del día es cero por construcción.') : null);
}

function panelAlertas(alertas) {
  const errores = alertas.filter((a) => a.nivel === 'error');
  const avisos = alertas.filter((a) => a.nivel !== 'error');
  return panel(`Alertas de control (${alertas.length})`,
    errores.length ? el('ul', { clase: 'errores' }, errores.map((a) => el('li', {}, `${a.isin}: ${a.mensaje}`))) : null,
    avisos.length ? el('ul', { clase: 'avisos-lista' }, avisos.map((a) => el('li', {}, `${a.isin}: ${a.mensaje}`))) : null);
}

// --------------------------------------------------------------- posiciones --

function panelPosiciones(bonos, sinteticas, dia, datos, refrescar) {
  const columnas = [
    { titulo: 'ISIN', render: (p) => el('button', { clase: 'enlace', type: 'button', onclick: () => { detalle = detalle === p.isin ? null : p.isin; refrescar(); } }, p.isin) },
    { titulo: 'Nominal vigente', alinear: 'der', render: (p) => fmt.nominal(p.nominal) },
    { titulo: 'Precio limpio', alinear: 'der', render: (p) => el('span', {}, fmt.precio(p.precio.valor), p.precio.estado === 'stale' ? etiqueta('stale', 'aviso') : null, p.precio.estado === 'faltante' ? etiqueta('falta', 'error') : null) },
    { titulo: 'A · F. liq.', render: (p) => fmt.fecha(p.A.fechaLiquidacion) },
    { titulo: 'A · Días', alinear: 'der', render: (p) => (p.A.diasPeriodo ? `${p.A.diasTranscurridos}/${p.A.diasPeriodo}` : '—') },
    { titulo: 'A · Accrued', alinear: 'der', render: (p) => fmt.monto(p.A.accrued) },
    { titulo: 'A · Cupón por cobrar', alinear: 'der', ayuda: 'Cupón ya devengado cuya fecha de pago quedó dentro del plazo de liquidación pero que aún no entró a caja.', render: (p) => (p.A.cobroPendiente ? el('span', { clase: 'positivo' }, fmt.monto(p.A.cobroPendiente)) : '—') },
    { titulo: 'A · P. sucio', alinear: 'der', render: (p) => fmt.precio(p.A.precioSucio) },
    { titulo: 'A · SMV', alinear: 'der', render: (p) => fmt.monto(p.A.smv) },
    { titulo: 'A · TMV', alinear: 'der', render: (p) => el('strong', {}, fmt.monto(p.A.tmv)) },
    { titulo: 'B · F. liq.', render: (p) => fmt.fecha(p.B.fechaLiquidacion) },
    { titulo: 'B · Accrued', alinear: 'der', render: (p) => fmt.monto(p.B.accrued) },
    { titulo: 'B · Cupón por cobrar', alinear: 'der', render: (p) => (p.B.cobroPendiente ? fmt.monto(p.B.cobroPendiente) : '—') },
    { titulo: 'B · TMV', alinear: 'der', render: (p) => fmt.monto(p.B.tmv) },
    { titulo: 'Dif. A − B', alinear: 'der', render: (p) => el('span', { clase: p.excedeUmbral ? 'valor-alerta' : '' }, fmt.monto(p.diferenciaTMV), p.excedeUmbral ? etiqueta('> umbral', 'error') : null) },
    { titulo: 'BMV (A)', alinear: 'der', render: (p) => fmt.monto(p.bmv) },
    { titulo: 'EMV (A)', alinear: 'der', render: (p) => el('strong', {}, fmt.monto(p.emv)) },
    { clave: 'moneda', titulo: 'Mon.' },
  ];

  const suma = (lista, f) => lista.reduce((s, p) => s + (Number(f(p)) || 0), 0);
  const pie = el('tr', { clase: 'total' },
    el('td', {}, 'Total instrumentos'),
    el('td', { clase: 'der' }, ''), el('td', { clase: 'der' }, ''), el('td', {}, ''), el('td', {}, ''),
    el('td', { clase: 'der' }, fmt.monto(suma(bonos, (p) => p.A.accrued))),
    el('td', { clase: 'der' }, fmt.monto(suma(bonos, (p) => p.A.cobroPendiente))),
    el('td', {}, ''),
    el('td', { clase: 'der' }, fmt.monto(suma(bonos, (p) => p.A.smv))),
    el('td', { clase: 'der' }, el('strong', {}, fmt.monto(suma(bonos, (p) => p.A.tmv)))),
    el('td', {}, ''),
    el('td', { clase: 'der' }, fmt.monto(suma(bonos, (p) => p.B.accrued))),
    el('td', { clase: 'der' }, fmt.monto(suma(bonos, (p) => p.B.cobroPendiente))),
    el('td', { clase: 'der' }, fmt.monto(suma(bonos, (p) => p.B.tmv))),
    el('td', { clase: 'der' }, fmt.monto(suma(bonos, (p) => p.diferenciaTMV))),
    el('td', { clase: 'der' }, fmt.monto(suma(bonos, (p) => p.bmv))),
    el('td', { clase: 'der' }, el('strong', {}, fmt.monto(suma(bonos, (p) => p.emv)))),
    el('td', {}, ''));

  return panel('Valorización por instrumento — Versión A vs. Versión B',
    nota(`Importes por instrumento en su moneda base; el consolidado del portafolio va convertido a ${datos.config.monedaReporte}. Umbral de alerta: ${datos.config.umbralBp} bp del nominal. Haga clic en un ISIN para ver la tabla comparativa campo por campo.`, 'info'),
    tabla(columnas, bonos, { clase: 'compacta', vacio: 'Sin posiciones vivas en esta fecha.', pie: bonos.length ? pie : null }),
    el('h3', { clase: 'sub' }, 'Posiciones sintéticas del motor'),
    nota('La caja es una posición más del portafolio, con su propio ISIN sintético, para que el TMV total sea la simple suma de todas las posiciones. PEND_<moneda> sostiene el importe de las operaciones entre su fecha de operación y su fecha de liquidación, de modo que el total no salte en el medio.', 'info'),
    tabla([
      { titulo: 'Posición', render: (p) => el('code', {}, p.isin) },
      { clave: 'nombre', titulo: 'Descripción' },
      { titulo: 'Saldo', alinear: 'der', render: (p) => fmt.monto(p.nominal) },
      { titulo: 'BMV (A)', alinear: 'der', render: (p) => fmt.monto(p.bmv) },
      { titulo: 'EMV (A)', alinear: 'der', render: (p) => el('strong', {}, fmt.monto(p.emv)) },
      { clave: 'moneda', titulo: 'Moneda' },
    ], sinteticas, { vacio: 'Sin caja ni liquidaciones pendientes.' }),
    el('div', { clase: 'acciones' }, boton('Exportar esta valorización a CSV', () => exportar(dia, datos))));
}

// -------------------------------------------------- detalle campo por campo --

function panelDetalle(p, datos) {
  if (!p) return null;
  const inst = datos.instrumentos.find((i) => i.isin === p.isin);
  const fx = p.fx;
  const filas = [
    ['Nominal vigente', 'Nominal(t−1) ± operaciones del día ± amortizaciones del calendario', fmt.nominal(p.nominal), fmt.nominal(p.nominal)],
    ['Precio limpio', `Input del día (fuente: ${p.precio.fuente || 's/d'}${p.precio.estado === 'stale' ? `, arrastrado del ${fmt.fecha(p.precio.fechaPrecio)}` : ''})`, fmt.precio(p.A.precioLimpio), fmt.precio(p.B.precioLimpio)],
    ['Fecha de liquidación usada', `A: convención del mercado T+${inst?.convLiquidacion}. B: fecha de valorización + 1 día ${datos.config.versionBHabil ? 'hábil' : 'calendario'}`, fmt.fecha(p.A.fechaLiquidacion), fmt.fecha(p.B.fechaLiquidacion)],
    ['Inicio del período', 'Último cupón anterior o igual a la fecha de liquidación (o la emisión)', fmt.fecha(p.A.inicioPeriodo), fmt.fecha(p.B.inicioPeriodo)],
    ['Fin del período', 'Cupón siguiente a la fecha de liquidación', fmt.fecha(p.A.finPeriodo), fmt.fecha(p.B.finPeriodo)],
    ['Días transcurridos', `Desde el inicio del período hasta la liquidación, base ${inst?.baseDias}`, fmt.entero(p.A.diasTranscurridos), fmt.entero(p.B.diasTranscurridos)],
    ['Días del período', `Del período completo de cupón, base ${inst?.baseDias}`, fmt.entero(p.A.diasPeriodo), fmt.entero(p.B.diasPeriodo)],
    ['Cupón del período (por 100)', `Cupón anual ${fmt.tasa(inst?.cupon)} ÷ ${FRECUENCIAS[inst?.frecuencia]?.porAnio || 0} pagos al año`, fmt.precio(p.A.cuponPeriodo), fmt.precio(p.B.cuponPeriodo)],
    ['Accrued por 100', 'Cupón del período × días transcurridos ÷ días del período', fmt.precio(p.A.accruedPor100), fmt.precio(p.B.accruedPor100)],
    ['Accrued', 'Nominal vigente × accrued por 100 ÷ 100', fmt.monto(p.A.accrued), fmt.monto(p.B.accrued)],
    ['Cupón devengado por cobrar', 'Cupón cuya fecha de pago cayó dentro del plazo de liquidación y todavía no entró a caja (0 en un día normal)', fmt.monto(p.A.cobroPendiente), fmt.monto(p.B.cobroPendiente)],
    ['Precio sucio', 'Precio limpio + accrued por 100', fmt.precio(p.A.precioSucio), fmt.precio(p.B.precioSucio)],
    ['SMV', 'Nominal vigente × precio limpio ÷ 100', fmt.monto(p.A.smv), fmt.monto(p.B.smv)],
    ['TMV', 'SMV + accrued + cupón por cobrar', fmt.monto(p.A.tmv), fmt.monto(p.B.tmv)],
    ['BMV de la posición', 'EMV de la posición el día anterior (solo Versión A alimenta la serie)', fmt.monto(p.bmv), '— (no aplica)'],
    ['EMV de la posición', 'TMV del cierre del día con el nominal vigente de hoy (solo Versión A)', fmt.monto(p.emv), `${fmt.monto(p.B.tmv)} (solo referencia)`],
  ];
  if (inst && inst.moneda !== datos.config.monedaReporte) {
    filas.push(['Tipo de cambio aplicado', `${inst.moneda} → ${datos.config.monedaReporte}, mismo criterio en ambas versiones (${fx.estado})`, fmt.cambio(fx.tasa), fmt.cambio(fx.tasa)]);
    filas.push([`TMV en ${datos.config.monedaReporte}`, 'TMV en moneda base × tipo de cambio', fmt.monto(p.tmvReporte), fmt.monto(p.B.tmv != null && fx.tasa != null ? p.B.tmv * fx.tasa : null)]);
  }

  return panel(`Detalle comparativo — ${p.isin} · ${p.nombre}`,
    tabla([
      { titulo: 'Campo', render: (f) => el('strong', {}, f[0]) },
      { titulo: 'Fórmula / criterio aplicado', render: (f) => el('span', { clase: 'tenue' }, f[1]) },
      { titulo: 'Versión A (estándar de mercado)', alinear: 'der', render: (f) => f[2] },
      { titulo: 'Versión B (sistema interno +1 día)', alinear: 'der', render: (f) => f[3] },
    ], filas, { clase: 'detalle' }),
    el('div', { clase: 'resumen-supuestos' },
      el('h3', {}, 'Nota comparativa y supuestos'),
      el('ul', {},
        el('li', {}, `Diferencia de valorización A − B: ${fmt.monto(p.diferenciaTMV)} ${p.moneda}, equivalente a ${p.nominal ? ((Math.abs(p.diferenciaTMV || 0) / Math.abs(p.nominal)) * 10000).toFixed(4) : '0'} bp del nominal. Umbral configurado: ${datos.config.umbralBp} bp (${fmt.monto(p.umbral)}).`),
        el('li', {}, `La diferencia nace exclusivamente de la fecha de liquidación usada para el devengo: ${fmt.entero(Math.abs(p.B.diasTranscurridos - p.A.diasTranscurridos))} día(s) de cupón. Precio, nominal, cupón y tipo de cambio son idénticos en ambas versiones.`),
        el('li', {}, `Fuente del instrumento: ${inst?.fuente || 'no registrada'}. Última verificación de características: ${fmt.fecha(inst?.fechaUltimaVerificacion)}.`),
        el('li', {}, `Convención de días: ${inst?.baseDias}. Tipo: ${inst?.tipo}. Plaza de liquidación: ${inst?.plaza} (sus feriados definen tanto el T+${inst?.convLiquidacion} de la Versión A como el «+1 día» de la Versión B).`),
        el('li', {}, `Cuando la fecha de liquidación cruza una fecha de cupón, el devengo se reinicia en el período nuevo (convención de mercado) pero el efectivo todavía no entró a caja: ese cupón se sostiene como «cupón devengado por cobrar» hasta su fecha de pago, para que el valor del portafolio no muestre una caída ficticia seguida de un rebote.`),
        el('li', {}, `La serie BMV/EMV que se arrastra día a día y que alimentará el TWRR de la Fase 2 es únicamente la de Versión A. El EMV de la Versión B se muestra solo como referencia de control.`))));
}

// --------------------------------------------------------------- consolidado -

function panelConsolidado(dia, datos) {
  const c = dia.consolidado;
  const porMoneda = new Map();
  for (const p of dia.posiciones) {
    if (!porMoneda.has(p.moneda)) porMoneda.set(p.moneda, { moneda: p.moneda, tmv: 0, tmvReporte: 0, n: 0 });
    const g = porMoneda.get(p.moneda);
    g.tmv += Number(p.A.tmv) || 0;
    g.tmvReporte += Number(p.tmvReporte) || 0;
    g.n++;
  }
  return panel(`Consolidado del portafolio en ${c.monedaReporte}`,
    nota('Vista consolidada lista para alimentar el frame de Retornos TWRR de la Fase 2: V(t−1) = BMV total y V(t) = EMV total, caja incluida, sin recalcular nada retroactivamente.', 'info'),
    tabla([
      { clave: 'moneda', titulo: 'Moneda' },
      { titulo: 'Posiciones', alinear: 'der', render: (g) => String(g.n) },
      { titulo: 'TMV en moneda base', alinear: 'der', render: (g) => fmt.monto(g.tmv) },
      { titulo: `TMV en ${c.monedaReporte}`, alinear: 'der', render: (g) => fmt.monto(g.tmvReporte) },
    ], [...porMoneda.values()], {
      pie: el('tr', { clase: 'total' },
        el('td', {}, 'Portafolio'),
        el('td', { clase: 'der' }, String(c.nPosiciones)),
        el('td', { clase: 'der' }, '—'),
        el('td', { clase: 'der' }, el('strong', {}, fmt.monto(c.tmvReporte)))),
    }),
    el('div', { clase: 'rejilla-datos' },
      dato('BMV total = V(t−1)', fmt.monto(c.bmv)),
      dato('EMV total = V(t)', fmt.monto(c.emv)),
      dato('Flujo externo F(t)', fmt.monto(c.flujoExterno)),
      dato('TMV Versión A', fmt.monto(c.tmvA)),
      dato('Cupones por cobrar', fmt.monto(c.cobroPendienteA)),
      dato('TMV Versión B (control)', fmt.monto(c.tmvB)),
      dato('Día hábil en la plaza', c.esHabil ? 'sí' : 'no')));
}

function dato(titulo, valor) {
  return el('div', { clase: 'dato' }, el('span', { clase: 'dato-titulo' }, titulo), el('span', { clase: 'dato-valor' }, valor));
}

function panelMovimientos(dia) {
  return panel(`Movimientos de caja del día (${dia.movimientos.length})`,
    nota('Generados automáticamente por el motor: los cupones y amortizaciones salen del Calendario_Cupones y las liquidaciones de la tabla de Operaciones. Ninguno se carga a mano.', 'info'),
    tabla([
      { titulo: 'Origen', render: (m) => etiqueta(m.origen.replace('_', ' '), m.origen === 'cupon' || m.origen === 'amortizacion' ? 'ok' : 'neutro') },
      { clave: 'detalle', titulo: 'Detalle' },
      { clave: 'moneda', titulo: 'Moneda' },
      { titulo: 'Monto', alinear: 'der', render: (m) => el('span', { clase: m.monto < 0 ? 'negativo' : 'positivo' }, fmt.monto(m.monto)) },
      { titulo: 'Flujo', render: (m) => etiqueta(m.flujo, m.flujo === 'externo' ? 'aviso' : 'neutro') },
    ], dia.movimientos, { vacio: 'Sin movimientos de caja en esta fecha.' }));
}

function panelCuadre(dia) {
  const descuadres = dia.cuadres.filter((c) => !c.cuadra).length;
  return panel('Control de cuadre diario de posiciones',
    descuadres
      ? nota(`${descuadres} instrumento(s) no cuadran. Revise las operaciones y el calendario.`, 'alerta')
      : nota('Todas las posiciones cuadran: Posición(t) = Posición(t−1) + operaciones(t) − amortizaciones(t).', 'ok'),
    tabla([
      { titulo: 'ISIN', render: (c) => el('code', {}, c.isin) },
      { titulo: 'Posición(t−1)', alinear: 'der', render: (c) => fmt.nominal(c.nominalAnterior) },
      { titulo: '+ Operaciones(t)', alinear: 'der', render: (c) => fmt.nominal(c.netoOps) },
      { titulo: '− Amortizaciones(t)', alinear: 'der', render: (c) => fmt.nominal(c.amortizacion) },
      { titulo: '= Esperado', alinear: 'der', render: (c) => fmt.nominal(c.esperado) },
      { titulo: 'Posición(t) del motor', alinear: 'der', render: (c) => fmt.nominal(c.nominalFinal) },
      { titulo: 'Cuadre', render: (c) => (c.cuadra ? etiqueta('cuadra', 'ok') : etiqueta('DESCUADRE', 'error')) },
    ], dia.cuadres, { vacio: 'Sin posiciones que cuadrar.' }));
}

function panelSerie(resultado, refrescar) {
  const filas = resultado.fechas.map((f) => resultado.porFecha[f].consolidado);
  return panel('Serie consolidada BMV / EMV — insumo listo para la Fase 2',
    nota('Estos son exactamente los V(t−1) y V(t) que consumirá la fórmula de retorno diario r(t) = (V(t) − F(t)) / V(t−1) − 1. El TWRR no se calcula todavía (está fuera del alcance de la Fase 1), pero la serie ya queda guardada día a día y no habrá que reconstruirla.', 'info'),
    el('div', { clase: 'barra' },
      campo('Días de historia a mostrar', entrada({ type: 'number', min: 1, max: 400, value: diasSerie, onchange: (e) => { diasSerie = Math.max(1, Number(e.target.value) || 10); refrescar(); } }))),
    tabla([
      { titulo: 'Fecha', render: (c) => fmt.fecha(c.fecha) },
      { titulo: 'Hábil', render: (c) => (c.esHabil ? 'sí' : el('span', { clase: 'tenue' }, 'no')) },
      { titulo: 'V(t−1) = BMV', alinear: 'der', render: (c) => fmt.monto(c.bmv) },
      { titulo: 'V(t) = EMV', alinear: 'der', render: (c) => fmt.monto(c.emv) },
      { titulo: 'Flujo externo F(t)', alinear: 'der', render: (c) => fmt.monto(c.flujoExterno) },
      { titulo: 'Variación sin flujo', alinear: 'der', render: (c) => el('span', { clase: c.emv - c.bmv - c.flujoExterno >= 0 ? 'positivo' : 'negativo' }, fmt.monto(c.emv - c.bmv - c.flujoExterno)) },
      { titulo: 'Accrued total', alinear: 'der', render: (c) => fmt.monto(c.accruedA) },
      { titulo: 'Dif. A − B', alinear: 'der', render: (c) => fmt.monto(c.diferenciaAB) },
    ], filas.slice().reverse(), { clase: 'compacta' }),
    el('div', { clase: 'acciones' }, boton('Exportar serie BMV/EMV a CSV', () => {
      descargar(`serie_bmv_emv_${fecha}.csv`, aCSV(
        ['fecha', 'es_habil', 'bmv_v_t_menos_1', 'emv_v_t', 'flujo_externo', 'tmv_version_a', 'tmv_version_b', 'diferencia_a_b', 'moneda_reporte'],
        filas.map((c) => [c.fecha, c.esHabil ? 'si' : 'no', c.bmv, c.emv, c.flujoExterno, c.tmvA, c.tmvB, c.diferenciaAB, c.monedaReporte])));
      aviso('Serie exportada.');
    })));
}

function exportar(dia, datos) {
  const encabezados = ['fecha', 'isin', 'descripcion', 'tipo_posicion', 'moneda', 'nominal_vigente', 'precio_limpio', 'estado_precio',
    'A_fecha_liquidacion', 'A_dias_transcurridos', 'A_dias_periodo', 'A_cupon_periodo', 'A_accrued', 'A_cupon_por_cobrar', 'A_precio_sucio', 'A_smv', 'A_tmv',
    'B_fecha_liquidacion', 'B_dias_transcurridos', 'B_accrued', 'B_cupon_por_cobrar', 'B_precio_sucio', 'B_smv', 'B_tmv',
    'diferencia_A_menos_B', 'umbral', 'excede_umbral', 'bmv_version_a', 'emv_version_a', 'tipo_cambio', `tmv_${datos.config.monedaReporte}`];
  const filas = dia.posiciones.map((p) => [dia.fecha, p.isin, p.nombre, p.tipoPosicion, p.moneda, p.nominal, p.precio.valor, p.precio.estado,
    p.A.fechaLiquidacion, p.A.diasTranscurridos, p.A.diasPeriodo, p.A.cuponPeriodo, p.A.accrued, p.A.cobroPendiente, p.A.precioSucio, p.A.smv, p.A.tmv,
    p.B.fechaLiquidacion, p.B.diasTranscurridos, p.B.accrued, p.B.cobroPendiente, p.B.precioSucio, p.B.smv, p.B.tmv,
    p.diferenciaTMV, p.umbral, p.excedeUmbral ? 'si' : 'no', p.bmv, p.emv, p.fx.tasa, p.tmvReporte]);
  descargar(`valorizacion_${dia.fecha}.csv`, aCSV(encabezados, filas));
  aviso('Valorización exportada.');
}

function ultimaFechaUtil(datos) {
  const fechas = [...datos.precios.map((p) => p.fecha), ...datos.operaciones.map((o) => o.fechaOperacion)].filter(Boolean).sort(comparar);
  return fechas.pop() || hoyISO();
}
