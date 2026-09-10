---
format: 1920x1080
duration: 148s
message: "Cualquier persona de la GOI puede entrar a Datamart BI, encontrar su reporte, filtrarlo y exportarlo"
arc: "Bienvenida → Entrar → Reconocer → Consultar → Filtrar → Exportar → Volver → Cierre"
audience: "Personal de la Gerencia de Operaciones Internacionales del BCRP"
mode: autonomous
---

## Frame 0 — Portada

- status: outline
- src: compositions/esc00-portada.html
- duration: 9s
- transition_in: cut
- scene: Título de la capacitación sobre azul institucional a sangre.
- voiceover: "Bienvenidos a esta capacitación sobre el acceso al Sistema Datamart BI, OAS, de la Gerencia de Operaciones Internacionales."
- poster: 4
- motion: blueprint `kinetic-type-beats` · reglas `waterfall-entry`, `ambient-glow-bloom`

Fondo `--blue` completo. El título llega en cascada por líneas: «Capacitación» en
mono pequeño, «Acceso al Sistema Datamart BI – OAS» en Montserrat 900 a 96px, y
«Gerencia de Operaciones Internacionales» como pie. Espacio reservado arriba para
el escudo del BCRP. Un halo `--sky` respira detrás del titular. Esta escena y la
11 son las únicas que rompen la rejilla de dos zonas.

## Frame 1 — Acceso a la plataforma

- status: outline
- src: compositions/esc01-link.html
- duration: 7s
- transition_in: crossfade
- scene: La URL de acceso presentada como una barra de navegador aislada.
- voiceover: "Para acceder a la plataforma, debemos ingresar al siguiente link."
- poster: 4
- motion: reglas `waterfall-entry`, `spring-pop-entrance`, `svg-path-draw`

Primera aparición de la rejilla. Panel izquierdo: «PASO 01» en mono, título
«Ingresa al link de acceso». Escenario: una barra de direcciones reconstruida
—no una captura— con `oasgoi.bcrp.gob:9502/analytics/` en IBM Plex Mono a 44px.
La barra entra con pop; un trazo `--sky` se dibuja bajo la URL de izquierda a
derecha. Reconstruida y no capturada porque el guion no trae imagen para esta
escena y el texto debe leerse nítido.

## Frame 2 — Ventana de login

- status: outline
- src: compositions/esc02-login.html
- duration: 10s
- transition_in: crossfade
- scene: Captura del login con los dos campos y el botón Conectar resaltados en orden.
- voiceover: "En la ventana se mostrará la pantalla de login. Aquí deberás ingresar tus credenciales: usuario y contraseña."
- poster: 6
- motion: blueprint `device-surface-showcase` (static tour) · reglas `spring-pop-entrance`, `svg-path-draw`, `sine-wave-loop`

`escena02_login.png` (657×683, vertical) va en ficha blanca centrada en el
escenario, escalada a la altura disponible. Tres resaltados de trazo `--sky` se
dibujan en secuencia: ID de Usuario → Contraseña → botón Conectar. Cada uno baja
a 25% cuando entra el siguiente.

## Frame 3 — Página principal Overview

- status: outline
- src: compositions/esc03-overview.html
- duration: 16s
- transition_in: crossfade
- scene: La página Overview completa; la cámara se acerca a dos bloques temáticos.
- voiceover: "Esto nos dirigirá a la ventana principal, Overview, donde se muestran los diversos dashboards y reportes disponibles, agrupados por área temática. Por ejemplo: Portafolio y Contrapartes, o Indicadores de Desempeño, entre otros."
- poster: 10
- motion: blueprint `spatial-pan-stations` · reglas `coordinate-target-zoom`, `svg-path-draw`

La escena más densa: la captura tiene 14 bloques de enlaces diminutos. Se muestra
completa 4 s para dar el panorama, luego un punch-in a 1.5× sobre la columna
izquierda mientras la voz nombra «Portafolio y Contrapartes» y «Indicadores de
Desempeño», con un resaltado por bloque. El zoom es lo que hace legible el texto
de 12px de la captura; sin él la escena no cumple su función.

## Frame 4 — Acceder a un reporte

- status: outline
- src: compositions/esc04-abrir-reporte.html
- duration: 12s
- transition_in: crossfade
- scene: El cursor viaja al enlace del reporte, hace clic y aparece el reporte.
- voiceover: "Si se requiere consultar alguno de estos reportes, solo es necesario dar clic para acceder. Por ejemplo, el reporte de Portafolio vs Referencia."
- poster: 8
- motion: blueprint `cursor-ui-demo` · componente `simulated-cursor` · reglas `cursor-click-ripple`, `scale-swap-transition`

Única escena con interacción representada. Arranca sobre el recorte de Overview
donde vive el enlace «Portafolio vs Referencia»; el cursor entra desde fuera de
cuadro, viaja al enlace, se hunde con el pulso de clic, y la ficha cambia por
`escena04_reporte_portafolio_vs_referencia.png` con un swap de escala. El cursor
usa `tone: dark` porque va sobre pantalla blanca.

## Frame 5 — Panel de filtros

