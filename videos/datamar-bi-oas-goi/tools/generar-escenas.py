#!/usr/bin/env python3
"""Genera las escenas de contenido del video Datamart BI OAS.

Uso:
    python3 tools/generar-escenas.py                # duraciones autorales
    python3 tools/generar-escenas.py --voz camila   # calzadas a esa narración

Todas las escenas comparten la misma rejilla (panel izquierdo + escenario
derecho) y el mismo mecanismo de atención: un reflector que oscurece la ficha
salvo una ventana limpia sobre lo que la voz nombra en ese instante.

Los tiempos de los reflectores y de la cámara se escriben aquí contra una
duración autoral. Con `--voz` se reescalan a la narración real: si la locutora
tarda un 26% más, cada foco se enciende un 26% más tarde y sigue cayendo sobre
la palabra correcta. Sin ese reescalado los focos se adelantan a la voz.
"""
import argparse
import contextlib
import os
import subprocess
import sys
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "compositions")
AUDIO_BASE = os.path.join(ROOT, "assets", "audio")

LEAD, TAIL, MIN_DUR = 0.6, 1.2, 4.0
EXTS = (".wav", ".mp3", ".m4a", ".aac", ".ogg")


def dur_audio(path):
    if path.lower().endswith(".wav"):
        with contextlib.suppress(Exception):
            with wave.open(path, "rb") as w:
                return w.getnframes() / float(w.getframerate())
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True).stdout.strip()
    return float(out)


def voz_de(slug, voz):
    if not voz:
        return None
    for ext in EXTS:
        p = os.path.join(AUDIO_BASE, voz, slug + ext)
        if os.path.isfile(p):
            return dur_audio(p)
    return None


def reescalar(spec, voz):
    """Estira la coreografía de una escena para que siga a la narración real."""
    hablado = voz_de(spec["id"].split("-")[0], voz)
    if hablado is None:
        return spec, 1.0
    nueva = max(MIN_DUR, spec["dur"], round(LEAD + hablado + TAIL, 2))
    k = nueva / spec["dur"]
    if abs(k - 1) < 0.01:
        return spec, 1.0
    spec = dict(spec)
    spec["dur"] = round(nueva, 2)
    if spec.get("spots"):
        spec["spots"] = [dict(s, at=round(s["at"] * k, 2)) for s in spec["spots"]]
    if spec.get("camera"):
        spec["camera"] = [dict(c, at=round(c["at"] * k, 2),
                               **({"d": round(c["d"] * k, 2)} if "d" in c else {}))
                          for c in spec["camera"]]
    return spec, k

CSS = """
        #root {
          position: absolute;
          inset: 0;
          width: 1920px;
          height: 1080px;
          overflow: hidden;
          background: #f4f7fb;
          font-family: "Montserrat", sans-serif;
          color: #0f2b4a;
        }
        .bg-mesh {
          position: absolute;
          inset: -60px;
          background-image: radial-gradient(rgba(13, 73, 136, 0.22) 2px, transparent 2px);
          background-size: 48px 48px;
          opacity: 0.55;
        }
        .bg-glow {
          position: absolute;
          top: -300px;
          right: -240px;
          width: 1000px;
          height: 1000px;
          border-radius: 50%;
          background: radial-gradient(circle, rgba(41, 161, 230, 0.26) 0%, rgba(41, 161, 230, 0) 68%);
        }
        .topbar {
          position: absolute;
          top: 0;
          left: 0;
          width: 1920px;
          height: 8px;
          background: #003366;
          transform-origin: left center;
        }
        .panel {
          position: absolute;
          left: 0;
          top: 8px;
          width: 620px;
          height: 922px;
          padding: 132px 58px 0 110px;
        }
        .step {
          font-family: "IBM Plex Mono", monospace;
          font-weight: 700;
          font-size: 26px;
          letter-spacing: 0.22em;
          color: #007dc9;
          text-transform: uppercase;
          margin-bottom: 26px;
        }
        .ptitle {
          font-size: 58px;
          font-weight: 900;
          line-height: 1.1;
          letter-spacing: -0.03em;
          color: #003366;
        }
        .prule {
          width: 120px;
          height: 5px;
          background: #29a1e6;
          margin: 32px 0 28px;
          transform-origin: left center;
        }
        .psub {
          font-size: 32px;
          font-weight: 400;
          line-height: 1.42;
        }
        .cue-list {
          margin-top: 40px;
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .cue {
          font-family: "IBM Plex Mono", monospace;
          font-size: 25px;
          font-weight: 700;
          letter-spacing: 0.03em;
          color: #0d4988;
          padding-left: 26px;
          border-left: 4px solid #29a1e6;
          line-height: 1.3;
        }
        .divider {
          position: absolute;
          left: 620px;
          top: 8px;
          width: 2px;
          height: 922px;
          background: #c9d8e8;
          transform-origin: top center;
        }
        .stage {
          position: absolute;
          left: 620px;
          top: 8px;
          width: 1300px;
          height: 922px;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .card {
          position: relative;
          overflow: hidden;
          background: #ffffff;
          border: 3px solid #c9d8e8;
          box-shadow: 0 20px 54px rgba(0, 51, 102, 0.2);
        }
        .zoom {
          position: absolute;
          left: 0;
          top: 0;
          transform-origin: 0 0;
        }
        .zoom img {
          display: block;
        }
        .spot {
          position: absolute;
          left: 0;
          top: 0;
          transform-origin: 0 0;
          box-shadow: 0 0 0 9999px rgba(13, 73, 136, 0.4);
        }
"""


