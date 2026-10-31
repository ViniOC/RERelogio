"""Prévia 240x240 da tela do RERelogio (pixel-art, tema muda com o horário).

Desenha exatamente o que o firmware vai compor: um fundo fixo por tema (céu,
cenário, molduras) e, por cima, textos em fonte pixel sem suavização.

Uso: python3 -I design/tela.py [saida.png]
     gera saida.png (folha 2x2 com os 4 temas, ampliada 2x)
"""
import math
import random
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W = H = 240
PASTA = Path(__file__).resolve().parent
F_PIXEL = PASTA / "fontes/Jersey10.ttf"

Y_HORIZONTE = 146
CARTAO_CLAUDE = (6, 150, 233, 203)
CARTAO_SEMANA = (6, 207, 233, 235)

# Cores comuns a todos os temas (cartões)
CARTAO = (6, 12, 34)
BORDA = (44, 92, 210)
TRILHO = (30, 40, 70)
TEXTO = (240, 244, 255)
TEXTO_2 = (130, 160, 225)
LARANJA = (242, 132, 58)
AMBAR = (246, 190, 60)
VERMELHO = (236, 72, 60)
AZUL = (40, 132, 255)
SOL = (255, 204, 64)
NUVEM = (236, 242, 255)

TEMAS = {
    "noite": {
        "ceu": [(6, 10, 32), (18, 30, 78)],
        "morros": [(30, 62, 150), (22, 44, 112)],
        "predio": (8, 12, 30), "janela": (246, 196, 66),
        "astro": (226, 234, 255),
        "texto": TEXTO, "texto_2": TEXTO_2,
    },
    "dia": {
        "ceu": [(46, 140, 240), (150, 214, 255)],
        "morros": [(110, 150, 200), (60, 150, 80)],
        "predio": (120, 160, 210), "janela": None,
        "astro": None,
        "texto": (8, 16, 40), "texto_2": (20, 50, 110),
    },
    "por_do_sol": {
        "ceu": [(92, 52, 140), (255, 120, 140), (255, 180, 110)],
        "morros": [(150, 70, 140), (100, 46, 110)],
        "predio": (48, 22, 70), "janela": (255, 190, 90),
        "astro": SOL,
        "texto": (20, 8, 30), "texto_2": (70, 20, 70),
    },
    "minimalista": {
        "ceu": [(0, 0, 0), (0, 0, 0)],
        "texto": TEXTO, "texto_2": TEXTO_2,
    },
}

DIAS = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]
MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN",
         "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]


def fonte(tam):
    """Jersey 10 fica nítida em múltiplos de 10 px."""
    return ImageFont.truetype(str(F_PIXEL), tam)


def cor_uso(p):
    if p > 85:
        return VERMELHO
    if p >= 60:
        return AMBAR
    return LARANJA


def degrade(cores, t):
    """Interpola numa lista de cores (t de 0 a 1)."""
    t = max(0.0, min(t, 1.0)) * (len(cores) - 1)
    i = min(int(t), len(cores) - 2)
    a, b, f = cores[i], cores[i + 1], t - i
    return tuple(round(a[k] + (b[k] - a[k]) * f) for k in range(3))


# ---------- cenário ----------

def ceu(d, tema):
    for y in range(0, Y_HORIZONTE, 4):  # faixas de 4 px: degradê "pixelado"
        d.rectangle((0, y, W, y + 3), fill=degrade(tema["ceu"], y / Y_HORIZONTE))


def estrelas(d, rnd, cor):
    for _ in range(40):
        x, y = rnd.randrange(4, W - 4), rnd.randrange(4, 112)
        if 44 <= y <= 100 or (y < 44 and (x < 84 or x > 150)):
            continue  # longe dos textos e da hora
        d.point((x, y), fill=cor)
        if rnd.random() < 0.35:
            d.point([(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)], fill=cor)


