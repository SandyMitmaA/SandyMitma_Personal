#!/usr/bin/env python3
"""Limpia y nivela una narración antes de montarla en el video.

Uso:
    python3 tools/pulir-audio.py entrada.mp4 -o salida.wav
    python3 tools/pulir-audio.py entrada.mp4 -o salida.wav --sin-eq

La cadena es deliberadamente conservadora: una locución de capacitación se
arruina antes por exceso de proceso que por defecto. Cada paso responde a algo
medido en el archivo, no a una receta genérica:

  1. Paso alto a 80 Hz — la voz femenina tiene su fundamental sobre 180 Hz, así
     que por debajo de 80 solo hay retumbe y continua. No cuesta nada quitarlo.
  2. −2 dB en 300 Hz — la banda 250-500 estaba +5.6 dB sobre el medio, que es
     el clásico exceso «embarrado» que emborrona las consonantes.
  3. +2.5 dB en 2.8 kHz — donde viven las consonantes. En un instructivo el
     espectador necesita distinguir «Portafolio» de «Portafolios», y esa
     diferencia se juega aquí.
  4. Expansor descendente — el ruido de fondo medía −55 a −61 dB RMS en las
     pausas. No se silencia del todo (eso suena a bombeo): se baja 30 dB, que
     lo deja inaudible conservando la naturalidad de las colas de palabra.
  5. Compresión suave 2:1 — solo para domar los picos, no para aplastar.
  6. Normalización a −16 LUFS con techo de pico real en −1.5 dBTP, en dos
     pasadas para que la medida sea exacta. −16 LUFS es el estándar de video
     en web; el original venía a −20.5, casi 5 dB por debajo.
"""
import argparse
import json
import os
import re
import subprocess
import sys

OBJETIVO_LUFS = -16.0
TECHO_TP = -1.5
LRA_OBJETIVO = 7.0


def ffmpeg(args, **kw):
    return subprocess.run(["ffmpeg", *args], capture_output=True, text=True, **kw)


def cadena_base(con_eq=True):
    pasos = ["highpass=f=80"]
    if con_eq:
        pasos += [
            "equalizer=f=300:t=q:w=1.2:g=-2",      # quita el barro
            "equalizer=f=2800:t=q:w=1.0:g=2.5",    # levanta las consonantes
        ]
    pasos += [
        # umbral -45 dB, reducción de 30 dB: expansor, no compuerta brusca
        "agate=threshold=0.0056:ratio=2:attack=8:release=180:range=0.032",
        "acompressor=threshold=-18dB:ratio=2:attack=15:release=250:makeup=1",
    ]
    return ",".join(pasos)


def medir(path):
    """Sonoridad y pico reales, para poder comparar antes y después."""
    err = ffmpeg(["-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    def cap(patron):
        m = re.findall(patron, err)
        return float(m[-1]) if m else None
    return {
        "lufs": cap(r"I:\s+(-?[\d.]+) LUFS"),
        "lra": cap(r"LRA:\s+(-?[\d.]+) LU"),
        "tp": cap(r"Peak:\s+(-?[\d.]+) dBFS"),
    }


def main():
    ap = argparse.ArgumentParser(description="Limpia y nivela una narración.")
    ap.add_argument("entrada")
    ap.add_argument("-o", "--salida", required=True)
    ap.add_argument("--sin-eq", action="store_true",
                    help="omite el ecualizador; solo limpia y nivela")
    ap.add_argument("--lufs", type=float, default=OBJETIVO_LUFS)
    a = ap.parse_args()

    if not os.path.isfile(a.entrada):
        print(f"No existe {a.entrada}")
        return 1

    antes = medir(a.entrada)
    print(f"Entrada:  {antes['lufs']} LUFS · LRA {antes['lra']} LU · pico real {antes['tp']} dBFS")

    base = cadena_base(con_eq=not a.sin_eq)

    # --- primera pasada: medir lo que quedará después del proceso ---
    print("Analizando…")
    med = ffmpeg([
        "-i", a.entrada, "-af",
        f"{base},loudnorm=I={a.lufs}:TP={TECHO_TP}:LRA={LRA_OBJETIVO}:print_format=json",
        "-f", "null", "-",
    ]).stderr
    bloque = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", med, re.S)
    if not bloque:
        print("No pude medir la primera pasada.")
        return 1
    m = json.loads(bloque.group(0))

    # --- segunda pasada: aplicar con la medida exacta ---
    print("Procesando…")
    norm = (f"loudnorm=I={a.lufs}:TP={TECHO_TP}:LRA={LRA_OBJETIVO}"
            f":measured_I={m['input_i']}:measured_TP={m['input_tp']}"
            f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
            f":offset={m['target_offset']}:linear=true")
    res = ffmpeg(["-y", "-i", a.entrada, "-af", f"{base},{norm}",
                  "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", a.salida])
    if res.returncode != 0:
        print(res.stderr.strip().splitlines()[-1])
        return 1

    despues = medir(a.salida)
    print(f"\nSalida:   {despues['lufs']} LUFS · LRA {despues['lra']} LU · pico real {despues['tp']} dBFS")
    print(f"Ganancia aplicada: {despues['lufs'] - antes['lufs']:+.1f} dB")
    print(f"Escrito: {a.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