def scene(spec):
    """Compone un archivo de sub-composición a partir de la especificación."""
    iw, ih = spec["img_size"]
    base = spec["base"]
    card_w, card_h = round(iw * base), round(ih * base)

    # --- cámara: cada estado se expresa en coordenadas de la imagen ---
    cams = spec.get("camera") or [{"at": 0, "scale": base, "cx": iw / 2, "cy": ih / 2, "d": 0.01}]

    def cam_xy(c):
        """Traduce un centro de interés a desplazamiento, sin salirse de la imagen.

        Sin este recorte un punto de interés cercano al borde deja franjas
        muertas dentro de la ficha, que se leen como un panel vacío.
        """
        z = c["scale"]
        vis_w, vis_h = card_w / z, card_h / z
        cx = c["cx"] if vis_w >= iw else min(max(c["cx"], vis_w / 2), iw - vis_w / 2)
        cy = c["cy"] if vis_h >= ih else min(max(c["cy"], vis_h / 2), ih - vis_h / 2)
        return (round(card_w / 2 - cx * z, 1), round(card_h / 2 - cy * z, 1))

    # --- reflector: el primer objetivo fija el tamaño base del elemento ---
    spots = spec.get("spots") or []
    sw, sh = (spots[0]["w"], spots[0]["h"]) if spots else (10, 10)

    cues = "".join(
        f'\n            <div class="cue" id="{spec["id"]}-cue{i}">{s["label"]}</div>'
        for i, s in enumerate(spots) if s.get("label")
    )
    cue_block = f'\n          <div class="cue-list">{cues}\n          </div>' if cues else ""

    spot_html = (
        f'\n            <div class="spot" id="{spec["id"]}-spot" '
        f'style="width: {sw}px; height: {sh}px"></div>' if spots else ""
    )

    # ---------- script de animación ----------
    js = []
    js.append('          const tl = gsap.timeline({ paused: true });')
    js.append(f'          tl.fromTo("#{spec["id"]}-mesh", {{ y: 0 }}, {{ y: 40, duration: {spec["dur"]}, ease: "none" }}, 0);')
    js.append(f'          tl.fromTo("#{spec["id"]}-glow", {{ scale: 0.94, opacity: 0.78 }}, '
              f'{{ scale: 1.06, opacity: 1, duration: {round(spec["dur"] / 2, 2)}, ease: "sine.inOut", yoyo: true, repeat: 1 }}, 0);')
    js.append(f'          tl.fromTo("#{spec["id"]}-topbar", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.6, ease: "power3.out" }}, 0);')
    js.append(f'          tl.fromTo("#{spec["id"]}-divider", {{ scaleY: 0 }}, {{ scaleY: 1, duration: 0.6, ease: "power2.out" }}, 0.2);')
    js.append('')
    js.append('          /* panel izquierdo — waterfall-entry */')
    js.append(f'          tl.fromTo("#{spec["id"]}-step", {{ autoAlpha: 0, x: -34 }}, {{ autoAlpha: 1, x: 0, duration: 0.45, ease: "power2.out" }}, 0.15);')
    js.append(f'          tl.fromTo("#{spec["id"]}-title", {{ autoAlpha: 0, y: 44 }}, {{ autoAlpha: 1, y: 0, duration: 0.6, ease: "power4.out" }}, 0.3);')
    js.append(f'          tl.fromTo("#{spec["id"]}-rule", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.5, ease: "power3.inOut" }}, 0.62);')
    js.append(f'          tl.fromTo("#{spec["id"]}-sub", {{ autoAlpha: 0, y: 24 }}, {{ autoAlpha: 1, y: 0, duration: 0.5, ease: "power2.out" }}, 0.75);')
    js.append('')
    js.append('          /* ficha — spring-pop-entrance */')
    js.append(f'          tl.fromTo("#{spec["id"]}-card", {{ autoAlpha: 0, scale: 0.955, y: 26 }}, '
              f'{{ autoAlpha: 1, scale: 1, y: 0, duration: 0.72, ease: "back.out(1.4)" }}, 0.5);')

    # cámara
    c0 = cams[0]
    x0, y0 = cam_xy(c0)
    js.append('')
    js.append('          /* cámara — coordinate-target-zoom */')
    js.append(f'          tl.set("#{spec["id"]}-zoom", {{ scale: {c0["scale"]}, x: {x0}, y: {y0} }}, 0);')
    for c in cams[1:]:
        x, y = cam_xy(c)
        js.append(f'          tl.to("#{spec["id"]}-zoom", {{ scale: {c["scale"]}, x: {x}, y: {y}, '
                  f'duration: {c.get("d", 1.2)}, ease: "power2.inOut" }}, {c["at"]});')

    # reflector
    if spots:
        s0 = spots[0]
        js.append('')
        js.append('          /* reflector — un solo foco que recorre la pantalla */')
        js.append(f'          tl.set("#{spec["id"]}-spot", {{ x: {s0["x"]}, y: {s0["y"]}, scaleX: 1, scaleY: 1 }}, 0);')
        js.append(f'          tl.fromTo("#{spec["id"]}-spot", {{ autoAlpha: 0 }}, '
                  f'{{ autoAlpha: 1, duration: 0.5, ease: "power2.out" }}, {s0["at"]});')
        for i, s in enumerate(spots[1:], start=1):
            js.append(f'          tl.to("#{spec["id"]}-spot", {{ x: {s["x"]}, y: {s["y"]}, '
                      f'scaleX: {round(s["w"] / sw, 4)}, scaleY: {round(s["h"] / sh, 4)}, '
                      f'duration: 0.55, ease: "power2.inOut" }}, {s["at"]});')
        last_end = spec["dur"] - 0.5
        js.append(f'          tl.to("#{spec["id"]}-spot", {{ autoAlpha: 0, duration: 0.45, ease: "power2.in" }}, {round(last_end, 2)});')

        # pistas del panel: la activa a plena opacidad, las demás atenuadas
        for i, s in enumerate(spots):
            if not s.get("label"):
                continue
            js.append(f'          tl.fromTo("#{spec["id"]}-cue{i}", {{ autoAlpha: 0, x: -20 }}, '
                      f'{{ autoAlpha: 0.32, x: 0, duration: 0.4, ease: "power2.out" }}, {max(0.9, s["at"] - 0.9)});')
            js.append(f'          tl.to("#{spec["id"]}-cue{i}", {{ autoAlpha: 1, duration: 0.3, ease: "power2.out" }}, {s["at"]});')
            nxt = spots[i + 1]["at"] if i + 1 < len(spots) else None
            if nxt is not None:
                js.append(f'          tl.to("#{spec["id"]}-cue{i}", {{ autoAlpha: 0.32, duration: 0.3, ease: "power2.in" }}, {nxt});')

    js.extend(spec.get("extra_js", []))
    js.append('')
    js.append(f'          window.__timelines["{spec["id"]}"] = tl;')

    return f"""<!doctype html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
  </head>
  <body>
    <template>
      <style>{CSS}{spec.get("extra_css", "")}      </style>

      <div
        id="root"
        data-composition-id="{spec['id']}"
        data-width="1920"
        data-height="1080"
        data-duration="{spec['dur']}"
      >
        <div class="bg-mesh" id="{spec['id']}-mesh"></div>
        <div class="bg-glow" id="{spec['id']}-glow"></div>
        <div class="topbar" id="{spec['id']}-topbar"></div>

        <div class="panel">
          <div class="step" id="{spec['id']}-step">{spec['step']}</div>
          <div class="ptitle" id="{spec['id']}-title">{spec['title']}</div>
          <div class="prule" id="{spec['id']}-rule"></div>
          <div class="psub" id="{spec['id']}-sub">{spec['sub']}</div>{cue_block}
        </div>

        <div class="divider" id="{spec['id']}-divider"></div>

        <div class="stage">
          <div class="card" id="{spec['id']}-card" style="width: {card_w}px; height: {card_h}px">
            <div class="zoom" id="{spec['id']}-zoom" style="width: {iw}px; height: {ih}px">
              <img src="{spec['img']}" width="{iw}" height="{ih}" alt="" />{spot_html}
            </div>{spec.get("extra_html", "")}
          </div>
        </div>
      </div>

      <script>
        (function () {{
{chr(10).join(js)}
        }})();
      </script>
    </template>
  </body>
</html>
"""


