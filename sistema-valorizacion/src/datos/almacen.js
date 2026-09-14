// Capa 1 — almacén de datos crudos (inputs). Es la verdad de fuente.
//
// Persiste en localStorage como un único documento JSON versionado. La tabla de
// Operaciones es append-only: no existe API para editar ni borrar un registro;
// las correcciones se hacen con una reversa que se agrega al final (regla 5).

import { CONFIG_POR_DEFECTO } from '../core/motor.js';
import { hoyISO } from '../core/fechas.js';
import { generarCalendario } from '../core/calendario.js';

export const CLAVE_ALMACEN = 'valorizacion.rf.v1';
const ESQUEMA = 1;

export const TIPOS_INSTRUMENTO = {
  bullet: 'Bullet',
  amortizable: 'Amortizable',
  cupon_cero: 'Cupón cero',
};

function vacio() {
  return {
    esquema: ESQUEMA,
    config: { ...CONFIG_POR_DEFECTO },
    instrumentos: [],
    calendario: [],
    operaciones: [],
    precios: [],
    fx: [],
    feriados: [],
    bitacora: [],
  };
}

const almacenamiento = (() => {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('__probe__', '1');
      localStorage.removeItem('__probe__');
      return localStorage;
    }
  } catch { /* modo privado o sin permisos */ }
  const memoria = new Map();
  return {
    getItem: (k) => (memoria.has(k) ? memoria.get(k) : null),
    setItem: (k, v) => memoria.set(k, v),
    removeItem: (k) => memoria.delete(k),
  };
})();

let datos = vacio();
const suscriptores = new Set();

export function estado() {
  return datos;
}

export function suscribir(fn) {
  suscriptores.add(fn);
  return () => suscriptores.delete(fn);
}

function notificar() {
  guardar();
  for (const fn of suscriptores) fn(datos);
}

/**
 * Devuelve además si ya había un documento guardado. La diferencia importa:
 * «nunca se abrió el sistema» habilita sembrar el ejemplo, mientras que «el
 * usuario borró todo» debe respetarse y dejar el almacén vacío.
 */
export function cargar() {
  let existia = false;
  try {
    const crudo = almacenamiento.getItem(CLAVE_ALMACEN);
    if (crudo) {
      existia = true;
      const leido = JSON.parse(crudo);
      datos = { ...vacio(), ...leido, config: { ...CONFIG_POR_DEFECTO, ...(leido.config || {}) } };
    }
  } catch (e) {
    console.warn('No se pudo leer el almacén; se empieza vacío.', e);
    datos = vacio();
  }
  return { datos, existia };
}

export function guardar() {
  try {
    almacenamiento.setItem(CLAVE_ALMACEN, JSON.stringify(datos));
  } catch (e) {
    console.warn('No se pudo guardar en localStorage.', e);
  }
}

export function reemplazar(nuevos) {
  datos = { ...vacio(), ...nuevos, config: { ...CONFIG_POR_DEFECTO, ...(nuevos.config || {}) } };
  notificar();
}

export function limpiar() {
  datos = vacio();
  notificar();
}

const id = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

function bitacora(accion, detalle) {
  datos.bitacora.unshift({ id: id(), ts: new Date().toISOString(), accion, detalle });
  if (datos.bitacora.length > 500) datos.bitacora.length = 500;
}

// ------------------------------------------------------- config y feriados --

export function actualizarConfig(parche) {
  datos.config = { ...datos.config, ...parche };
  bitacora('config', `Configuración actualizada: ${Object.keys(parche).join(', ')}`);
  notificar();
}

export function agregarFeriado({ plaza, fecha, descripcion = '' }) {
  if (datos.feriados.some((f) => f.plaza === plaza && f.fecha === fecha)) return;
  datos.feriados.push({ id: id(), plaza, fecha, descripcion });
  notificar();
}

export function quitarFeriado(idFeriado) {
  datos.feriados = datos.feriados.filter((f) => f.id !== idFeriado);
  notificar();
}

