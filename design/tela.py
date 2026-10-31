"""Prévia 240x240 da tela do RERelogio (pixel-art, tema muda com o horário).

Fundo fixo por tema (céu, cenário, molduras dos cartões) + partes dinâmicas
desenhadas com as tabelas de `glifos.py`, do mesmo jeito que o firmware.
O firmware espelha `desenha_dinamico`; as posições vêm de LAYOUT (exportado
por `gerar.py`).

Uso: python3 -I design/tela.py [saida.png]   (folha 2x2 com os 4 temas, 2x)
"""
import math
import random
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import glifos as G  # noqa: E402

W = H = 240
Y_HORIZONTE = 146

# Posições usadas pelo firmware (y de texto = linha de base)
LAYOUT = {
    "DIA_X": 12, "DIA_Y": 30,
    "DATA_X": 12, "DATA_Y": 48,
    "TEMP_X": 202, "TEMP_Y": 30,
    "CLIMA_X": 206, "CLIMA_Y": 6,
    "HORA_X": 120, "HORA_Y": 102,
    "CC_X0": 6, "CC_Y0": 150, "CC_X1": 233, "CC_Y1": 203,  # cartão Claude
    "CS_X0": 6, "CS_Y0": 207, "CS_X1": 233, "CS_Y1": 235,  # cartão Semana
}
L = LAYOUT

# Cores comuns (cartões)
CARTAO = (6, 12, 34)
BORDA = (44, 92, 210)
TRILHO = (30, 40, 70)
TEXTO = (240, 244, 255)
TEXTO_2 = (130, 160, 225)
LARANJA = (242, 132, 58)
AMBAR = (246, 190, 60)
VERMELHO = (236, 72, 60)
AZUL = (40, 132, 255)
CHUVA = (90, 160, 230)
CINZA = (100, 108, 130)  # dado velho

# Ordem = índice no firmware
TEMAS = {
    "noite": {
        "ceu": [(6, 10, 32), (18, 30, 78)],
        "morros": [(30, 62, 150), (22, 44, 112)],
        "predio": (8, 12, 30), "janela": (246, 196, 66),
        "astro": (226, 234, 255),
        "texto": TEXTO, "texto_2": TEXTO_2, "nuvem": (200, 210, 235),
    },
    "dia": {
        "ceu": [(46, 140, 240), (150, 214, 255)],
        "morros": [(110, 150, 200), (60, 150, 80)],
        "predio": (120, 160, 210),
        "texto": (8, 16, 40), "texto_2": (20, 50, 110), "nuvem": (255, 255, 255),
    },
    "por_do_sol": {
        "ceu": [(92, 52, 140), (255, 120, 140), (255, 180, 110)],
        "morros": [(150, 70, 140), (100, 46, 110)],
        "predio": (48, 22, 70), "janela": (255, 190, 90),
        "astro": G.SOL,
        "texto": (20, 8, 30), "texto_2": (70, 20, 70), "nuvem": (255, 240, 240),
    },
    "minimalista": {
        "texto": TEXTO, "texto_2": TEXTO_2, "nuvem": (200, 210, 235),
    },
}

DIAS = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]
MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN",
         "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]


def cor_uso(p):
    if p > 85:
        return VERMELHO
    if p >= 60:
        return AMBAR
    return LARANJA


def degrade(cores, t):
    t = max(0.0, min(t, 1.0)) * (len(cores) - 1)
    i = min(int(t), len(cores) - 2)
    a, b, f = cores[i], cores[i + 1], t - i
    return tuple(round(a[k] + (b[k] - a[k]) * f) for k in range(3))


# ---------- cenário (fundo fixo) ----------

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


def cenario(d, nome):
    tema = TEMAS[nome]
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
            nuvem(d, x, y, (255, 255, 255))
        morro(d, tema["morros"][0], 112, 14, 10, 24)
        cidade(d, rnd, tema["predio"], None, alt_max=26)
        morro(d, tema["morros"][1], 136, 4, 70, 30)
        for x in range(6, W, 22):
            pinheiro(d, x + rnd.randrange(-3, 4), 140, rnd.randrange(14, 24),
                     (24, 96, 52), (90, 60, 30))
        d.rectangle((0, 140, W, Y_HORIZONTE), fill=(70, 170, 70))


def fundo(nome):
    minimal = nome == "minimalista"
    img = Image.new("RGB", (W, H), (0, 0, 0) if minimal else CARTAO)
    d = ImageDraw.Draw(img)
    if not minimal:
        cenario(d, nome)
        d.rectangle((0, Y_HORIZONTE + 1, W, H), fill=CARTAO)  # corta o que passou do chão
    for c in ("CC", "CS"):
        caixa = (L[c + "_X0"], L[c + "_Y0"], L[c + "_X1"], L[c + "_Y1"])
        d.rounded_rectangle(caixa, radius=5, fill=CARTAO, outline=BORDA, width=1)
    return img


# ---------- partes dinâmicas (o firmware espelha esta função) ----------

def icones_clima(codigo, dia):
    if codigo <= 1:
        return [("sol", G.SOL)] if dia else [("lua", G.SOL)]
    if 51 <= codigo <= 67 or 80 <= codigo <= 82 or codigo >= 95:
        return [("nuvem", None), ("gotas", CHUVA)]
    return [("nuvem", None)]