def spot(x, y, w, h, at, label=None):
    return {"x": x, "y": y, "w": w, "h": h, "at": at, "label": label}


SCENES = [
    # ---------- Escena 2 — login ----------
    dict(
        id="esc02-login", dur=10, step="Paso 02",
        title="Ingresa tu usuario y contraseña",
        sub="La plataforma pedirá tus credenciales institucionales.",
        img="assets/capturas/escena02_login.png", img_size=(657, 683), base=1.15,
        spots=[
            spot(120, 196, 396, 62, 2.6, "ID de Usuario"),
            spot(120, 258, 396, 62, 4.6, "Contraseña"),
            spot(120, 358, 396, 62, 6.6, "Conectar"),
        ],
    ),
    # ---------- Escena 3 — Overview ----------
    dict(
        id="esc03-overview", dur=16, step="Paso 03",
        title="Overview: los dashboards por área temática",
        sub="Todos los reportes disponibles, agrupados por tema.",
        img="assets/capturas/escena03_overview_dashboards.png", img_size=(1417, 961), base=0.79,
        camera=[
            {"at": 0, "scale": 0.79, "cx": 708, "cy": 480},
            {"at": 5.4, "scale": 1.52, "cx": 151, "cy": 392, "d": 1.6},
            {"at": 10.4, "scale": 1.52, "cx": 151, "cy": 756, "d": 1.4},
        ],
        spots=[
            spot(14, 190, 278, 400, 6.6, "1) Portafolio y Contrapartes"),
            spot(14, 596, 278, 330, 11.2, "2) Indicadores de Desempeño"),
        ],
    ),
    # ---------- Escena 5 — panel de filtros ----------
    dict(
        id="esc05-filtros", dur=25, step="Paso 05",
        title="El panel de filtros",
        sub="A la izquierda del reporte defines qué quieres consultar.",
        img="assets/capturas/escena05_panel_filtros.png", img_size=(1133, 740), base=1.06,
        camera=[
            {"at": 0, "scale": 1.06, "cx": 566, "cy": 370},
            {"at": 3.2, "scale": 1.42, "cx": 183, "cy": 332, "d": 1.5},
        ],
        spots=[
            spot(46, 158, 250, 82, 5.0, "Frecuencia"),
            spot(40, 244, 300, 44, 8.2, "Fecha de consulta"),
            spot(40, 294, 260, 40, 11.0, "Moneda"),
            spot(40, 344, 260, 40, 13.0, "Instrumento"),
            spot(40, 394, 260, 40, 15.0, "Tipo de fecha"),
            spot(40, 442, 260, 40, 17.4, "Mostrar por"),
            spot(154, 486, 80, 30, 20.2, "Aplicar"),
        ],
    ),
    # ---------- Escena 6 — opción exportar ----------
    dict(
        id="esc06-exportar", dur=8, step="Paso 06",
        title="Dónde está la opción de exportar",
        sub="Al pie del reporte aparece el enlace Exportar.",
        img="assets/capturas/escena06_opcion_exportar.png", img_size=(292, 92), base=3.5,
        spots=[spot(145, 33, 89, 43, 2.8, "Exportar")],
    ),
    # ---------- Escena 7 — con formato ----------
    dict(
        id="esc07-con-formato", dur=13, step="Paso 07",
        title="Opción «Con formato»",
        sub="Exporta el reporte tal como se ve en pantalla.",
        img="assets/capturas/escena07_exportar_con_formato.png", img_size=(304, 171), base=3.6,
        spots=[
            spot(46, 113, 131, 33, 1.8, "Con formato"),
            spot(168, 28, 132, 24, 5.4, "PDF"),
            spot(168, 52, 132, 24, 6.9, "Excel"),
            spot(168, 76, 132, 24, 8.4, "Powerpoint"),
            spot(168, 100, 132, 24, 9.9, "Archivo Web"),
        ],
    ),
    # ---------- Escena 8 — datos ----------
    dict(
        id="esc08-datos", dur=10, step="Paso 08",
        title="Opción «Datos»",
        sub="Exporta los valores en crudo, para trabajarlos aparte.",
        img="assets/capturas/escena08_exportar_datos.png", img_size=(378, 131), base=2.9,
        spots=[
            spot(5, 85, 141, 38, 1.6, "Datos"),
            spot(152, 6, 220, 24, 4.0, "Excel"),
            spot(152, 32, 220, 24, 5.2, "CSV"),
            spot(152, 58, 220, 24, 6.4, "Delimitado por tabulaciones"),
            spot(152, 82, 220, 24, 7.8, "XML"),
        ],
    ),
    # ---------- Escena 9 — esquina superior derecha ----------
    dict(
        id="esc09-superior-derecha", dur=12, step="Paso 09",
        title="La otra ruta de exportación",
        sub="Desde el menú de la esquina superior derecha del reporte.",
        img="assets/capturas/escena09_exportar_excel_pagina.png", img_size=(605, 372), base=1.6,
        spots=[
            spot(516, 56, 50, 39, 2.2, "Menú superior derecho"),
            spot(297, 138, 259, 33, 5.6, "Exportar a Excel"),
            spot(47, 140, 247, 33, 8.4, "Exportar Página Actual"),
        ],
    ),
    # ---------- Escena 10 — regresar ----------
    dict(
        id="esc10-regresar", dur=11, step="Paso 10",
        title="Cómo volver al inicio",
        sub="Panel de Control te devuelve al listado; Overview es la portada.",
        img="assets/capturas/escena10_regresar_overview.png", img_size=(542, 495), base=1.55,
        spots=[
            spot(0, 0, 149, 44, 3.0, "Panel de Control"),
            spot(24, 140, 151, 28, 6.4, "00.- Overview"),
        ],
    ),
]