// ----------------------------------------------------------- instrumentos ---

export function validarInstrumento(inst, { editando = false } = {}) {
  const errores = [];
  if (!inst.isin || inst.isin.trim().length < 4) errores.push('El ISIN es obligatorio (mínimo 4 caracteres).');
  if (/^(CASH|PEND)_/.test(inst.isin || '')) errores.push('Los prefijos CASH_ y PEND_ están reservados para posiciones sintéticas del motor.');
  if (!editando && datos.instrumentos.some((i) => i.isin === inst.isin)) errores.push(`El ISIN ${inst.isin} ya existe en el maestro.`);
  if (!inst.emisor) errores.push('El emisor es obligatorio.');
  if (!inst.moneda) errores.push('La moneda base es obligatoria.');
  if (!inst.fechaEmision) errores.push('La fecha de emisión es obligatoria.');
  if (!inst.fechaVencimiento) errores.push('La fecha de vencimiento es obligatoria.');
  if (inst.fechaEmision && inst.fechaVencimiento && inst.fechaVencimiento <= inst.fechaEmision) errores.push('El vencimiento debe ser posterior a la emisión.');
  if (inst.tipo !== 'cupon_cero' && !(Number(inst.cupon) > 0)) errores.push('Un instrumento con cupón debe tener tasa mayor a 0 (use tipo «Cupón cero» si corresponde).');
  if (Number(inst.convLiquidacion) < 0 || Number(inst.convLiquidacion) > 5) errores.push('La convención de liquidación debe estar entre T+0 y T+5.');
  return errores;
}

export function guardarInstrumento(inst, { regenerarCalendario = true } = {}) {
  const existe = datos.instrumentos.findIndex((i) => i.isin === inst.isin);
  const errores = validarInstrumento(inst, { editando: existe >= 0 });
  if (errores.length) return { ok: false, errores };

  const registro = {
    isin: inst.isin.trim(),
    emisor: inst.emisor.trim(),
    moneda: inst.moneda,
    cupon: Number(inst.cupon) || 0,
    frecuencia: inst.frecuencia,
    fechaEmision: inst.fechaEmision,
    fechaVencimiento: inst.fechaVencimiento,
    baseDias: inst.baseDias,
    convLiquidacion: Number(inst.convLiquidacion),
    tipo: inst.tipo,
    plaza: inst.plaza || datos.config.plazaPorDefecto,
    fuente: inst.fuente || '',
    fechaUltimaVerificacion: inst.fechaUltimaVerificacion || hoyISO(),
  };

  if (existe >= 0) datos.instrumentos[existe] = registro;
  else datos.instrumentos.push(registro);

  if (regenerarCalendario) {
    datos.calendario = datos.calendario.filter((c) => c.isin !== registro.isin);
    for (const fila of generarCalendario(registro)) datos.calendario.push({ id: id(), ...fila });
  }
  bitacora('instrumento', `${existe >= 0 ? 'Editado' : 'Alta de'} ${registro.isin}${regenerarCalendario ? ' (calendario regenerado)' : ''}`);
  notificar();
  return { ok: true, errores: [] };
}

export function eliminarInstrumento(isin) {
  const conOperaciones = datos.operaciones.some((o) => o.isin === isin);
  if (conOperaciones) return { ok: false, errores: ['No se puede eliminar: el instrumento tiene operaciones registradas. Cierre la posición con una venta.'] };
  datos.instrumentos = datos.instrumentos.filter((i) => i.isin !== isin);
  datos.calendario = datos.calendario.filter((c) => c.isin !== isin);
  datos.precios = datos.precios.filter((p) => p.isin !== isin);
  bitacora('instrumento', `Eliminado ${isin}`);
  notificar();
  return { ok: true, errores: [] };
}

