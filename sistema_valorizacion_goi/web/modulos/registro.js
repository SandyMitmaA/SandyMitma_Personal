// Frame 1. Registro de instrumentos y posiciones. No pide precios ni calcula.
import {
  aviso, el, enlaceModulo, enviarJson, estadoGlobal, formatearFecha, limpiar,
  modal, monto, pedir, confirmarConMotivo,
} from '../componentes/nucleo.js';
import { estadoVacio, marca, reemplazar, tabla } from '../componentes/tabla.js';

const CAMPOS_MAESTRA = [
  ['isin', 'ISIN', 'text', ''],
  ['descripcion', 'Descripcion', 'text', ''],
  ['moneda', 'Moneda', 'text', 'USD'],
  ['tasa_cupon', 'Tasa de cupon (%)', 'text', ''],
  ['frecuencia', 'Frecuencia', 'select', '2'],
  ['fecha_emision', 'Fecha de emision', 'date', ''],
  ['fecha_vencimiento', 'Fecha de vencimiento', 'date', ''],
  ['convencion', 'Convencion de dias', 'select', 'ACT/ACT'],
  ['precio_expresado_en', 'El precio llega en', 'select', 'LOCAL'],
  ['valor_redencion', 'Valor de redencion', 'text', '100'],
];

export async function render(raiz, ctx) {
  const contenedor = el('div');
  raiz.appendChild(el('div', { class: 'encabezado-modulo' }, [
    el('h1', { texto: 'Registro de instrumentos' }),
    el('span', { class: 'pregunta', texto: 'Que hay en cartera y desde cuando.' }),
  ]));
  raiz.appendChild(contenedor);
  await dibujar(contenedor, ctx);
}

async function dibujar(contenedor, ctx) {
  limpiar(contenedor);
  const datos = await pedir('/instrumentos?incluir_eliminados=1');
  const estados = Object.fromEntries(datos.estados.map((e) => [e.isin + ':' + e.posicion_id, e]));

  contenedor.appendChild(el('div', { class: 'panel' }, [
    el('h2', {}, ['Maestra de instrumentos', el('span', { class: 'acciones' }, [
      el('button', { texto: 'Nuevo instrumento', onclick: () => formularioMaestra(null, contenedor, ctx) }),
    ])]),
    datos.instrumentos.length
      ? tabla(['isin', 'descripcion', 'moneda', 'tasa_cupon', 'frecuencia', 'fecha_emision',
               'fecha_vencimiento', 'convencion', 'precio_expresado_en', 'valor_redencion',
               'estado_registro'],
        datos.instrumentos.map((i) => ({ ...i, estado_registro: i.eliminado_en ? 'eliminado' : 'activo' })),
        {
          claseFila: (f) => (f.eliminado_en ? 'muted' : ''),
          alHacerClic: (f) => detalleInstrumento(f, datos, contenedor, ctx),
        })
      : estadoVacio('No hay instrumentos registrados.',
          'Registra la maestra de un bono para poder cargar sus precios y valorizarlo.',
          el('button', { texto: 'Registrar el primero',
            onclick: () => formularioMaestra(null, contenedor, ctx) })),
  ]));

  contenedor.appendChild(el('div', { class: 'panel' }, [
    el('h2', {}, ['Posiciones', el('span', { class: 'acciones' }, [
      el('button', { texto: 'Nueva posicion',
        onclick: () => formularioPosicion(null, datos, contenedor, ctx) }),
    ])]),
    datos.posiciones.length
      ? tabla(['isin', 'nominal', 'fecha_alta', 'estado', 'cobertura', 'acciones'],
        datos.posiciones.map((p) => {
          const e = estados[p.isin + ':' + p.id] || {};
          return {
            ...p, estado: p.eliminado_en ? 'eliminada' : (e.estado || '-'),
            cobertura: e.dias_requeridos ? `${e.dias_cubiertos}/${e.dias_requeridos}` : '-',
            acciones: p.eliminado_en ? 'reactivar' : 'editar / eliminar',
          };
        }),
        {
          claseFila: (f) => (f.eliminado_en ? 'muted' : ''),
          alHacerClic: (f) => (f.eliminado_en
            ? reactivar(f, contenedor, ctx)
            : formularioPosicion(f, datos, contenedor, ctx)),
        })
      : estadoVacio('No hay posiciones registradas.',
          'Una posicion asocia un nominal y una fecha de alta en cartera a un instrumento.',
          datos.instrumentos.length
            ? el('button', { texto: 'Registrar posicion',
                onclick: () => formularioPosicion(null, datos, contenedor, ctx) })
            : null),
  ]));
}

