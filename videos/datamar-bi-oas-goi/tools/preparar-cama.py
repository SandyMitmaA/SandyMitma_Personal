#!/usr/bin/env python3
"""Adapta una pista de música para usarla como cama bajo la locución.

Uso:
    python3 tools/preparar-cama.py "narracion-ssml/So Happy (Full Track).wav"
    python3 tools/preparar-cama.py pista.wav --nivel -30 --corte 5000

Una pista masterizada no sirve tal cual de fondo: viene fuerte (las de catálogo
rondan los -10 LUFS, por encima de una locución a -16), suele durar menos que el
video, y ocupa de lleno la banda de 1 a 3 kHz donde se juega la inteligibilidad
de las consonantes.

Esta herramienta hace tres cosas y deja la cuarta al framework:

  1. **Longitud.** Si la pista es más corta que el video, la encadena consigo
     misma con un crossfade de varios segundos. La costura queda dentro de un
     fundido, y a nivel de cama es prácticamente inaudible.
  2. **Tono.** Un pasabajos suave por encima de la voz: la música conserva su
     cuerpo y su brillo, pero deja de disputar la banda de las consonantes.
  3. **Nivel.** Normaliza a un nivel de cama, muy por debajo de la voz, con
     entrada y salida en fundido.
  4. El equilibrio dinámico —cuánto se aparta la música en cada frase— NO se
     hace aquí. Lo escribe el voiceover carve del framework, que además abre
     hueco por bandas en lugar de bajar el volumen entero.
"""
import argparse
import os
import re
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO = os.path.join(RAIZ, "assets", "audio", "musica", "cama.wav")
CRUCE = 6.0          # segundos de crossfade en la costura del bucle
ENTRADA = 3.0
SALIDA = 5.0


def ffmpeg(args):
    return subprocess.run(["ffmpeg", *args], capture_output=True, text=True)


def duracion(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True).stdout.strip()
    return float(out)


def lufs(path):
    err = ffmpeg(["-i", path, "-af", "ebur128", "-f", "null", "-"]).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    return float(m[-1]) if m else None


def duracion_composicion():
    with open(os.path.join(RAIZ, "index.html"), encoding="utf-8") as fh:
        cab = fh.read(4000)
    m = re.search(r'data-composition-id="main".*?data-duration="([\d.]+)"', cab, re.S)
    return float(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser(description="Prepara una pista como cama musical.")
    ap.add_argument("pista")
    ap.add_argument("-o", "--salida", default=DESTINO)
    ap.add_argument("--nivel", type=float, default=-30.0,
                    help="LUFS de la cama; -30 es discreto bajo una voz a -16")
    ap.add_argument("--corte", type=float, default=5000.0,
                    help="Hz del pasabajos; más bajo = más se aparta de la voz")
    ap.add_argument("--duracion", type=float, help="segundos; por defecto los del video")
    a = ap.parse_args()

    if not os.path.isfile(a.pista):
        print(f"No existe {a.pista}")
        return 1

    objetivo = (a.duracion or duracion_composicion() or 180.0) + 2.0
    fuente = duracion(a.pista)
    print(f"Pista:  {os.path.basename(a.pista)}  ·  {fuente:.1f}s  ·  {lufs(a.pista)} LUFS")
    print(f"Video:  {objetivo - 2:.1f}s  →  cama de {objetivo:.1f}s")

    os.makedirs(os.path.dirname(os.path.abspath(a.salida)) or ".", exist_ok=True)
    tmp = os.path.join(os.path.dirname(os.path.abspath(a.salida)), "_cama_larga.wav")

    if fuente >= objetivo:
        print("La pista alcanza: se recorta, sin bucle.")
        r = ffmpeg(["-y", "-i", a.pista, "-t", f"{objetivo:.3f}",
                    "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", tmp])
    else:
        # cada vuelta aporta (fuente - CRUCE) segundos nuevos
        vueltas = 1
        while fuente + (vueltas - 1) * (fuente - CRUCE) < objetivo:
            vueltas += 1
        print(f"La pista se queda {objetivo - fuente:.1f}s corta: "
              f"{vueltas} pasadas encadenadas con crossfade de {CRUCE:.0f}s.")

        entradas, filtros, etiqueta = [], [], None
        for i in range(vueltas):
            entradas += ["-i", a.pista]
        for i in range(vueltas):
            filtros.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo[p{i}]")
        etiqueta = "p0"
        for i in range(1, vueltas):
            nueva = f"x{i}"
            filtros.append(f"[{etiqueta}][p{i}]acrossfade=d={CRUCE}:c1=tri:c2=tri[{nueva}]")
            etiqueta = nueva
        filtro = ";".join(filtros)
        r = ffmpeg(["-y", *entradas, "-filter_complex", filtro, "-map", f"[{etiqueta}]",
                    "-t", f"{objetivo:.3f}", "-c:a", "pcm_s16le", tmp])

    if r.returncode != 0:
        print(r.stderr.strip().splitlines()[-1])
        return 1

    # tono, fundidos y nivel de cama
    ent, sal = ENTRADA, SALIDA
    cadena = (f"lowpass=f={a.corte:.0f}:poles=2,"
              f"afade=t=in:st=0:d={ent},"
              f"afade=t=out:st={objetivo - sal:.3f}:d={sal},"
              f"loudnorm=I={a.nivel}:TP=-6:LRA=9")
    r = ffmpeg(["-y", "-i", tmp, "-af", cadena,
                "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", a.salida])
    if r.returncode != 0:
        print(r.stderr.strip().splitlines()[-1])
        return 1
    os.remove(tmp)

    print(f"\nCama:   {duracion(a.salida):.1f}s  ·  {lufs(a.salida)} LUFS  ·  "
          f"pasabajos {a.corte:.0f} Hz")
    print(f"Escrita en {os.path.relpath(a.salida, RAIZ)}")
    print("\nAhora vuelve a aplicar el carve para que se aparte de la voz:")
    print("    node <skills>/hyperframes-audio/scripts/carve.mjs --comp index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
