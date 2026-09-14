// Control y quiebres contra T+0. Responde: en que difiere del estandar de mercado.
import {
  aviso, el, enlaceModulo, estadoGlobal, formatearFecha, guardarFiltros, limpiar, monto, pedir,
} from '../componentes/nucleo.js';
import { estadoVacio, marca, tabla } from '../componentes/tabla.js';

const NIVEL = {
  'Sin quiebre': 'ok',
  'Quiebre equivale a un dia de devengo': 'ok',
  Revisar: 'alert',
};

export async function render(raiz) {
  raiz.appendChild(el('div', { class: 'encabezado-modulo' }, [
    el('h1', { texto: 'Control y quiebres' }),
    el('span', { class: 'pregunta',
      texto: 'En que difiere la valorizacion del sistema de la convencion T+0 de mercado.' }),
  ]));

  const desde = el('input', { type: 'date', value: estadoGlobal.desde });
  const hasta = el('input', { type: 'date', value: estadoGlobal.hasta });
  const cuerpo = el('div');

  raiz.appendChild(el('div', { class: 'filtros' }, [
    el('div', { class: 'campo' }, [el('label', { texto: 'Desde' }), desde]),
    el('div', { class: 'campo' }, [el('label', { texto: 'Hasta' }), hasta]),
    el('button', { texto: 'Aplicar', onclick: () => {
      estadoGlobal.desde = desde.value; estadoGlobal.hasta = hasta.value;
      guardarFiltros(); refrescar(); } }),
  ]));
  raiz.appendChild(el('div', { class: 'aviso' }, [el('div', {
    texto: 'Bajo la convencion del sistema el quiebre contra T+0 es, por construccion, '
         + 'exactamente un dia de devengo del portafolio, todos los dias. Esa identidad '
         + 'convierte un desfase conocido en una constante verificable, y todo lo que se '
         + 'salga de ella en senal de error.' })]));
  raiz.appendChild(cuerpo);

  async function refrescar() {
    limpiar(cuerpo);
    const datos = await pedir(`/control?desde=${desde.value}&hasta=${hasta.value}`);
    if (!datos.filas.length) {
      cuerpo.appendChild(el('div', { class: 'panel' }, [estadoVacio(
        'No hay nada que controlar en este rango.',
        'El control se calcula junto con la valorizacion. Ejecuta el reproceso del rango.',
        enlaceModulo('Ir a Reproceso', 'reproceso', { desde: desde.value, hasta: hasta.value }))]));
      return;
    }
    const conteo = {};
    for (const f of datos.filas) conteo[f.estado_quiebre] = (conteo[f.estado_quiebre] || 0) + 1;
    const revisar = conteo.Revisar || 0;
    const residualMax = Math.max(...datos.filas.map((f) => Math.abs(Number(f.residual || 0))));

    cuerpo.appendChild(el('div', { class: 'panel' }, [
      el('div', { class: 'cifras' }, [
        cifra('Fechas evaluadas', datos.filas.length),
        cifra('Sin quiebre', conteo['Sin quiebre'] || 0),
        cifra('Un dia de devengo', conteo['Quiebre equivale a un dia de devengo'] || 0),
        cifra('Revisar', revisar),
        cifra('Residual maximo', monto(residualMax)),
      ]),
    ]));

    cuerpo.appendChild(revisar
      ? aviso(`${revisar} fecha(s) en estado Revisar: tienen un error distinto al desfase `
            + 'conocido de un dia.', 'alert')
      : aviso('Todas las fechas quedan explicadas por el desfase de un dia de devengo.', 'ok'));

    cuerpo.appendChild(el('div', { class: 'panel' }, [
      el('h2', {}, ['Quiebre por fecha']),
      tabla(['fecha', 'total_mv_base', 'total_mv_base_t0', 'quiebre_t0', 'devengo_diario',
             'residual', 'estado_quiebre'],
        datos.filas, { claseFila: (f) => (f.estado_quiebre === 'Revisar' ? 'negativo' : '') }),
      el('div', { class: 'leyenda' }, [
        'Quiebre = Total MV del control T+0 menos Total MV del sistema. ',
        'Residual = quiebre + devengo diario teorico del portafolio. ',
        marca('Sin quiebre', 'ok'), marca('Un dia de devengo', 'ok'), marca('Revisar', 'alert'),
      ]),
    ]));
  }

  await refrescar();
}

function cifra(etiqueta, valor) {
  return el('div', { class: 'cifra' }, [
    el('div', { class: 'etiqueta', texto: etiqueta }),
    el('div', { class: 'valor', texto: String(valor) })]);
}