export function calendarioDe(isin) {
  return datos.calendario.filter((c) => c.isin === isin).sort((a, b) => (a.fechaPago < b.fechaPago ? -1 : 1));
}

export function guardarFilaCalendario(fila) {
  const i = datos.calendario.findIndex((c) => c.id === fila.id);
  const registro = {
    id: fila.id || id(),
    isin: fila.isin,
    fechaPago: fila.fechaPago,
    cuponPct: Number(fila.cuponPct) || 0,
    amortPct: Number(fila.amortPct) || 0,
    esUltimoPago: !!fila.esUltimoPago,
  };
  if (i >= 0) datos.calendario[i] = registro;
  else datos.calendario.push(registro);
  bitacora('calendario', `Cupón ${registro.isin} ${registro.fechaPago} actualizado`);
  notificar();
}

export function quitarFilaCalendario(idFila) {
  datos.calendario = datos.calendario.filter((c) => c.id !== idFila);
  notificar();
}

export function regenerarCalendario(isin) {
  const inst = datos.instrumentos.find((i) => i.isin === isin);
  if (!inst) return;
  datos.calendario = datos.calendario.filter((c) => c.isin !== isin);
  for (const fila of generarCalendario(inst)) datos.calendario.push({ id: id(), ...fila });
  bitacora('calendario', `Calendario regenerado para ${isin}`);
  notificar();
}

// ------------------------------------------------- operaciones (append-only) -

export function validarOperacion(op) {
  const errores = [];
  const esFlujo = op.tipo === 'aporte' || op.tipo === 'rescate';
  if (!op.tipo) errores.push('El tipo de operación es obligatorio.');
  if (op.tipo === 'amortizacion' || op.tipo === 'cupon') errores.push('Los cupones y amortizaciones NO se cargan como operación: se generan automáticamente desde el Calendario_Cupones (regla 2).');
  if (!op.fechaOperacion) errores.push('La fecha de operación es obligatoria.');
  if (esFlujo) {
    if (!(Number(op.monto) > 0)) errores.push('El monto del aporte/rescate debe ser mayor a 0.');
    if (!op.moneda) errores.push('La moneda del aporte/rescate es obligatoria.');
  } else {
    const inst = datos.instrumentos.find((i) => i.isin === op.isin);
    if (!inst) errores.push('Seleccione un instrumento del maestro.');
    if (!(Number(op.nominal) > 0)) errores.push('El nominal debe ser mayor a 0.');
    if (!(Number(op.precioOperacion) > 0)) errores.push('El precio de operación debe ser mayor a 0.');
    if (op.fechaLiquidacion && op.fechaLiquidacion < op.fechaOperacion) errores.push('La fecha de liquidación no puede ser anterior a la de operación.');
    if (inst && op.fechaOperacion > inst.fechaVencimiento) errores.push('La fecha de operación es posterior al vencimiento del instrumento.');
  }
  return errores;
}

export function agregarOperacion(op) {
  const errores = validarOperacion(op);
  if (errores.length) return { ok: false, errores };
  const esFlujo = op.tipo === 'aporte' || op.tipo === 'rescate';
  const registro = {
    id: id(),
    ts: new Date().toISOString(),
    tipo: op.tipo,
    isin: esFlujo ? null : op.isin,
    fechaOperacion: op.fechaOperacion,
    fechaLiquidacion: op.fechaLiquidacion || op.fechaOperacion,
    nominal: esFlujo ? 0 : Number(op.nominal),
    precioOperacion: esFlujo ? 0 : Number(op.precioOperacion),
    monto: esFlujo ? Number(op.monto) : 0,
    moneda: esFlujo ? op.moneda : (datos.instrumentos.find((i) => i.isin === op.isin)?.moneda || ''),
    flujo: esFlujo ? 'externo' : (op.flujo || 'interno'),
    reversaDe: null,
    comentario: op.comentario || '',
  };
  datos.operaciones.push(registro);
  bitacora('operacion', `Alta ${registro.tipo} ${registro.isin || registro.moneda} ${registro.fechaOperacion}`);
  notificar();
  return { ok: true, errores: [], operacion: registro };
}

