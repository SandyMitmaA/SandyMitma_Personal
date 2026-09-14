// Frame 3. Reproceso. El unico modulo que dispara calculo.
import {
  aviso, el, enlaceModulo, enviarJson, estadoGlobal, formatearFecha, guardarFiltros,
  limpiar, modal, monto, pedir,
} from '../componentes/nucleo.js';
import { estadoVacio, marca, tabla } from '../componentes/tabla.js';

let temporizador = null;

export async function render(raiz, ctx) {
  raiz.appendChild(el('div', { class: 'encabezado-modulo' }, [
    el('h1', { texto: 'Reproceso' }),
    el('span', { class: 'pregunta', texto: 'Que hay que recalcular, y que cambiaria si lo hago.' }),
  ]));

  const propuesta = await pedir('/reproceso/propuesta');
  const desde = el('input', { type: 'date', value: propuesta.desde || estadoGlobal.desde });
  const hasta = el('input', { type: 'date', value: propuesta.hasta || estadoGlobal.hasta });
  const isines = el('input', { size: 24, value: (propuesta.isines || []).join(','),
    placeholder: 'todos los instrumentos' });
  const forzado = el('input', { type: 'checkbox' });

  raiz.appendChild(el('div', { class: 'filtros' }, [
    el('div', { class: 'campo' }, [el('label', { texto: 'Desde' }), desde]),
    el('div', { class: 'campo' }, [el('label', { texto: 'Hasta' }), hasta]),
    el('div', { class: 'campo' }, [el('label', { texto: 'Instrumentos (opcional)' }), isines]),
    el('div', { class: 'campo' }, [el('label', { texto: 'Recalculo forzado' }),
      el('div', {}, [forzado, el('span', { class: 'mono-pequeno',
        texto: ' recalcula aunque no haya cambiado ningun dato' })])]),
    el('button', { texto: 'Analizar impacto', onclick: () => analizar() }),
  ]));

  raiz.appendChild(el('div', { class: 'aviso' }, [el('div', {
    texto: propuesta.fechas_desactualizadas
      ? `Se propone el rango minimo que cubre las ${propuesta.fechas_desactualizadas} `
        + `fechas marcadas como desactualizadas (${propuesta.origen}).`
      : 'No hay fechas desactualizadas. El rango propuesto es el ultimo periodo valorizado. '
        + 'Puedes usar el recalculo forzado como herramienta de diagnostico.' })]));

  const panelImpacto = el('div');
  const panelHistorial = el('div');
  raiz.appendChild(panelImpacto);
  raiz.appendChild(panelHistorial);

  async function analizar() {
    limpiar(panelImpacto);
    const cuerpo = {
      desde: desde.value, hasta: hasta.value,
      isines: isines.value.trim() ? isines.value.split(',').map((s) => s.trim().toUpperCase()) : null,
    };
    const imp = await enviarJson('/reproceso/impacto', 'POST', cuerpo);
    panelImpacto.appendChild(el('div', { class: 'panel' }, [
      el('h2', {}, ['Analisis de impacto, antes de ejecutar']),
      el('div', { class: 'cifras' }, [
        cifra('Dias a recalcular', imp.dias),
        cifra('Valorizaciones afectadas', imp.valorizaciones_afectadas),
        cifra('Fechas desactualizadas', imp.fechas_desactualizadas),
        cifra(`Total MV ${formatearFecha(imp.desde)}`, monto(imp.total_actual_inicio)),
        cifra(`Total MV ${formatearFecha(imp.hasta)}`, monto(imp.total_actual_fin)),
      ]),
      imp.periodos_cerrados.length
        ? aviso('El rango cae en un periodo cerrado. Se exige reapertura explicita con '
              + 'justificacion, queda en bitacora y genera reporte de reexpresion.', 'alert')
        : null,
      el('div', { class: 'panel' }, [
        el('h2', {}, ['Que cambio desde el ultimo calculo']),
        imp.cambios_desde_ultimo_calculo.length
          ? tabla(['momento', 'usuario', 'accion', 'entidad', 'entidad_id'],
              imp.cambios_desde_ultimo_calculo)
          : estadoVacio('Sin cambios registrados.', 'Ningun dato de entrada se modifico.')]),
      imp.detalle_desactualizadas.length
        ? el('div', { class: 'panel' }, [
            el('h2', {}, ['Fechas marcadas como desactualizadas']),
            tabla(['fecha', 'isin', 'motivo', 'marcado_en'], imp.detalle_desactualizadas)])
        : null,
      el('div', { class: 'cuerpo' }, [
        el('button', { texto: 'Ejecutar reproceso',
          onclick: () => ejecutar(cuerpo, imp, ctx, cargarHistorial) }),
      ]),
    ]));
  }

  async function ejecutar(cuerpo, imp, ctx2, recargar) {
    let justificacion = '';
    if (imp.periodos_cerrados.length) {
      const entrada = el('textarea', { rows: 3, style: 'width:100%' });
      const ok = await new Promise((resolver) => {
        modal('Reapertura de periodo cerrado', el('div', {}, [
          aviso('Justifica la reapertura. Queda registrada en bitacora y obliga a emitir '
              + 'reporte de reexpresion.', 'alert'), entrada]),
          [{ texto: 'Reabrir y reprocesar', clase: 'peligro',
             al: () => { resolver(entrada.value.trim()); return true; } }]);
      });
      if (!ok) return;
      justificacion = ok;
    }
    const r = await enviarJson('/reproceso', 'POST', {
      ...cuerpo, forzado: forzado.checked, justificacion_reapertura: justificacion });
    seguir(r.reproceso_id, ctx2, recargar);
  }

  async function seguir(id, ctx2, recargar) {
    const estado = el('div', { class: 'aviso' }, [el('div', { texto: 'Encolado...' })]);
    const { cerrar } = modal(`Reproceso ${id}`, estado, []);
    if (temporizador) clearInterval(temporizador);
    temporizador = setInterval(async () => {
      const r = await pedir(`/reproceso/${id}`);
      limpiar(estado);
      estado.className = 'aviso ' + (r.estado === 'error' ? 'alert'
        : r.estado === 'terminado' ? 'ok' : '');
      estado.appendChild(el('div', { texto: `Estado: ${r.estado}. ${r.mensaje || ''}` }));
      if (r.estado === 'terminado' || r.estado === 'error') {
        clearInterval(temporizador); temporizador = null;
        if (r.estado === 'terminado') {
          estado.appendChild(el('div', { texto:
            `${r.valorizaciones_totales} valorizaciones procesadas, `
            + `${r.valorizaciones_cambiadas} modificadas, en ${r.duracion_ms} ms.` }));
          estado.appendChild(el('div', { class: 'siguiente' }, [
            r.valorizaciones_cambiadas
              ? el('button', { class: 'secundario', texto: 'Ver reporte de reexpresion',
                  onclick: () => verReexpresion(id) })
              : null,
            enlaceModulo('Ver la valorizacion', 'valorizacion',
              { desde: r.fecha_desde, hasta: r.fecha_hasta }),
          ].filter(Boolean)));
        }
        await recargar();
        await ctx2.recargarNav();
      }
    }, 400);
  }

  async function cargarHistorial() {
    limpiar(panelHistorial);
    const datos = await pedir('/reproceso');
    panelHistorial.appendChild(el('div', { class: 'panel' }, [
      el('h2', {}, ['Historial de reprocesos',
        el('span', { class: 'acciones' }, [
          el('span', { class: 'mono-pequeno',
            texto: `cola: ${datos.cola.en_espera} en espera` })])]),
      datos.reprocesos.length
        ? tabla(['id', 'fecha_desde', 'fecha_hasta', 'disparador', 'usuario', 'iniciado_en',
                 'duracion_ms', 'estado', 'version_calculo', 'valorizaciones_totales',
                 'valorizaciones_cambiadas', 'forzado', 'mensaje'],
            datos.reprocesos, { alHacerClic: (f) => verReexpresion(f.id) })
        : estadoVacio('Todavia no se ejecuto ningun reproceso.',
            'Analiza el impacto del rango propuesto y ejecuta el primero.'),
    ]));
  }

  await cargarHistorial();
  await analizar();
}

async function verReexpresion(id) {
  const r = await pedir(`/reproceso/${id}/reexpresion`);
  modal(`Reporte de reexpresion del reproceso ${id}`, el('div', {}, [
    r.filas.length
      ? tabla(['fecha_valorizacion', 'isin', 'valor_anterior', 'valor_nuevo',
               'diferencia_absoluta', 'diferencia_relativa', 'causa', 'usuario', 'momento'],
          r.filas)
      : estadoVacio('Este reproceso no modifico ningun valor ya calculado.',
          'Reejecutar sobre los mismos datos es idempotente: no genera version nueva.'),
  ]), []);
}

function cifra(etiqueta, valor) {
  return el('div', { class: 'cifra' }, [
    el('div', { class: 'etiqueta', texto: etiqueta }),
    el('div', { class: 'valor', texto: String(valor) })]);
}