def morro(d, cor, base, amp, fase, escala):
    for x in range(0, W, 2):
        alt = base - amp * (0.6 * math.sin((x + fase) / escala)
                            + 0.4 * math.sin((x + fase) / (escala * 0.45)))
        d.rectangle((x, int(alt) // 2 * 2, x + 1, Y_HORIZONTE), fill=cor)


def cidade(d, rnd, cor, janela, livre=None, alt_max=34):
    x = 0
    while x < W:
        larg = rnd.choice([8, 10, 12, 14, 16])
        alt = rnd.randrange(10, alt_max)
        if livre and livre[0] - larg < x < livre[1]:
            alt = min(alt, 8)  # deixa o astro aparecer
        topo = Y_HORIZONTE - alt
        d.rectangle((x, topo, x + larg - 1, Y_HORIZONTE), fill=cor)
        if alt > 20 and rnd.random() < 0.3:
            d.rectangle((x + larg // 2, topo - 4, x + larg // 2, topo), fill=cor)
        if janela:
            for wy in range(topo + 3, Y_HORIZONTE - 3, 5):
                for wx in range(x + 2, x + larg - 3, 4):
                    if rnd.random() < 0.4:
                        d.rectangle((wx, wy, wx + 1, wy + 1), fill=janela)
        x += larg + rnd.choice([2, 4, 6])


def pinheiro(d, x, base, alt, cor, tronco):
    d.rectangle((x - 1, base - 3, x, base), fill=tronco)
    for i in range(alt):
        meia = max(1, (i * 6) // alt + (i % 4) // 2)
        y = base - 3 - alt + i
        d.rectangle((x - meia, y, x + meia - 1, y), fill=cor)


def nuvem(d, x, y, cor):
    for dx, dy, w, h in [(0, 4, 26, 6), (4, 0, 12, 6), (14, 2, 8, 4)]:
        d.rectangle((x + dx, y + dy, x + dx + w - 1, y + dy + h - 1), fill=cor)


def cenario(img, nome):
    tema = TEMAS[nome]
    d = ImageDraw.Draw(img)
    rnd = random.Random(7)
    ceu(d, tema)
    if nome == "noite":
        estrelas(d, rnd, (120, 160, 255))
        d.ellipse((132, 104, 164, 136), fill=tema["astro"])
        morro(d, tema["morros"][0], 116, 12, 0, 22)
        cidade(d, rnd, tema["predio"], tema["janela"], livre=(130, 166))
    elif nome == "por_do_sol":
        d.ellipse((150, 108, 194, 152), fill=tema["astro"])
        morro(d, tema["morros"][0], 120, 10, 40, 26)
        cidade(d, rnd, tema["predio"], tema["janela"], livre=(146, 196))
    elif nome == "dia":
        for x, y in [(96, 30), (176, 50), (20, 56)]:
            nuvem(d, x, y, NUVEM)
        morro(d, tema["morros"][0], 112, 14, 10, 24)
        cidade(d, rnd, tema["predio"], None, alt_max=26)
        morro(d, tema["morros"][1], 136, 4, 70, 30)
        for x in range(6, W, 22):
            pinheiro(d, x + rnd.randrange(-3, 4), 140, rnd.randrange(14, 24),
                     (24, 96, 52), (90, 60, 30))
        d.rectangle((0, 140, W, Y_HORIZONTE), fill=(70, 170, 70))


def fundo(nome):
    img = Image.new("RGB", (W, H), CARTAO if nome != "minimalista" else (0, 0, 0))
    if nome != "minimalista":
        cenario(img, nome)
    d = ImageDraw.Draw(img)
    d.rectangle((0, Y_HORIZONTE + 1, W, H),
                fill=CARTAO if nome != "minimalista" else (0, 0, 0))
    for c in (CARTAO_CLAUDE, CARTAO_SEMANA):
        d.rounded_rectangle(c, radius=5, fill=CARTAO, outline=BORDA, width=1)
    return img


# ---------- ícones ----------

def icone_sol(d, x, y):
    d.ellipse((x + 4, y + 4, x + 15, y + 15), fill=SOL)
    for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
        px, py = x + 9 + dx * 9, y + 9 + dy * 9
        d.rectangle((px, py, px + 1, py + 1), fill=SOL)


def icone_lua(d, x, y, fundo_cor):
    d.ellipse((x + 2, y + 2, x + 17, y + 17), fill=SOL)
    d.ellipse((x + 7, y - 1, x + 22, y + 14), fill=fundo_cor)


def icone_claude(d, x, y):
    cx, cy = x + 6, y + 6  # asterisco de 8 pontas, traço de 2 px
    for dx, dy in [(1, 0), (0, 1), (1, 1), (1, -1)]:
        for k in range(-6, 7):
            px, py = cx + dx * k, cy + dy * k
            d.rectangle((px, py, px + 1, py + 1), fill=LARANJA)


def icone_calendario(d, x, y):
    d.rectangle((x, y + 2, x + 11, y + 12), outline=AZUL)
    d.rectangle((x, y + 2, x + 11, y + 4), fill=AZUL)
    d.point([(x + 3, y), (x + 3, y + 1), (x + 8, y), (x + 8, y + 1)], fill=AZUL)
    d.rectangle((x + 3, y + 7, x + 5, y + 9), fill=AZUL)


# ---------- tela ----------

def barra(d, x0, y0, x1, y1, pct, cor):
    d.rectangle((x0, y0, x1, y1), fill=TRILHO)
    cheio = round((x1 - x0) * max(0, min(pct, 100)) / 100)
    if cheio:
        d.rectangle((x0, y0, x0 + cheio, y1), fill=cor)


def tela(estado, nome):
    tema = TEMAS[nome]
    img = fundo(nome)
    d = ImageDraw.Draw(img)
    d.fontmode = "1"  # sem suavização: só pixels acesos/apagados
    agora = estado["agora"]
    c1, c2 = tema["texto"], tema["texto_2"]

    # topo
    d.text((12, 6), DIAS[agora.weekday()], font=fonte(30), fill=c1)
    d.text((12, 30), f"{agora.day:02d} {MESES[agora.month - 1]}",
           font=fonte(20), fill=c2)
    d.text((202, 8), f"{estado['temp']}°", font=fonte(30), fill=c1, anchor="ra")
    if estado["dia"]:
        icone_sol(d, 208, 6)
    else:
        icone_lua(d, 208, 6, img.getpixel((236, 4)))

    # hora
    d.text((W // 2, 80), agora.strftime("%H:%M"), font=fonte(80),
           fill=c1, anchor="mm")

    # cartão Claude
    x0, y0, x1, _ = CARTAO_CLAUDE
    s = estado["sessao"]
    icone_claude(d, x0 + 8, y0 + 7)
    d.text((x0 + 26, y0 + 22), "Claude", font=fonte(30), fill=TEXTO, anchor="ls")
    d.text((x1 - 8, y0 + 22), f"{s}%", font=fonte(30), fill=TEXTO, anchor="rs")
    barra(d, x0 + 8, y0 + 26, x1 - 8, y0 + 31, s, cor_uso(s))
    f_peq = fonte(20)
    d.text((x0 + 8, y0 + 48), "sessão 5h", font=f_peq, fill=TEXTO_2, anchor="ls")
    d.text((x1 - 8, y0 + 48), f"reinicia {estado['reinicia']}", font=f_peq,
           fill=TEXTO_2, anchor="rs")

    # cartão Semana
    x0, y0, x1, _ = CARTAO_SEMANA
    w = estado["semana"]
    icone_calendario(d, x0 + 8, y0 + 7)
    d.text((x0 + 26, y0 + 20), "Semana", font=f_peq, fill=TEXTO, anchor="ls")
    barra(d, x0 + 94, y0 + 12, x1 - 44, y0 + 17, w, AZUL)
    d.text((x1 - 8, y0 + 20), f"{w}%", font=f_peq, fill=TEXTO, anchor="rs")
    return img


if __name__ == "__main__":
    saida = Path(sys.argv[1] if len(sys.argv) > 1 else "previa.png")
    base = {"agora": datetime(2026, 10, 26, 2, 3), "sessao": 41,
            "reinicia": "3h31", "semana": 35}
    casos = [("noite", 15, False), ("dia", 28, True),
             ("minimalista", 15, False), ("por_do_sol", 24, True)]
    folha = Image.new("RGB", (W * 2 + 12, H * 2 + 12), (40, 40, 48))
    for i, (nome, temp, dia) in enumerate(casos):
        img = tela({**base, "temp": temp, "dia": dia}, nome)
        folha.paste(img, ((i % 2) * (W + 12), (i // 2) * (H + 12)))
    folha.resize((folha.width * 2, folha.height * 2), Image.NEAREST).save(saida)
    print("gerado:", saida)
