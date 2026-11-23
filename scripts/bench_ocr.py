#!/usr/bin/env python3
"""Compara os motores de OCR em AMOSTRAS de paginas (inicio, meio, fim).
Gabarito = camada de texto do proprio PDF (use um PDF digital como base).
Imprime 1 linha por motor + a recomendacao.

Uso: python bench_ocr.py base.pdf [-k 3] [--engines dharma,unlimited,tesseract] [--dpi 200] [--rerun]
Saidas ficam em cache (~/.cache/ocr-integro/bench) para reavaliar sem refazer OCR.
"""
import argparse, json, os, re, sys, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engines
from check_integrity import picks
from textq import SUP, dedupe_fields

ACC = re.compile(r"[áàâãéêíóôõúç]", re.I)


def norm(t):
    t = dedupe_fields(t).translate(SUP)
    t = re.sub(r"<!--\s*(cabecalho|margem|rodape):", " ", t)  # conteudo de cabecalho/rodape conta
    t = re.sub(r"<!--.*?-->|<[^>]+>|-->", " ", t, flags=re.S)
    t = re.sub(r"-\n(\w)", r"\1", t)
    t = re.sub(r"[#*_|`>\[\]()]+", " ", t)
    return re.findall(r"\w+", t.lower())


def wer(ref, hyp):
    """Distancia de edicao por palavra / len(ref)."""
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1] / len(ref)


def acc_recall(ref, hyp):
    """Fracao das palavras acentuadas do gabarito que aparecem no OCR (importante em PT)."""
    ra = [w for w in ref if ACC.search(w)]
    if not ra:
        return 1.0
    hs = {}
    for w in hyp:
        hs[w] = hs.get(w, 0) + 1
    hit = 0
    for w in ra:
        if hs.get(w, 0):
            hs[w] -= 1
            hit += 1
    return hit / len(ra)


def degrade(f):
    """Simula digitalizacao ruim: 110 dpi efetivos, rotacao, desfoque, ruido, JPEG."""
    import random
    from PIL import Image, ImageFilter
    im = Image.open(f).convert("L")
    w, h = im.size
    im = im.resize((w * 110 // 200, h * 110 // 200)).rotate(1.2, expand=True, fillcolor=255)
    im = im.filter(ImageFilter.GaussianBlur(0.9))
    rnd = random.Random(1)
    px = im.load()
    for _ in range(im.size[0] * im.size[1] // 40):
        x, y = rnd.randrange(im.size[0]), rnd.randrange(im.size[1])
        px[x, y] = rnd.choice((0, 90, 255))
    im.save(f[:-4] + ".jpg", quality=35)
    os.replace(f[:-4] + ".jpg", f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-k", type=int, default=3)
    ap.add_argument("--engines", default=",".join(engines.available()))
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--degrade", action="store_true", help="simular digitalizacao ruim")
    ap.add_argument("--rerun", action="store_true", help="ignorar cache de saidas")
    a = ap.parse_args()
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    doc = fitz.open(a.pdf)
    idx = picks(doc.page_count, a.k, a.pdf)
    tmp = tempfile.mkdtemp(prefix="bench_")
    refs, imgs = [], []
    for i in idx:
        refs.append(norm(doc[i].get_text()))
        f = os.path.join(tmp, f"p{i+1}.png")
        doc[i].get_pixmap(dpi=a.dpi).save(f)
        if a.degrade:
            degrade(f)
        imgs.append(f)
    if sum(map(len, refs)) < 50:
        sys.exit("PDF sem camada de texto: use um PDF digital como base do benchmark.")
    print(f"AMOSTRA\tpaginas {[i+1 for i in idx]} de {doc.page_count}\tpalavras={sum(map(len, refs))}")
    res = []
    cdir = os.path.join(engines.BASE, "bench")
    os.makedirs(cdir, exist_ok=True)
    stem = re.sub(r"\W+", "_", os.path.basename(a.pdf))[:60] + "_" + "-".join(map(str, idx)) + f"_{a.dpi}" + ("_deg" if a.degrade else "")
    for e in [x for x in a.engines.split(",") if x]:
        cf = os.path.join(cdir, f"{stem}_{e}.json")
        if os.path.exists(cf) and not a.rerun:
            d = json.load(open(cf, encoding="utf-8"))
            pages, secs = d["pages"], d["secs"]
        else:
            try:
                pages, secs = engines.run(e, imgs)
            except Exception as ex:
                print(f"ERRO\t{e}\t{str(ex)[:150]}")
                continue
            json.dump({"pages": pages, "secs": secs}, open(cf, "w", encoding="utf-8"), ensure_ascii=False)
        hyps = [norm(p) for p in pages]
        w = sum(wer(r, h) * len(r) for r, h in zip(refs, hyps)) / sum(map(len, refs))
        ac = sum(acc_recall(r, h) for r, h in zip(refs, hyps)) / len(refs)
        sp = sum(secs) / max(len(secs), 1)
        res.append((w, sp, e, ac))
        print(f"{e}\tWER={w:.3f}\tacentos={ac:.0%}\t{sp:.1f}s/pag")
    shutil.rmtree(tmp, ignore_errors=True)
    if res:
        best = min(res, key=lambda r: (round(r[0], 2), r[1]))
        print(f"MELHOR\t{best[2]}\t(menor WER; empate -> mais rapido)")


if __name__ == "__main__":
    main()
