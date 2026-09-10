#!/usr/bin/env python3
"""Ensambla el timeline maestro y lo sincroniza con la narración real.

Uso:
    python3 tools/sincronizar.py

Si existen los archivos `assets/audio/esc00.wav` … `esc11.wav`, mide su duración
real y ajusta cada escena a la voz. Si no existen, usa la estimación por conteo
de palabras (148 palabras/min) para poder trabajar antes de tener el audio.

En ambos casos reescribe `index.html` y `subtitulos.json`.
"""
import contextlib
import json
import os
import subprocess
import sys
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_DIR = os.path.join(ROOT, "assets", "audio")

LEAD = 0.6        # silencio antes de que entre la voz en cada escena
TAIL = 1.2        # aire después de la última palabra, para que la escena respire
XFADE = 0.5       # encadenado entre escenas
WPM = 148.0       # ritmo pausado de capacitación en español
MIN_DUR = 4.0     # ninguna escena baja de esto aunque la frase sea muy corta

FFMPEG = "/opt/pw-browsers/ffmpeg-1011/ffmpeg-linux"

# Duración para la que está coreografiado el interior de cada escena.
# Es un piso: acortar por debajo truncaría resaltados y movimientos de cámara.
COREOGRAFIA = {
    "esc00": 9,
    "esc01": 7,
    "esc02": 10,
    "esc03": 16,
    "esc04": 12,
    "esc05": 25,
    "esc06": 8,
    "esc07": 13,
    "esc08": 10,
    "esc09": 12,
    "esc10": 11,
    "esc11": 15,
}

# (slug, id de composición, archivo, subtítulos)
SCENES = [
    ("esc00", "esc00-portada", "compositions/esc00-portada.html", [
        "Bienvenidos a esta capacitación sobre el acceso al Sistema Datamar BI – OAS,",
        "de la Gerencia de Operaciones Internacionales.",
    ]),
    ("esc01", "esc01-link", "compositions/esc01-link.html", [
        "Para acceder a la plataforma, debemos ingresar al siguiente link.",
    ]),
    ("esc02", "esc02-login", "compositions/esc02-login.html", [
        "En la ventana se mostrará la pantalla de login.",
        "Aquí deberás ingresar tus credenciales: usuario y contraseña.",
    ]),
    ("esc03", "esc03-overview", "compositions/esc03-overview.html", [
        "Esto nos dirigirá a la ventana principal, Overview,",
        "donde se muestran los diversos dashboards y reportes disponibles, agrupados por área temática.",
        "Por ejemplo: Portafolio y Contrapartes, o Indicadores de Desempeño, entre otros.",
    ]),
    ("esc04", "esc04-abrir-reporte", "compositions/esc04-abrir-reporte.html", [
        "Si se requiere consultar alguno de estos reportes, solo es necesario dar clic para acceder.",
        "Por ejemplo, el reporte de Portafolio vs Referencia.",
    ]),
    ("esc05", "esc05-filtros", "compositions/esc05-filtros.html", [
        "Aquí se mostrará el reporte.",
        "En la parte lateral izquierda encontramos un panel con los filtros disponibles:",
        "frecuencia, ya sea diaria, mensual o anual;",
        "fecha o rango de fecha; moneda; instrumento;",
        "metodología de consulta;",
        "y si se desea ver el reporte a nivel de tramo o moneda.",
        "Finalmente, se debe presionar Aplicar.",
    ]),
    ("esc06", "esc06-exportar", "compositions/esc06-exportar.html", [
        "Para exportar los resultados, en la parte inferior se mostrará la opción de exportar.",
    ]),
    ("esc07", "esc07-con-formato", "compositions/esc07-con-formato.html", [
        "Al hacer clic se mostrarán los distintos formatos disponibles.",
        "Con la opción Con Formato, se puede exportar en PDF, Excel, PowerPoint o archivo web.",
    ]),
    ("esc08", "esc08-datos", "compositions/esc08-datos.html", [
        "Con la otra opción, Datos, se podrá exportar en formatos Excel, CSV,",
        "delimitado por tabulaciones, y XML.",
    ]),
    ("esc09", "esc09-superior-derecha", "compositions/esc09-superior-derecha.html", [
        "Otra manera de exportar es dando clic en la parte superior derecha,",
        "en Exportar a Excel, o en Exportar Página Actual.",
    ]),
    ("esc10", "esc10-regresar", "compositions/esc10-regresar.html", [
        "Si se requiere regresar a la página principal,",
        "nos dirigimos a Panel de Control y hacemos clic en Overview.",
    ]),
    ("esc11", "esc11-cierre", "compositions/esc11-cierre.html", [
        "De esta manera podrás interactuar con los diversos reportes disponibles que existen en el OAS.",
        "Con esto, ya conoces cómo acceder, navegar, filtrar y exportar reportes en Datamar BI OAS.",
    ]),
]