- status: outline
- src: compositions/esc05-filtros.html
- duration: 25s
- transition_in: crossfade
- scene: El panel de filtros a la izquierda, cada control resaltado cuando la voz lo nombra.
- voiceover: "Aquí se mostrará el reporte. En la parte lateral izquierda encontramos un panel con los filtros disponibles: frecuencia, ya sea diaria, mensual o anual; fecha o rango de fecha; moneda; instrumento; metodología de consulta; y si se desea ver el reporte a nivel de tramo o moneda. Finalmente, se debe presionar Aplicar."
- poster: 14
- motion: blueprint `panel-edit-live-sync` · reglas `depth-of-field-blur`, `control-target-sync`, `svg-path-draw`

La escena más larga (25 s) y la de mayor carga informativa: seis filtros más el
botón Aplicar, nombrados en orden. La captura ya trae un recuadro rojo del área
sobre el panel completo; el encuadre se apoya en él en lugar de competir. Cada
control se ilumina por turno con el resto en `depth-of-field-blur` suave, y el
botón Aplicar cierra la secuencia con un pulso. Siete resaltados en 21 s de voz
≈ 3 s por control: cómodo.

## Frame 6 — Opción de exportar

- status: outline
- src: compositions/esc06-exportar.html
- duration: 8s
- transition_in: crossfade
- scene: El enlace Exportar al pie del reporte, ampliado como ficha.
- voiceover: "Para exportar los resultados, en la parte inferior se mostrará la opción de exportar."
- poster: 5
- motion: reglas `spring-pop-entrance`, `svg-path-draw`, `ambient-glow-bloom`

`escena06_opcion_exportar.png` mide 292×92 — la captura más pequeña del lote. Se
presenta a 2× (584×184) centrada en el escenario, nunca a sangre. Un resaltado
rodea la palabra «Exportar».

## Frame 7 — Exportar «Con formato»

- status: outline
- src: compositions/esc07-con-formato.html
- duration: 13s
- transition_in: crossfade
- scene: El submenú desplegado; los cuatro formatos se resaltan en orden.
- voiceover: "Al hacer clic se mostrarán los distintos formatos disponibles. Con la opción Con Formato, se puede exportar en PDF, Excel, PowerPoint o archivo web."
- poster: 8
- motion: blueprint `cursor-ui-demo` · reglas `anchored-layout-expand`, `waterfall-entry`, `svg-path-draw`

`escena07_exportar_con_formato.png` (304×171) a 2×. El submenú se revela con
`anchored-layout-expand` anclado en el borde donde nace, luego PDF → Excel →
PowerPoint → Archivo Web se resaltan uno por uno siguiendo la voz.

## Frame 8 — Exportar «Datos»

- status: outline
- src: compositions/esc08-datos.html
- duration: 10s
- transition_in: crossfade
- scene: El segundo submenú con los cuatro formatos de datos.
- voiceover: "Con la otra opción, Datos, se podrá exportar en formatos Excel, CSV, delimitado por tabulaciones, y XML."
- poster: 6
- motion: reglas `waterfall-entry`, `spring-pop-entrance`, `svg-path-draw`

`escena08_exportar_datos.png` (378×131) a 2×. Misma gramática que la escena 7
para que el espectador lea las dos rutas de exportación como un par, no como dos
temas distintos. Cuatro resaltados en 7 s de voz — más rápido que la escena 7, así
que el resaltado anterior se apaga antes.

## Frame 9 — Otra forma de exportar

- status: outline
- src: compositions/esc09-superior-derecha.html
- duration: 12s
- transition_in: crossfade
- scene: Las acciones de la esquina superior derecha del reporte.
- voiceover: "Otra manera de exportar es dando clic en la parte superior derecha, en Exportar a Excel, o en Exportar Página Actual."
- poster: 8
- motion: reglas `coordinate-target-zoom`, `svg-path-draw`, `spring-pop-entrance`

`escena09_exportar_excel_pagina.png` (605×372) en ficha, con punch-in sobre las
dos acciones nombradas y un resaltado para cada una.

## Frame 10 — Regresar a la página principal

- status: outline
- src: compositions/esc10-regresar.html
- duration: 11s
- transition_in: crossfade
- scene: La ruta Panel de Control > Overview marcada como recorrido de dos pasos.
- voiceover: "Si se requiere regresar a la página principal, nos dirigimos a Panel de Control y hacemos clic en Overview."
- poster: 7
- motion: reglas `coordinate-target-zoom`, `svg-path-draw`, `nudge-curve`

`escena10_regresar_overview.png` (542×495) en ficha. Dos resaltados encadenados
—Panel de Control, luego Overview— unidos por un trazo `--sky` que se dibuja del
primero al segundo: la ruta se ve como ruta, no como dos puntos sueltos.

## Frame 11 — Cierre

- status: outline
- src: compositions/esc11-cierre.html
- duration: 15s
- transition_in: crossfade
- scene: Cierre sobre azul institucional con el resumen de las cuatro acciones aprendidas.
- voiceover: "De esta manera podrás interactuar con los diversos reportes disponibles que existen en el OAS. Con esto, ya conoces cómo acceder, navegar, filtrar y exportar reportes en Datamart BI OAS."
- poster: 9
- motion: blueprint `kinetic-type-beats` · reglas `waterfall-entry`, `ambient-glow-bloom`

Vuelve al fondo `--blue` de la portada para cerrar el paréntesis. Las cuatro
acciones —acceder, navegar, filtrar, exportar— llegan en cascada como cuatro
fichas mono, y el titular «Ya puedes navegar Datamart BI» se asienta debajo.
Espacio reservado para el escudo y para datos de soporte si el área los entrega.