/** Corrección de una operación: se agrega la contraria, nunca se borra (regla 5). */
export function reversarOperacion(idOperacion, motivo = '') {
  const original = datos.operaciones.find((o) => o.id === idOperacion);
  if (!original) return { ok: false, errores: ['Operación no encontrada.'] };
  if (original.reversaDe) return { ok: false, errores: ['No se puede reversar una reversa. Registre la operación correcta.'] };
  if (datos.operaciones.some((o) => o.reversaDe === idOperacion)) return { ok: false, errores: ['Esta operación ya fue reversada.'] };

  const opuesto = { compra: 'venta', venta: 'compra', aporte: 'rescate', rescate: 'aporte' }[original.tipo];
  const reversa = {
    ...original,
    id: id(),
    ts: new Date().toISOString(),
    tipo: opuesto,
    reversaDe: idOperacion,
    comentario: `REVERSA de ${idOperacion}${motivo ? ` — ${motivo}` : ''}`,
  };
  datos.operaciones.push(reversa);
  bitacora('reversa', `Reversa de ${idOperacion} (${original.tipo} ${original.isin || original.moneda})`);
  notificar();
  return { ok: true, errores: [], operacion: reversa };
}

export function estaReversada(idOperacion) {
  return datos.operaciones.some((o) => o.reversaDe === idOperacion);
}

// -------------------------------------------------------- precios y FX ------

export function guardarPrecio({ isin, fecha, precioLimpio, fuente }) {
  const errores = [];
  if (!datos.instrumentos.some((i) => i.isin === isin)) errores.push('ISIN no existe en el maestro.');
  if (!fecha) errores.push('La fecha de valorización es obligatoria.');
  if (!(Number(precioLimpio) > 0)) errores.push('El precio limpio debe ser mayor a 0.');
  if (errores.length) return { ok: false, errores };

  const anterior = datos.precios.find((p) => p.isin === isin && p.fecha === fecha);
  if (anterior) {
    // No se sobrescribe la historia: se guarda la revisión anterior (consideración 8.4).
    datos.precios = datos.precios.filter((p) => p !== anterior);
    bitacora('precio-revision', `Precio ${isin} ${fecha}: ${anterior.precioLimpio} → ${precioLimpio} (fuente ${fuente || 's/d'})`);
  }
  datos.precios.push({ id: id(), isin, fecha, precioLimpio: Number(precioLimpio), fuente: fuente || '', ts: new Date().toISOString() });
  notificar();
  return { ok: true, errores: [] };
}

export function guardarFX({ par, fecha, tipo, fuente }) {
  const errores = [];
  if (!/^[A-Z]{3}\/[A-Z]{3}$/.test(par || '')) errores.push('El par debe tener el formato XXX/YYY (por ejemplo USD/PEN).');
  if (!fecha) errores.push('La fecha es obligatoria.');
  if (!(Number(tipo) > 0)) errores.push('El tipo de cambio debe ser mayor a 0.');
  if (errores.length) return { ok: false, errores };

  const anterior = datos.fx.find((f) => f.par === par && f.fecha === fecha);
  if (anterior) {
    datos.fx = datos.fx.filter((f) => f !== anterior);
    bitacora('fx-revision', `FX ${par} ${fecha}: ${anterior.tipo} → ${tipo}`);
  }
  datos.fx.push({ id: id(), par, fecha, tipo: Number(tipo), fuente: fuente || '', ts: new Date().toISOString() });
  notificar();
  return { ok: true, errores: [] };
}

export function quitarPrecio(idPrecio) {
  datos.precios = datos.precios.filter((p) => p.id !== idPrecio);
  notificar();
}

export function quitarFX(idFX) {
  datos.fx = datos.fx.filter((f) => f.id !== idFX);
  notificar();
}
