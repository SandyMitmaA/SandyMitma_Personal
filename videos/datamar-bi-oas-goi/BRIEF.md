---
workflow: general-video
flow: automation
storyboard: no
message: "Cualquier persona de la GOI puede entrar a Datamar BI, encontrar su reporte, filtrarlo y exportarlo"
destination: web
aspect: 1920x1080
language: es
audience: "Personal de la Gerencia de Operaciones Internacionales del BCRP"
length: 148s
angle: tutorial
---

## Intent

Video de capacitación institucional para el personal de la GOI sobre el acceso al
Sistema Datamar BI – OAS (Oracle Analytics Server). Recorre el flujo completo de
un usuario nuevo: entrar por el link, autenticarse, reconocer la página Overview,
abrir un reporte, usar el panel de filtros, exportar en sus distintos formatos y
volver al inicio.

El tono es el de una guía institucional: cálida y clara, sin ser publicitaria.
El video no vende nada — enseña un procedimiento. La voz narradora acompaña,
no anima. Cada escena debe poder pausarse y seguir siendo un instructivo legible.

El guion original del área está en `GUION-ORIGINAL.md` y es la fuente de verdad
del contenido; este proyecto no inventa pasos ni afirma nada que el guion no diga.

## Assets

- `assets/capturas/escena02_login.png` — pantalla de login de OAS; escena 2.
- `assets/capturas/escena03_overview_dashboards.png` — página Overview completa; escena 3.
- `assets/capturas/escena04_reporte_portafolio_vs_referencia.png` — reporte Portafolio vs Referencia; escena 4.
- `assets/capturas/escena05_panel_filtros.png` — reporte con el panel de filtros marcado en rojo; escena 5.
- `assets/capturas/escena06_opcion_exportar.png` — enlace Exportar al pie del reporte; escena 6.
- `assets/capturas/escena07_exportar_con_formato.png` — submenú Con formato; escena 7.
- `assets/capturas/escena08_exportar_datos.png` — submenú Datos; escena 8.
- `assets/capturas/escena09_exportar_excel_pagina.png` — acciones de la esquina superior derecha; escena 9.
- `assets/capturas/escena10_regresar_overview.png` — menú Panel de Control > Overview; escena 10.
- `assets/audio/esc00.wav` … `esc11.wav` — narración, **pendiente de entrega** por la usuaria.

## Customizations

- **Narración externa.** La voz es `es-PE-CamilaNeural` (Azure Speech) y se
  sintetiza fuera de este entorno; aquí no hay proveedor de Azure ni credenciales.
  El texto listo para sintetizar está en `NARRACION.md` y en `narracion-ssml/`.
  El video se construye primero con las duraciones estimadas del guion y se
  re-sincroniza contra el audio real cuando llegue.
- **Subtítulos** en la franja inferior, sincronizados con la narración.
- **Cursor animado** en la escena 4, donde el guion pide mostrar el clic sobre el reporte.
- **Resaltado secuencial** de los filtros en la escena 5 y de los formatos de
  exportación en las escenas 7 y 8, siguiendo el orden en que la voz los nombra.

## Notes

- **No hay logo del BCRP.** El guion lo marca como opcional en las escenas 0 y 11.
  Las portadas se diseñan con un espacio reservado para el escudo; si la usuaria
  entrega el archivo, entra sin rediseñar la escena.
- **La captura de la escena 5 ya trae un recuadro rojo** dibujado sobre el panel
  de filtros. Choca con la paleta azul institucional, así que esa escena enmarca
  la captura de modo que el recuadro rojo quede fuera del encuadre o se apoye en
  él en lugar de duplicarlo con un resaltado azul encima.
- **Tres capturas son muy pequeñas** (escena 6: 292×92, escena 7: 304×171,
  escena 8: 378×131). Ampliadas a pantalla completa se verían borrosas, así que
  se presentan como fichas ampliadas a 2× sobre un fondo diseñado, nunca a sangre.
- El header del guion dice 2:40–3:10, pero sus propios tiempos por escena suman
  2:30 y la narración pura mide ~1:52. Se trabaja con 2:28 y se ajusta al audio real.
- La URL `oasgoi.bcrp.gob:9502/analytics/` es un host interno; aparece tal cual
  porque es lo que el usuario debe escribir.
