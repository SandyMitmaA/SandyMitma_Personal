# Design truth — Datamar BI OAS · Capacitación GOI

## Concepto

**«La guía y el sistema».** El video es una conversación entre dos voces: una
persona que orienta y una máquina que responde. Todo el diseño sostiene esa
dualidad — la voz institucional presenta cada paso en un panel limpio a la
izquierda, y la pantalla real del sistema aparece a la derecha como evidencia.
El espectador nunca duda de qué es instrucción y qué es software.

## Paleta

Los azules **no son inventados**: están muestreados de las propias capturas de
OAS, así que el video y el sistema comparten color literal.

| Token | Hex | Origen | Uso |
|---|---|---|---|
| `--navy` | `#003366` | títulos de sección en Overview | texto de titulares, barra superior |
| `--blue` | `#0d4988` | barra «00.- Overview» de OAS | color principal, paneles, portada |
| `--link` | `#007dc9` | enlaces de OAS | acentos, subrayados, números de paso |
| `--sky` | `#29a1e6` | hover de enlaces | resaltados, trazos de atención |
| `--paper` | `#f4f7fb` | — (blanco tintado hacia el azul) | fondo de todas las escenas |
| `--ink` | `#0f2b4a` | — | texto de cuerpo sobre fondo claro |
| `--rule` | `#c9d8e8` | — | reglas, bordes de ficha, divisores |

Lienzo **claro**: es capacitación institucional, no cine. Un fondo oscuro
convertiría capturas de pantalla blancas en parches cegadores. El blanco puro
`#fff` se reserva para las fichas que contienen capturas, de modo que la captura
flote sobre el papel y no se funda con él.

Contraste verificado: `--ink` sobre `--paper` ≈ 12:1 · blanco sobre `--blue` ≈ 9:1 ·
`--blue` sobre `--paper` ≈ 8:1. Todos superan WCAG AA con holgura.

## Tipografía

**Montserrat** (900 / 700 / 400) + **IBM Plex Mono** (700 / 400).

La tensión es literal, no decorativa: Montserrat es la voz institucional —
geométrica, pública, la que rotula un banco central. IBM Plex Mono es la voz de
la máquina — nació para interfaces técnicas y aquí rotula lo que pertenece al
sistema: la URL, los nombres de campo, los formatos de archivo, el número de paso.
Cuando el espectador ve monoespaciado, está mirando algo que el software dice.

Escalas de video, no de web:

| Rol | Familia | Tamaño | Peso |
|---|---|---|---|
| Titular de portada | Montserrat | 96 px | 900 |
| Título de escena | Montserrat | 62 px | 900 |
| Cuerpo / apoyo | Montserrat | 34 px | 400 |
| Etiqueta de sistema | IBM Plex Mono | 30 px | 700 |
| Número de paso | IBM Plex Mono | 26 px | 700 |
| Subtítulo | Montserrat | 38 px | 700 |

Tracking `-0.03em` en los titulares. Contraste de peso 900 vs 400, nunca 700 vs 400.

## Sistema de composición

Todas las escenas de contenido (2 a 10) comparten una rejilla de dos zonas para
que el ojo no tenga que reaprender dónde mirar:

```
┌─────────────────────────────────────────────────────────┐
│  barra superior — navy, 8px, con el paso actual         │
├──────────────────┬──────────────────────────────────────┤
│  PANEL IZQUIERDO │   ESCENARIO DERECHO                  │
│  620 px          │                                      │
│                  │   la captura, sobre ficha blanca     │
│  · nº de paso    │   con sombra y borde --rule          │
│  · título        │                                      │
│  · apoyo         │   los resaltados viven aquí          │
└──────────────────┴──────────────────────────────────────┘
│  franja de subtítulos — 150 px inferiores               │
└─────────────────────────────────────────────────────────┘
```

Las portadas (0 y 11) rompen la rejilla a propósito: fondo `--blue` a sangre,
titular centrado, escudo reservado arriba. El corte entre portada y rejilla es lo
que marca «empieza el procedimiento» y «terminó el procedimiento».

## Tratamiento de las capturas

- Cada captura va sobre una **ficha blanca** con borde `2px --rule` y sombra
  `0 18px 50px rgba(0,51,102,.18)`. Nunca a sangre: el marco declara «esto es una
  pantalla», no «esto es el video».
- Las capturas grandes (escenas 3, 4, 5, 9, 10) se escalan a la altura del
  escenario y admiten punch-in sobre la zona que la voz menciona.
- Las capturas pequeñas (escenas 6, 7, 8) se amplían a **2× como máximo** y se
  centran en el escenario. Más aumento las rompe.
### Resaltado: reflector, no recuadro

Siete de las nueve capturas **ya traen recuadros rojos** dibujados por el área
(escenas 4, 5, 6, 7, 8, 9 y 10). Dibujar encima un recuadro azul competiría con
ellos y ensuciaría el cuadro. Así que el mecanismo de atención es un **reflector**,
no un marco:

- Una máscara `#0d4988` al 42% cubre la ficha entera y se abre una **ventana
  limpia** sobre la zona que la voz nombra en ese momento.
- La ventana lleva un **halo `--sky` de 3px** en su borde — suficiente para
  definirla, sin volverse un segundo recuadro.
- Al pasar al siguiente elemento la ventana **se desplaza** en lugar de apagarse
  y encenderse: el ojo la sigue y entiende que es un solo foco recorriendo la
  pantalla.

Esto compone bien con los recuadros rojos existentes: el rojo dice «esto es lo
importante» y el reflector dice «esto es lo que se está diciendo ahora».

En las dos capturas **sin anotación** (escena 2, login; escena 3, Overview) el
reflector funciona igual, sin necesidad de añadir marcos propios.

## Capa de fondo

Sobre `--paper`, tres decorativos persistentes con movimiento ambiental lento:

1. **Malla de puntos** `--rule` al 22%, 48px de paso, con deriva vertical muy lenta.
2. **Halo radial** `--sky` al 14% en la esquina superior derecha, respirando en escala.
3. **Regla vertical** `--rule` de 2px que separa el panel del escenario, con un
   pulso de opacidad sincronizado con la entrada de cada escena.

## Movimiento

- Entradas de 0.4–0.6 s, ejes y eases variados dentro de cada escena.
- El panel izquierdo entra desde la izquierda; la ficha del escenario entra con
  escala 0.96 → 1 y opacidad; los resaltados aparecen con `back.out` breve.
- Los resaltados secuenciales (escenas 5, 7, 8) siguen el orden de la voz, con
  el anterior bajando a 25% de opacidad en lugar de desaparecer — el espectador
  conserva el mapa completo mientras avanza.
- Sin `repeat: -1` en ningún sitio: todos los ciclos ambientales usan conteo finito.

## Prohibiciones

- Nada de gradientes de texto, ni acentos neón, ni cian sobre oscuro.
- Nada de rojo salvo el que ya viene dentro de las capturas.
- Nada de `#000` ni `#fff` puros fuera de las fichas.
- No inventar pasos, cifras, nombres de reporte ni afirmaciones que el guion no diga.