// --- Maestra --------------------------------------------------------------
function formularioMaestra(instrumento, contenedor, ctx) {
  const entradas = {};
  const errores = {};
  const cuerpo = el('div', { class: 'rejilla' });

  for (const [clave, etiqueta, tipo, defecto] of CAMPOS_MAESTRA) {
    let entrada;
    if (tipo === 'select') {
      const opciones = clave === 'frecuencia' ? ['1', '2', '4', '12']
        : clave === 'convencion' ? ['ACT/ACT', 'ACT/365', 'ACT/360', '30/360']
        : ['LOCAL', 'BASE'];
      entrada = el('select', {}, opciones.map((o) => el('option', { value: o, texto: o })));
    } else {
      entrada = el('input', { type: tipo });
    }
    entrada.value = instrumento ? (instrumento[clave] ?? '') : defecto;
    if (instrumento && clave === 'isin') entrada.readOnly = true;
    entradas[clave] = entrada;
    const err = el('div', { class: 'error-campo' });
    errores[clave] = err;
    entrada.addEventListener('input', () => { err.textContent = ''; entrada.classList.remove('invalido'); });
    cuerpo.appendChild(el('div', { class: 'campo' }, [
      el('label', { texto: etiqueta }), entrada, err]));
  }

  const vistaCalendario = el('div', { style: 'margin-top:12px' });
  const leer = () => Object.fromEntries(
    Object.entries(entradas).map(([k, v]) => [k, v.value.trim()]));

  const previsualizar = async () => {
    limpiar(vistaCalendario);
    try {
      const r = await enviarJson('/instrumentos/calendario', 'POST', leer());
      vistaCalendario.appendChild(el('div', { class: 'aviso ok' }, [
        el('div', { texto: `Calendario de cupones derivado (${r.calendario.length} fechas, `
          + `cupon por periodo ${r.cupon_por_periodo}). Confirma que son las que esperas.` }),
        el('div', { class: 'tabular', style: 'margin-top:6px',
          texto: r.calendario.map(formatearFecha).join('  ') }),
      ]));
    } catch (e) {
      marcarError(e, entradas, errores, vistaCalendario);
    }
  };

  for (const c of ['fecha_emision', 'fecha_vencimiento', 'frecuencia']) {
    entradas[c].addEventListener('change', previsualizar);
  }

  const contenido = el('div', {}, [
    el('div', { class: 'aviso' }, [el('div', {
      texto: 'Al guardar veras de inmediato el calendario de cupones derivado. '
           + 'Es el control de calidad mas barato del sistema: un vencimiento mal '
           + 'capturado se detecta aqui.' })]),
    cuerpo, vistaCalendario,
  ]);

  modal(instrumento ? `Editar ${instrumento.isin}` : 'Nuevo instrumento', contenido, [
    { texto: 'Ver calendario', al: async () => { await previsualizar(); return false; } },
    {
      texto: 'Guardar', clase: '',
      al: async () => {
        try {
          const r = await enviarJson('/instrumentos', 'POST', leer());
          await dibujar(contenedor, ctx);
          await ctx.recargarNav();
          resultadoInstrumento(r);
          return true;
        } catch (e) {
          marcarError(e, entradas, errores, vistaCalendario);
          return false;
        }
      },
    },
  ]);
  if (instrumento) previsualizar();
}