def find_audio(slug):
    for ext in (".wav", ".mp3", ".m4a", ".aac", ".ogg"):
        p = os.path.join(AUDIO_DIR, slug + ext)
        if os.path.isfile(p):
            return p
    return None


def audio_duration(path):
    """Duración en segundos. WAV se lee nativo; el resto vía ffmpeg."""
    if path.lower().endswith(".wav"):
        with contextlib.suppress(Exception):
            with wave.open(path, "rb") as w:
                return w.getnframes() / float(w.getframerate())
    if os.path.isfile(FFMPEG):
        try:
            out = subprocess.run(
                [FFMPEG, "-i", path, "-f", "null", "-"],
                capture_output=True, text=True, timeout=120,
            ).stderr
            for line in reversed(out.splitlines()):
                if "time=" in line:
                    stamp = line.split("time=")[1].split()[0]
                    hh, mm, ss = stamp.split(":")
                    return int(hh) * 3600 + int(mm) * 60 + float(ss)
        except Exception:
            pass
    raise RuntimeError(f"No se pudo medir la duración de {path}")


def build():
    tracks, have_audio = [], False
    for slug, cid, src, lines in SCENES:
        path = find_audio(slug)
        if path:
            have_audio = True
            speech = audio_duration(path)
            source = "audio"
        else:
            speech = sum(len(l.split()) for l in lines) / WPM * 60.0
            source = "estimación"
        # la escena dura lo que pida la voz, pero nunca menos que su coreografía
        dur = max(MIN_DUR, COREOGRAFIA.get(slug, 0), round(LEAD + speech + TAIL, 2))
        tracks.append(dict(slug=slug, cid=cid, src=src, lines=lines,
                           speech=speech, dur=dur, audio=path, source=source))

    starts, t = [], 0.0
    for tr in tracks:
        starts.append(round(t, 2))
        t += tr["dur"]
    total = round(t, 2)

    hosts, caps, auds, tweens, index = [], [], [], [], []
    for i, tr in enumerate(tracks):
        st, last = starts[i], i == len(tracks) - 1
        slot = tr["dur"] if last else round(tr["dur"] + XFADE, 2)

        hosts.append(
            f'      <div\n'
            f'        id="host-{tr["cid"]}"\n'
            f'        class="clip"\n'
            f'        data-composition-id="{tr["cid"]}"\n'
            f'        data-composition-src="{tr["src"]}"\n'
            f'        data-start="{st:g}"\n'
            f'        data-duration="{slot:g}"\n'
            f'        data-track-index="{(i % 2) + 1}"\n'
            f'        data-width="1920"\n'
            f'        data-height="1080"\n'
            f'      ></div>'
        )

        if i > 0:
            prev = tracks[i - 1]["cid"]
            tweens.append(f'      tl.fromTo("#host-{tr["cid"]}", {{ opacity: 0 }}, '
                          f'{{ opacity: 1, duration: {XFADE}, ease: "power1.inOut" }}, {st:g});')
            tweens.append(f'      tl.to("#host-{prev}", {{ opacity: 0, duration: {XFADE}, '
                          f'ease: "power1.inOut" }}, {st:g});')

        if tr["audio"]:
            rel = os.path.relpath(tr["audio"], ROOT).replace(os.sep, "/")
            auds.append(
                f'      <audio id="vo-{tr["slug"]}" src="{rel}" data-start="{round(st + LEAD, 2)}" '
                f'data-duration="{round(tr["speech"], 2)}" data-track-index="8" data-volume="1"></audio>'
            )

        words = [len(l.split()) for l in tr["lines"]]
        cur = st + LEAD
        for j, line in enumerate(tr["lines"]):
            d = words[j] / sum(words) * tr["speech"]
            caps.append(
                f'      <div id="cap-{i:02d}-{j}" class="clip caption" data-start="{round(cur, 2)}" '
                f'data-duration="{round(d, 2)}" data-track-index="9" data-layout-allow-caption-zone="true">'
                f'<span class="caption-inner">{line}</span></div>'
            )
            index.append({"escena": tr["cid"], "texto": line,
                          "inicio": round(cur, 2), "duracion": round(d, 2)})
            cur += d

    audio_block = ("\n\n      <!-- narración -->\n" + "\n".join(auds)) if auds else ""

    html = f"""<!doctype html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="assets/vendor/gsap.min.js"></script>
    <style>
      * {{
        margin: 0;
        padding: 0;
        box-sizing: border-box;
      }}
      html,
      body {{
        margin: 0;
        width: 1920px;
        height: 1080px;
        overflow: hidden;
        background: #f4f7fb;
      }}
      body {{
        font-family: "Montserrat", sans-serif;
      }}
      .clip {{
        position: absolute;
        inset: 0;
      }}
      .caption {{
        display: flex;
        align-items: flex-end;
        justify-content: center;
        padding-bottom: 42px;
      }}
      .caption-inner {{
        display: inline-block;
        max-width: 1480px;
        text-align: center;
        background: rgba(0, 34, 68, 0.9);
        color: #ffffff;
        font-size: 38px;
        font-weight: 700;
        line-height: 1.34;
        letter-spacing: -0.01em;
        padding: 20px 40px;
        border-bottom: 4px solid #29a1e6;
      }}
    </style>
  </head>
  <body>
    <div
      id="root"
      data-composition-id="main"
      data-start="0"
      data-duration="{total:g}"
      data-width="1920"
      data-height="1080"
      data-fps="30"
      style="position: relative; width: 1920px; height: 1080px; overflow: hidden; background: #f4f7fb"
    >
{chr(10).join(hosts)}

      <!-- subtítulos -->
{chr(10).join(caps)}{audio_block}
    </div>

    <script>
      const tl = gsap.timeline({{ paused: true }});

      /* encadenados entre escenas */
{chr(10).join(tweens)}

      tl.to({{}}, {{ duration: {total:g} }}, 0);
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(html)
    with open(os.path.join(ROOT, "subtitulos.json"), "w", encoding="utf-8") as fh:
        json.dump({"duracion_total": total, "subtitulos": index}, fh, ensure_ascii=False, indent=2)

    print(f"{'escena':<24}{'inicio':>9}{'voz':>8}{'escena':>9}   origen")
    for i, tr in enumerate(tracks):
        print(f"{tr['cid']:<24}{starts[i]:>9.1f}{tr['speech']:>8.1f}{tr['dur']:>9.1f}   {tr['source']}")
    m, s = divmod(total, 60)
    print(f"\nTotal: {total:.1f} s = {int(m)}:{int(s):02d}   ·   {len(index)} subtítulos")
    if have_audio:
        print("Narración real detectada: los tiempos siguen a la voz.")
    else:
        print(f"Sin audio en {os.path.relpath(AUDIO_DIR, ROOT)}/ — tiempos estimados.")
        print("Coloca esc00.wav … esc11.wav y vuelve a ejecutar para sincronizar.")
    return 0


if __name__ == "__main__":
    sys.exit(build())
