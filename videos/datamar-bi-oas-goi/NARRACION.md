# Narración para sintetizar — Datamar BI OAS · GOI

**Voz:** `es-PE-CamilaNeural` (Azure Speech · español de Perú, femenina)
**Formato de salida:** WAV 48 kHz 16-bit mono (o MP3 192 kbps si tu herramienta no da WAV)
**Dónde dejar los archivos:** `assets/audio/`

---

## Cómo entregar el audio

**Opción recomendada — un archivo por escena.** Es la que permite ajustar una
escena sin volver a sintetizar todo el video. Nombra cada archivo exactamente así:

```
assets/audio/esc00.wav   assets/audio/esc04.wav   assets/audio/esc08.wav
assets/audio/esc01.wav   assets/audio/esc05.wav   assets/audio/esc09.wav
assets/audio/esc02.wav   assets/audio/esc06.wav   assets/audio/esc10.wav
assets/audio/esc03.wav   assets/audio/esc07.wav   assets/audio/esc11.wav
```

**Opción alternativa — un solo archivo continuo.** Nómbralo
`assets/audio/narracion-completa.wav`. Si eliges esta vía, deja **un silencio de
1 segundo entre escena y escena** al sintetizar: así puedo detectar los cortes
automáticamente y repartir los tiempos. Sin esos silencios el corte hay que
hacerlo a mano y es mucho más frágil.

---

## Ajustes de voz sugeridos

El guion pide un tono «delicado, cálido y profesional», con dicción clara y ritmo
pausado. Para capacitación institucional funciona bien:

| Parámetro | Valor sugerido |
|---|---|
| Velocidad (`rate`) | `-8%` — pausado, sin sonar lento |
| Tono (`pitch`) | `default` — Camila ya es cálida de fábrica |
| Estilo | `friendly` si tu herramienta lo ofrece; si no, el neutro está bien |

Al final de este documento tienes el SSML ya armado con estos valores, listo para
pegar en Speech Studio.

---

## Texto por escena

Lo que sigue es **solo lo que se pronuncia**. No leas los títulos ni los
encabezados: son referencia para ti.

### Escena 0 — Portada

> Bienvenidos a esta capacitación sobre el acceso al Sistema Datamart BI, OAS, de la Gerencia de Operaciones Internacionales.

### Escena 1 — Acceso a la plataforma

> Para acceder a la plataforma, debemos ingresar al siguiente link.

### Escena 2 — Ventana de login

> En la ventana se mostrará la pantalla de login. Aquí deberás ingresar tus credenciales: usuario y contraseña.

### Escena 3 — Página principal Overview

> Esto nos dirigirá a la ventana principal, Overview, donde se muestran los diversos dashboards y reportes disponibles, agrupados por área temática. Por ejemplo: Portafolio y Contrapartes, o Indicadores de Desempeño, entre otros.

### Escena 4 — Acceder a un reporte

> Si se requiere consultar alguno de estos reportes, solo es necesario dar clic para acceder. Por ejemplo, el reporte de Portafolio vs Referencia.

### Escena 5 — Panel de filtros

> Aquí se mostrará el reporte. En la parte lateral izquierda encontramos un panel con los filtros disponibles: frecuencia, ya sea diaria, mensual o anual; fecha o rango de fecha; moneda; instrumento; metodología de consulta; y si se desea ver el reporte a nivel de tramo o moneda. Finalmente, se debe presionar Aplicar.

### Escena 6 — Opción de exportar

> Para exportar los resultados, en la parte inferior se mostrará la opción de exportar.

### Escena 7 — Exportar Con Formato

> Al hacer clic se mostrarán los distintos formatos disponibles. Con la opción Con Formato, se puede exportar en PDF, Excel, PowerPoint o archivo web.

### Escena 8 — Exportar Datos

> Con la otra opción, Datos, se podrá exportar en formatos Excel, CSV, delimitado por tabulaciones, y XML.

### Escena 9 — Otra forma de exportar

> Otra manera de exportar es dando clic en la parte superior derecha, en Exportar a Excel, o en Exportar Página Actual.

### Escena 10 — Regresar a la página principal

> Si se requiere regresar a la página principal, nos dirigimos a Panel de Control y hacemos clic en Overview.

### Escena 11 — Cierre

> De esta manera podrás interactuar con los diversos reportes disponibles que existen en el OAS. Con esto, ya conoces cómo acceder, navegar, filtrar y exportar reportes en el Datamart BI OAS de la GOI.

---

## Nota sobre la pronunciación de siglas

Camila leerá algunas siglas letra por letra y otras como palabra. Conviene
revisar estas cuatro en la primera prueba y, si suenan mal, usar el SSML de abajo
que ya las corrige:

| Sigla | Cómo debe sonar |
|---|---|
| OAS | «o-as» (deletreada) |
| BI | «bi-ai» |
| CSV | «ce-ese-uve» (deletreada) |
| XML | «equis-eme-ele» (deletreada) |
| PDF | «pe-de-efe» (deletreada) |

El SSML incluye `<say-as interpret-as="characters">` en las que suelen fallar.
Si al escucharlas ya suenan bien sin ayuda, puedes borrar esas etiquetas.