function resultadoInstrumento(r) {
  modal(`Instrumento ${r.isin} guardado`, el('div', {}, [
    el('div', { class: 'aviso ok' }, [el('div', {
      texto: `Calendario de cupones derivado: ${r.calendario.length} fechas.` }),
      el('div', { class: 'tabular', style: 'margin-top:6px',
        texto: r.calendario.map(formatearFecha).join('  ') })]),
    r.desviacion_convencion
      ? el('div', { class: 'aviso warn' }, [el('div', {
          texto: `La maestra declara ${r.desviacion_convencion.declarada} y el uso de `
            + `mercado para esta moneda es ${r.desviacion_convencion.uso_de_mercado}. `
            + 'Se reporta en el panel de validaciones con su impacto. El motor no la altera.' })])
      : null,
    r.fechas_desactualizadas
      ? el('div', { class: 'aviso warn' }, [
          el('div', { texto: `${r.fechas_desactualizadas} valorizaciones quedaron `
            + 'desactualizadas. La edicion no recalcula: el recalculo se decide en Reproceso.' }),
          el('div', { class: 'siguiente' }, [enlaceModulo('Ir a Reproceso', 'reproceso')])])
      : null,
    el('div', { class: 'aviso' }, [
      el('div', { texto: 'Siguiente paso: registra la posicion con su nominal y fecha de alta.' })]),
  ]), []);
}

// --- Posicion -------------------------------------------------------------
function formularioPosicion(posicion, datos, contenedor, ctx) {
  const activos = datos.instrumentos.filter((i) => !i.eliminado_en);
  const selIsin = el('select', {}, activos.map((i) =>
    el('option', { value: i.isin, texto: `${i.isin}  ${i.descripcion || ''}` })));
  const nominal = el('input', { type: 'text', placeholder: '20000000' });
  const fechaAlta = el('input', { type: 'date' });
  const err = el('div', { class: 'error-campo' });
  if (posicion) {
    selIsin.value = posicion.isin;
    selIsin.disabled = true;
    nominal.value = posicion.nominal;
    fechaAlta.value = posicion.fecha_alta;
  } else {
    fechaAlta.value = estadoGlobal.fechaInicio;
    if (estadoGlobal.isin) selIsin.value = estadoGlobal.isin;
  }

  const nota = el('div', { class: 'aviso' }, [el('div', {
    texto: 'La fecha de alta puede ser cualquiera, incluso muy anterior a hoy o anterior '
         + 'al inicio del portafolio. Si es anterior o igual al inicio, la posicion forma '
         + 'parte del saldo inicial y no genera alta en el puente.' })]);

  const contenido = el('div', {}, [nota, el('div', { class: 'rejilla' }, [
    el('div', { class: 'campo' }, [el('label', { texto: 'Instrumento' }), selIsin]),
    el('div', { class: 'campo' }, [el('label', { texto: 'Nominal' }), nominal]),
    el('div', { class: 'campo' }, [el('label', { texto: 'Fecha de alta en cartera' }), fechaAlta]),
  ]), err]);

  const acciones = [{
    texto: 'Guardar',
    al: async () => {
      try {
        const cuerpo = { isin: selIsin.value, nominal: nominal.value.trim(),
          fecha_alta: fechaAlta.value };
        if (posicion) cuerpo.id = posicion.id;
        const r = await enviarJson('/posiciones', 'POST', cuerpo);
        await dibujar(contenedor, ctx);
        await ctx.recargarNav();
        resultadoPosicion(r);
        return true;
      } catch (e) { err.textContent = e.message; return false; }
    },
  }];
  if (posicion) {
    acciones.unshift({
      texto: 'Eliminar', clase: 'peligro',
      al: async () => { await eliminarPosicion(posicion, contenedor, ctx); return true; },
    });
  }
  modal(posicion ? `Posicion ${posicion.id} de ${posicion.isin}` : 'Nueva posicion',
    contenido, acciones);
}