def main():
    ap = argparse.ArgumentParser(description="Genera las escenas de contenido.")
    ap.add_argument("--voz", help="carpeta bajo assets/audio/ a la que calzar los tiempos")
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    nombres = {
        "esc02-login": "esc02-login.html",
        "esc03-overview": "esc03-overview.html",
        "esc05-filtros": "esc05-filtros.html",
        "esc06-exportar": "esc06-exportar.html",
        "esc07-con-formato": "esc07-con-formato.html",
        "esc08-datos": "esc08-datos.html",
        "esc09-superior-derecha": "esc09-superior-derecha.html",
        "esc10-regresar": "esc10-regresar.html",
    }

    print(f"{'archivo':<34}{'dur':>7}{'focos':>7}{'escala':>9}")
    for spec in SCENES:
        spec, k = reescalar(spec, a.voz)
        path = os.path.join(OUT, nombres[spec["id"]])
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(scene(spec))
        marca = f"×{k:.2f}" if k != 1.0 else "—"
        print(f"{nombres[spec['id']]:<34}{spec['dur']:>6}s{len(spec.get('spots') or []):>7}{marca:>9}")

    if a.voz:
        print(f"\nCoreografía calzada a la voz «{a.voz}».")
    else:
        print("\nDuraciones autorales. Usa --voz <nombre> para calzarlas a una narración.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
