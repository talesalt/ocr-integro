#!/usr/bin/env python3
"""Converte PDF/imagens em .md com o minimo de trabalho: paginas com texto bom sao
extraidas direto; so as ruins/escaneadas vao para OCR. O motor e escolhido pelas amostras
(PT -> DharmaOCR, longo/outro idioma -> Unlimited-OCR, sem GPU -> Tesseract).
Imprime 1 linha por arquivo.

Uso: python ocr_to_md.py <arquivos|pastas> [-o saida] [--engine auto|dharma|unlimited|tesseract]
       [--force-ocr] [--dpi 200] [--lang por]
"""
import argparse, os, sys, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from textq import quality
import engines

IMG_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def convert_pdf(path, want, force, dpi, lang):
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    doc = fitz.open(path)
    pages, need, good = [None] * doc.page_count, [], []
    tmp = tempfile.mkdtemp(prefix="ocrpg_")
    for i, pg in enumerate(doc):
        txt = "" if force else pg.get_text()
        if not force and quality(txt)["verdict"] == "OK":
            pages[i] = txt.strip()
            good.append(txt)
        else:
            f = os.path.join(tmp, f"p{i+1:04d}.png")
            pg.get_pixmap(dpi=dpi).save(f)
            need.append((i, f))
    eng, why = "-", "texto extraido direto"
    if need:
        imgs = [f for _, f in need]
        pr = engines.probe(imgs, lang=lang) if want == "auto" else {}
        if good and pr:
            pr["texts"] = good[:2] + pr["texts"]
        eng, why = engines.choose(pr, len(need), want)
        for (i, _), t in zip(need, engines.run(eng, imgs, lang)[0]):
            pages[i] = t
    shutil.rmtree(tmp, ignore_errors=True)
    return pages, len(need), eng, why


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("-o", "--out", help="pasta de saida (padrao: ao lado do arquivo)")
    ap.add_argument("--engine", default="auto", choices=["auto", "dharma", "unlimited", "tesseract"])
    ap.add_argument("--force-ocr", action="store_true", help="OCR em todas as paginas")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--lang", default="por", help="idioma do Tesseract (ex: por+eng)")
    a = ap.parse_args()
    files = []
    for p in a.paths:
        if os.path.isdir(p):
            files += [os.path.join(p, f) for f in sorted(os.listdir(p))
                      if os.path.splitext(f)[1].lower() in IMG_EXT | {".pdf"}]
        else:
            files.append(p)
    ok = True
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        try:
            if ext == ".pdf":
                pages, nocr, eng, why = convert_pdf(f, a.engine, a.force_ocr, a.dpi, a.lang)
            elif ext in IMG_EXT:
                img = os.path.abspath(f)
                eng, why = engines.choose(engines.probe([img], 1, a.lang) if a.engine == "auto" else {}, 1, a.engine)
                pages, nocr = engines.run(eng, [img], a.lang)[0], 1
            else:
                print(f"IGNORADO\t{f}")
                continue
            name = os.path.splitext(os.path.basename(f))[0]
            if name.lower().endswith(".docx"):
                name = name[:-5]
            od = a.out or os.path.dirname(os.path.abspath(f))
            os.makedirs(od, exist_ok=True)
            md = os.path.join(od, name + ".md")
            body = "\n\n".join(f"<!-- pagina {i+1} -->\n\n{t or ''}" for i, t in enumerate(pages))
            with open(md, "w", encoding="utf-8") as h:
                h.write(f"# {name}\n\n<!-- fonte: {os.path.basename(f)} | ocr: {nocr}/{len(pages)} pag | motor: {eng} ({why}) -->\n\n{body}\n")
            print(f"OK\t{md}\tpaginas={len(pages)} ocr={nocr} motor={eng} ({why}) qualidade={quality(body)['verdict']}")
        except Exception as e:
            ok = False
            print(f"ERRO\t{f}\t{str(e)[:200]}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