function resultadoPosicion(r) {
  modal('Posicion registrada', el('div', {}, [
    el('div', { class: r.parte_del_saldo_inicial ? 'aviso' : 'aviso warn' }, [el('div', {
      texto: r.parte_del_saldo_inicial
        ? 'La fecha de alta es anterior o igual al inicio del portafolio: la posicion forma '
          + 'parte del saldo inicial y cambia el Begin MV de esa fecha. No genera alta en el puente.'
        : 'La fecha de alta es posterior al inicio del portafolio: generara alta de posicion '
          + 'en el puente por su Total MV completo.' })]),
    r.fechas_faltantes_total
      ? el('div', { class: 'aviso alert' }, [
          el('div', { texto: `Faltan ${r.fechas_faltantes_total} precios entre `
            + `${formatearFecha(r.rango_precios_desde)} y ${formatearFecha(r.rango_precios_hasta)}.` }),
          el('div', { class: 'siguiente' }, [
            enlaceModulo('Cargar precios', 'precios',
              { isin: r.isin, desde: r.rango_precios_desde, hasta: r.rango_precios_hasta })])])
      : el('div', { class: 'aviso ok' }, [el('div', {
          texto: 'La cobertura de precios esta completa para el rango obligatorio.' })]),
    r.fechas_desactualizadas
      ? el('div', { class: 'aviso warn' }, [
          el('div', { texto: `${r.fechas_desactualizadas} fechas quedaron desactualizadas.` }),
          el('div', { class: 'siguiente' }, [enlaceModulo('Ir a Reproceso', 'reproceso')])])
      : null,
  ]), []);
}

async function eliminarPosicion(posicion, contenedor, ctx) {
  const impacto = await pedir(`/posiciones/${posicion.id}/impacto-eliminacion`);
  const descripcion = el('div', {}, [
    el('div', { class: 'aviso warn' }, [el('div', {
      texto: 'Este modulo corrige errores de registro. No sirve para registrar una venta '
           + 'ni un vencimiento. La eliminacion es logica: queda el rastro.' })]),
    tabla(['concepto', 'valor'], [
      { concepto: 'Rango con valorizacion', valor: impacto.rango_valorizado_desde
        ? `${formatearFecha(impacto.rango_valorizado_desde)} a ${formatearFecha(impacto.rango_valorizado_hasta)}`
        : 'sin valorizacion' },
      { concepto: 'Valorizaciones que quedan desactualizadas', valor: impacto.valorizaciones_afectadas },
      { concepto: 'Parte del saldo inicial', valor: impacto.parte_del_saldo_inicial ? 'si' : 'no' },
      { concepto: 'Total MV actual en la fecha inicial', valor: monto(impacto.total_actual_inicio) },
      { concepto: 'Total MV resultante en la fecha inicial', valor: monto(impacto.total_resultante_inicio) },
      { concepto: 'Total MV actual en la fecha final', valor: monto(impacto.total_actual_fin) },
      { concepto: 'Total MV resultante en la fecha final', valor: monto(impacto.total_resultante_fin) },
      { concepto: 'Fechas en periodo cerrado', valor: impacto.periodos_cerrados.length },
    ]),
    el('div', { class: 'aviso' }, [el('div', {
      texto: 'La eliminacion no recalcula. Marca las fechas afectadas como desactualizadas '
           + 'y las envia a la bandeja de pendientes.' })]),
  ]);
  confirmarConMotivo('Eliminar posicion', descripcion, async (motivo) => {
    const r = await enviarJson(`/posiciones/${posicion.id}`, 'DELETE', { motivo });
    await dibujar(contenedor, ctx);
    await ctx.recargarNav();
    modal('Posicion eliminada', el('div', {}, [
      el('div', { class: 'aviso warn' }, [
        el('div', { texto: `${r.fechas_desactualizadas} fechas quedaron desactualizadas. `
          + 'El recalculo se decide y ejecuta en Reproceso.' }),
        el('div', { class: 'siguiente' }, [enlaceModulo('Ir a Reproceso', 'reproceso')])]),
    ]), []);
  });
}

