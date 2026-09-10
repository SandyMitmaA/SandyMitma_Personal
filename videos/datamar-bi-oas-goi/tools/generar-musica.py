#!/usr/bin/env python3
"""Sintetiza la cama musical del video.

Uso:
    python3 tools/generar-musica.py -o assets/audio/musica/cama.wav
    python3 tools/generar-musica.py -o cama.wav --duracion 180

Se sintetiza aquí porque este entorno no alcanza ningún catálogo de música: el
CLI de HeyGen no tiene sesión y HuggingFace, freesound y archive.org responden
403 a través del proxy. Es una cama propia, sin licencia que gestionar, pensada
para sustituirse por una pista real si el área prefiere otra.

Criterios, todos al servicio de no estorbar a la voz:

  · Sin percusión ni transitorios. Un ataque marcado compite con las consonantes
    y obliga al espectador a re-enfocar la atención cada vez.
  · Filtro pasabajos a 3.2 kHz. La voz ya lleva un realce en 2.8 kHz para que las
    consonantes se distingan; la música se retira de esa banda por completo en
    vez de pelearla.
  · Acordes de once segundos con ataques y caídas de varios segundos, encabalgados.
    Nada cambia lo bastante rápido como para llamar la atención.
  · Ciclo de ocho acordes, no de cuatro: a lo largo de tres minutos un ciclo corto
    se vuelve reconocible y cansa.
  · Nivel de salida muy por debajo de la locución. El ajuste fino lo hace después
    el voiceover carve del framework, que además abre hueco por bandas.
"""
import argparse
import math
import os
import re
import sys
import wave

import numpy as np

SR = 48000

# Progresión en re mayor: serena y sin tensión sin resolver.
# El sexto acorde (fa# menor) es la única sombra del ciclo — evita que dos
# minutos y medio de acordes mayores se vuelvan almibarados.
PROGRESION = [
    [50, 54, 57, 61],   # Re maj7
    [47, 50, 54, 57],   # Si m7
    [43, 47, 50, 54],   # Sol maj7
    [45, 49, 52, 57],   # La
    [50, 54, 57, 61],   # Re maj7
    [42, 45, 49, 52],   # Fa# m7
    [43, 47, 50, 54],   # Sol maj7
    [45, 49, 52, 56],   # La 7
]
DUR_ACORDE = 11.0
CORTE_AGUDOS = 3200.0


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12.0)


def pad(notas, n, sr=SR):
    """Un acorde sostenido: parciales suaves y dos osciladores desafinados."""
    t = np.arange(n) / sr
    out = np.zeros(n)
    for i, m in enumerate(notas):
        f = hz(m)
        # los parciales caen rápido: un pad brillante se vuelve un órgano
        for p, amp in ((1, 1.0), (2, 0.26), (3, 0.10), (4, 0.045)):
            # dos copias con desafine mínimo dan cuerpo sin sonar a coro
            for det in (-0.12, 0.12):
                fase = (i * 1.7 + p * 0.4 + det)
                out += amp * np.sin(2 * np.pi * (f * p + det) * t + fase)
        # la fundamental una octava abajo, apenas presente, da fondo
        out += 0.35 * np.sin(2 * np.pi * (f / 2) * t + i)
    return out / (len(notas) * 2.6)


def envolvente(n, ataque, caida, sr=SR):
    e = np.ones(n)
    # el último acorde se corta al final de la pieza: los tramos de ataque y
    # caída no pueden sumar más que el bloque disponible
    na, nc = int(ataque * sr), int(caida * sr)
    if na + nc > n:
        k = n / (na + nc)
        na, nc = int(na * k), int(nc * k)
    if na:
        e[:na] = np.sin(np.linspace(0, np.pi / 2, na)) ** 2
    if nc:
        e[-nc:] = np.sin(np.linspace(np.pi / 2, 0, nc)) ** 2
    return e


def campanita(f, n, sr=SR):
    """Una nota corta y clara, con caída exponencial. Marca el paso sin percutir."""
    t = np.arange(n) / sr
    dec = np.exp(-t * 1.6)
    s = (np.sin(2 * np.pi * f * t)
         + 0.4 * np.sin(2 * np.pi * f * 2 * t)
         + 0.15 * np.sin(2 * np.pi * f * 3.01 * t))
    ataque = np.minimum(1.0, t / 0.02)
    return s * dec * ataque / 1.6