def idade(minutos):
    if minutos < 60:
        return f"{minutos} min"
    if minutos < 24 * 60:
        return f"{minutos // 60}h"
    return f"{minutos // (24 * 60)}d"


def barra(img, x0, y0, x1, y1, pct, cor):
    d = ImageDraw.Draw(img)
    d.rectangle((x0, y0, x1, y1), fill=TRILHO)
    cheio = (x1 - x0) * max(0, min(pct, 100)) // 100
    if cheio:
        d.rectangle((x0, y0, x0 + cheio, y1), fill=cor)


def desenha_dinamico(img, e, nome):
    tema = TEMAS[nome]
    c1, c2 = tema["texto"], tema["texto_2"]
    agora = e["agora"]
    txt = G.desenha_texto

    # topo
    txt(img, "grande", L["DIA_X"], L["DIA_Y"], DIAS[agora.weekday()], c1)
    txt(img, "data", L["DATA_X"], L["DATA_Y"],
        f"{agora.day:02d} {MESES[agora.month - 1]}", c2)
    if e["temp"] is not None:
        txt(img, "grande", L["TEMP_X"], L["TEMP_Y"], f"{e['temp']}°", c1, "d")
        for icone, cor in icones_clima(e["codigo"], e["dia"]):
            G.desenha_icone(img, icone, L["CLIMA_X"], L["CLIMA_Y"], cor or tema["nuvem"])

    # hora
    txt(img, "hora", L["HORA_X"], L["HORA_Y"], agora.strftime("%H:%M"), c1, "c")

    # cartão Claude
    # idade_min: minutos desde a leitura; >15 = dado velho (cinza).
    # renovada: o horário de reinício já passou, então a sessão está em 0%.
    x0, y0, x1 = L["CC_X0"], L["CC_Y0"], L["CC_X1"]
    velho = e.get("idade_min", 0) > 15
    renovada = e.get("renovada", False)
    s = 0 if renovada else e["sessao"]
    G.desenha_icone(img, "claude", x0 + 8, y0 + 7, LARANJA)
    txt(img, "titulo", x0 + 26, y0 + 19, "Claude", TEXTO)
    txt(img, "pct", x1 - 8, y0 + 20, f"{s}%", CINZA if velho and not renovada else TEXTO, "d")
    barra(img, x0 + 8, y0 + 26, x1 - 8, y0 + 31, s, CINZA if velho else cor_uso(s))
    txt(img, "peq", x0 + 8, y0 + 46, "janela 5h", TEXTO_2)
    if renovada:
        direita = "sessão renovada"
    elif velho:
        direita = f"atualizado há {idade(e['idade_min'])}"
    else:
        direita = f"reinicia {e['reinicia']}"
    txt(img, "peq", x1 - 8, y0 + 46, direita, TEXTO_2, "d")

    # cartão Semana
    x0, y0, x1 = L["CS_X0"], L["CS_Y0"], L["CS_X1"]
    w = e["semana"]
    G.desenha_icone(img, "calendario", x0 + 8, y0 + 7, AZUL)
    txt(img, "peq", x0 + 26, y0 + 19, "Semana", TEXTO)
    txt(img, "peq", x0 + 26 + G.largura("peq", "Semana "), y0 + 19, "7d", TEXTO_2)
    barra(img, x0 + 104, y0 + 12, x1 - 44, y0 + 17, w, CINZA if velho else AZUL)
    txt(img, "peq", x1 - 8, y0 + 19, f"{w}%", CINZA if velho else TEXTO, "d")


def tela(e, nome):
    img = fundo(nome)
    desenha_dinamico(img, e, nome)
    return img


if __name__ == "__main__":
    saida = Path(sys.argv[1] if len(sys.argv) > 1 else "previa.png")
    base = {"agora": datetime(2026, 10, 26, 2, 3), "sessao": 41,
            "reinicia": "3h31", "semana": 35, "codigo": 0}
    casos = [("noite", 15, False), ("dia", 28, True),
             ("minimalista", 15, False), ("por_do_sol", 24, True)]
    folha = Image.new("RGB", (W * 2 + 12, H * 2 + 12), (40, 40, 48))
    for i, (nome, temp, dia) in enumerate(casos):
        img = tela({**base, "temp": temp, "dia": dia}, nome)
        folha.paste(img, ((i % 2) * (W + 12), (i // 2) * (H + 12)))
    folha.resize((folha.width * 2, folha.height * 2), Image.NEAREST).save(saida)
    print("gerado:", saida)

    # estados do cartão do Claude: normal, dado velho, sessão renovada
    estados = [{}, {"idade_min": 42}, {"renovada": True, "idade_min": 130}]
    tira = Image.new("RGB", (W * 3 + 24, 92), (40, 40, 48))
    for i, extra in enumerate(estados):
        img = tela({**base, "temp": 15, "dia": False, **extra}, "noite")
        tira.paste(img.crop((0, 148, W, H)), (i * (W + 12), 0))
    estados_png = saida.with_name("previa-estados.png")
    tira.resize((tira.width * 2, tira.height * 2), Image.NEAREST).save(estados_png)
    print("gerado:", estados_png)