async function reactivar(posicion, contenedor, ctx) {
  const r = await pedir(`/posiciones/${posicion.id}/reactivar`, { method: 'POST' });
  await dibujar(contenedor, ctx);
  await ctx.recargarNav();
  modal('Posicion reactivada', el('div', { class: 'aviso ok' }, [
    el('div', { texto: `${r.fechas_desactualizadas} fechas quedaron desactualizadas. `
      + 'No hace falta recargar precios: la serie se conservo.' }),
    el('div', { class: 'siguiente' }, [enlaceModulo('Ir a Reproceso', 'reproceso')])]), []);
}

// --- Detalle de instrumento ----------------------------------------------
async function detalleInstrumento(instrumento, datos, contenedor, ctx) {
  const acciones = [
    { texto: 'Editar maestra', al: () => { formularioMaestra(instrumento, contenedor, ctx); return true; } },
  ];
  if (instrumento.eliminado_en) {
    acciones.push({ texto: 'Reactivar', al: async () => {
      await pedir(`/instrumentos/${instrumento.isin}/reactivar`, { method: 'POST' });
      await dibujar(contenedor, ctx); return true; } });
  } else {
    acciones.push({ texto: 'Eliminar', clase: 'peligro', al: async () => {
      await eliminarInstrumento(instrumento, contenedor, ctx); return true; } });
  }
  const cal = await enviarJson('/instrumentos/calendario', 'POST', instrumento);
  modal(`${instrumento.isin}  ${instrumento.descripcion || ''}`, el('div', {}, [
    tabla(['campo', 'valor'], Object.entries(instrumento)
      .filter(([k]) => k !== 'descripcion')
      .map(([campo, valor]) => ({ campo, valor: valor === null ? '' : String(valor) }))),
    el('div', { class: 'aviso ok', style: 'margin-top:10px' }, [
      el('div', { texto: `Calendario de cupones derivado (${cal.calendario.length} fechas)` }),
      el('div', { class: 'tabular', style: 'margin-top:6px',
        texto: cal.calendario.map(formatearFecha).join('  ') })]),
  ]), acciones);
}

async function eliminarInstrumento(instrumento, contenedor, ctx) {
  const impacto = await pedir(`/instrumentos/${instrumento.isin}/impacto-eliminacion`);
  const descripcion = el('div', {}, [
    impacto.requiere_cascada
      ? el('div', { class: 'aviso alert' }, [el('div', {
          texto: `${instrumento.isin} tiene ${impacto.posiciones_activas.length} posicion(es) `
            + 'asociada(s). Confirmar aqui elimina en cascada lo siguiente:' }),
          tabla(['id', 'nominal', 'fecha_alta'], impacto.posiciones_activas)])
      : el('div', { class: 'aviso' }, [el('div', { texto: 'Sin posiciones asociadas.' })]),
    el('div', { class: 'aviso' }, [el('div', {
      texto: `Los ${impacto.precios_conservados} registros de precio no se eliminan: quedan `
        + 'como serie de referencia huerfana y siguen disponibles si el instrumento se '
        + 'vuelve a registrar.' })]),
  ]);
  confirmarConMotivo(`Eliminar ${instrumento.isin}`, descripcion, async (motivo) => {
    const r = await enviarJson(`/instrumentos/${instrumento.isin}`, 'DELETE',
      { motivo, cascada: true });
    await dibujar(contenedor, ctx);
    await ctx.recargarNav();
    modal('Instrumento eliminado', el('div', { class: 'aviso warn' }, [
      el('div', { texto: `${r.posiciones_eliminadas} posicion(es) eliminadas, `
        + `${r.fechas_desactualizadas} fechas desactualizadas, `
        + `${r.precios_conservados} precios conservados como huerfanos.` }),
      el('div', { class: 'siguiente' }, [enlaceModulo('Ir a Reproceso', 'reproceso')])]), []);
  });
}

function marcarError(e, entradas, errores, destino) {
  if (e.campo && errores[e.campo]) {
    errores[e.campo].textContent = e.message;
    entradas[e.campo].classList.add('invalido');
    entradas[e.campo].focus();
  } else {
    limpiar(destino);
    destino.appendChild(aviso(e.message, 'alert'));
  }
}