def pasabajos(x, corte, sr=SR):
    """Pasabajos por FFT con caída suave — sin resonancia ni cambio de fase audible."""
    N = 1 << (len(x) - 1).bit_length()
    X = np.fft.rfft(x, N)
    f = np.fft.rfftfreq(N, 1 / sr)
    # transición de una octava: brusco delataría el filtro
    H = 1 / (1 + (f / corte) ** 4)
    return np.fft.irfft(X * H, N)[:len(x)]


def espacio(x, sr=SR):
    """Tres retardos cortos: sensación de sala sin la cola de una reverb."""
    out = x.copy()
    for retardo, gan in ((0.037, 0.30), (0.061, 0.22), (0.089, 0.16)):
        d = int(retardo * sr)
        eco = np.zeros_like(x)
        eco[d:] = x[:-d] * gan
        out += eco
    return out / 1.55


def duracion_de_index(ruta):
    with open(ruta, encoding="utf-8") as fh:
        cab = fh.read(4000)
    m = re.search(r'data-composition-id="main".*?data-duration="([\d.]+)"', cab, re.S)
    return float(m.group(1)) if m else None


def main():
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description="Sintetiza la cama musical.")
    ap.add_argument("-o", "--salida", required=True)
    ap.add_argument("--duracion", type=float,
                    help="segundos; por defecto los del index.html")
    ap.add_argument("--nivel", type=float, default=-30.0,
                    help="LUFS aproximados de salida (el carve afina después)")
    a = ap.parse_args()

    dur = a.duracion or duracion_de_index(os.path.join(raiz, "index.html")) or 180.0
    dur += 2.0                      # cola para el fundido final
    n = int(dur * SR)
    mezcla = np.zeros(n)

    # --- acordes encabalgados ---
    i, t0 = 0, 0.0
    while t0 < dur:
        notas = PROGRESION[i % len(PROGRESION)]
        largo = DUR_ACORDE + 4.0     # se solapa con el siguiente
        nn = min(int(largo * SR), n - int(t0 * SR))
        if nn <= 0:
            break
        bloque = pad(notas, nn) * envolvente(nn, 3.2, 4.2)
        s = int(t0 * SR)
        mezcla[s:s + nn] += bloque
        i += 1
        t0 += DUR_ACORDE

    # --- campanitas: una por acorde, sobre la tercera o la quinta ---
    for k in range(i):
        notas = PROGRESION[k % len(PROGRESION)]
        f = hz(notas[(k % 2) + 1] + 12)
        s = int((k * DUR_ACORDE + 1.6) * SR)
        nn = min(int(3.0 * SR), n - s)
        if nn > 0:
            mezcla[s:s + nn] += campanita(f, nn) * 0.16

    mezcla = espacio(pasabajos(mezcla, CORTE_AGUDOS))

    # --- entrada y salida ---
    ent, sal = int(4.0 * SR), int(6.0 * SR)
    mezcla[:ent] *= np.linspace(0, 1, ent) ** 2
    mezcla[-sal:] *= np.linspace(1, 0, sal) ** 2

    # --- nivel ---
    pico = np.abs(mezcla).max()
    if pico > 0:
        mezcla /= pico
    rms = np.sqrt((mezcla ** 2).mean())
    objetivo = 10 ** (a.nivel / 20)
    mezcla *= min(objetivo / rms, 0.95 / np.abs(mezcla).max())

    os.makedirs(os.path.dirname(os.path.abspath(a.salida)) or ".", exist_ok=True)
    with wave.open(a.salida, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(mezcla, -1, 1) * 32767).astype(np.int16).tobytes())

    rms_db = 20 * math.log10(np.sqrt((mezcla ** 2).mean()))
    pico_db = 20 * math.log10(np.abs(mezcla).max())
    print(f"{a.salida}")
    print(f"  {dur:.1f}s · {i} acordes · ciclo de {len(PROGRESION)}")
    print(f"  RMS {rms_db:.1f} dB · pico {pico_db:.1f} dB · pasabajos {CORTE_AGUDOS:.0f} Hz")
    return 0


if __name__ == "__main__":
    sys.exit(main())
