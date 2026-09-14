// Panel de validaciones. Responde: que esta mal.
import { el, enlaceModulo, estadoGlobal, limpiar, pedir } from '../componentes/nucleo.js';
import { estadoVacio, marca, tabla } from '../componentes/tabla.js';

export async function render(raiz) {
  raiz.appendChild(el('div', { class: 'encabezado-modulo' }, [
    el('h1', { texto: 'Validaciones' }),
    el('span', { class: 'pregunta', texto: 'Que esta mal en los datos o en el calculo.' }),
  ]));

  const desde = el('input', { type: 'date', value: estadoGlobal.desde });
  const hasta = el('input', { type: 'date', value: estadoGlobal.hasta });
  const cuerpo = el('div');
  raiz.appendChild(el('div', { class: 'filtros' }, [
    el('div', { class: 'campo' }, [el('label', { texto: 'Desde' }), desde]),
    el('div', { class: 'campo' }, [el('label', { texto: 'Hasta' }), hasta]),
    el('button', { texto: 'Recalcular panel', onclick: refrescar }),
  ]));
  raiz.appendChild(cuerpo);

  async function refrescar() {
    limpiar(cuerpo);
    const datos = await pedir(`/validaciones?desde=${desde.value}&hasta=${hasta.value}`);
    cuerpo.appendChild(el('div', { class: 'panel' }, [
      el('div', { class: 'cifras' }, [
        cifra('Alertas', datos.resumen.alertas),
        cifra('Advertencias', datos.resumen.advertencias),
        cifra('Conformes', datos.resumen.conformes),
      ]),
    ]));

    for (const v of datos.validaciones) {
      const panel = el('div', { class: 'panel' }, [
        el('h2', {}, [
          `${v.codigo}. ${v.titulo}`,
          el('span', { class: 'acciones' }, [
            marca(v.hallazgos ? `${v.hallazgos} hallazgo(s)` : 'conforme', v.nivel)]),
        ]),
      ]);
      if (v.hallazgos && v.detalle.length) {
        const columnas = [...new Set(v.detalle.flatMap((d) => Object.keys(d)))];
        panel.appendChild(tabla(columnas, v.detalle));
      } else if (v.hallazgos) {
        panel.appendChild(el('div', { class: 'cuerpo', texto: `${v.hallazgos} hallazgo(s).` }));
      } else {
        panel.appendChild(el('div', { class: 'cuerpo muted', texto: 'Sin hallazgos.' }));
      }
      cuerpo.appendChild(panel);
    }
  }

  await refrescar();
}

function cifra(etiqueta, valor) {
  return el('div', { class: 'cifra' }, [
    el('div', { class: 'etiqueta', texto: etiqueta }),
    el('div', { class: 'valor', texto: String(valor) })]);
}
