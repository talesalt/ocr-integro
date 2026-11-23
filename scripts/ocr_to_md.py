#!/usr/bin/env python3
"""Converte PDF/imagens em .md com o minimo de trabalho: paginas com texto bom sao
extraidas direto; so as ruins/escaneadas vao para OCR. Imprime 1 linha por arquivo.

Uso: python ocr_to_md.py <arquivos|pastas> [-o pasta_saida] [--engine auto|unlimited|tesseract]
       [--force-ocr] [--dpi 200] [--lang por]
engine auto = Unlimited-OCR 2 se instalado (setup_unlimited.ps1), senao Tesseract.
"""
import argparse, json, os, subprocess, sys, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from textq import quality

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("OCR_INTEGRO_HOME", os.path.join(os.path.expanduser("~"), ".cache", "ocr-integro"))
UPY = os.path.join(BASE, "venv-uocr", "Scripts" if os.name == "nt" else "bin",
                   "python.exe" if os.name == "nt" else "python")
IMG_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def tesseract_bin():
    t = shutil.which("tesseract")
    if not t and os.name == "nt":
        c = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        t = c if os.path.exists(c) else None
    return t


def pick_engine(want):
    if want in ("unlimited", "auto") and os.path.exists(UPY):
        return "unlimited"
    if want == "unlimited":
        sys.exit("Unlimited-OCR nao instalado. Rode scripts/setup_unlimited.ps1")
    if tesseract_bin():
        return "tesseract"
    sys.exit("Nenhum motor de OCR: rode setup_unlimited.ps1 ou instale o Tesseract (lang por).")


def ocr_images(images, engine, lang):
    if not images:
        return []
    if engine == "unlimited":
        tmp = tempfile.mkdtemp(prefix="ocrmd_")
        cfg = os.path.join(tmp, "cfg.json")
        out = os.path.join(tmp, "out.json")
        json.dump({"images": images, "out": out}, open(cfg, "w", encoding="utf-8"))
        r = subprocess.run([UPY, os.path.join(HERE, "uocr_worker.py"), cfg],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0 or not os.path.exists(out):
            tail = (r.stderr or r.stdout).strip().splitlines()[-3:]
            raise RuntimeError("Unlimited-OCR falhou: " + " | ".join(tail))
        return json.load(open(out, encoding="utf-8"))["pages"]
    t = tesseract_bin()
    res = []
    for img in images:
        r = subprocess.run([t, img, "stdout", "-l", lang, "--psm", "3"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        res.append(r.stdout.strip())
    return res


def convert_pdf(path, engine_want, force, dpi, lang):
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    doc = fitz.open(path)
    pages, need = [None] * doc.page_count, []
    tmp = tempfile.mkdtemp(prefix="ocrpg_")
    for i, pg in enumerate(doc):
        txt = "" if force else pg.get_text()
        if not force and quality(txt)["verdict"] == "OK":
            pages[i] = txt.strip()
        else:
            f = os.path.join(tmp, f"p{i+1:04d}.png")
            pg.get_pixmap(dpi=dpi).save(f)
            need.append((i, f))
    engine = "-"
    if need:
        engine = pick_engine(engine_want)
        for (i, _), t in zip(need, ocr_images([f for _, f in need], engine, lang)):
            pages[i] = t
    shutil.rmtree(tmp, ignore_errors=True)
    return pages, len(need), engine


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("-o", "--out", help="pasta de saida (padrao: ao lado do arquivo)")
    ap.add_argument("--engine", default="auto", choices=["auto", "unlimited", "tesseract"])
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
                pages, nocr, eng = convert_pdf(f, a.engine, a.force_ocr, a.dpi, a.lang)
            elif ext in IMG_EXT:
                eng = pick_engine(a.engine)
                pages, nocr = ocr_images([os.path.abspath(f)], eng, a.lang), 1
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
                h.write(f"# {name}\n\n<!-- fonte: {os.path.basename(f)} | ocr: {nocr}/{len(pages)} pag | motor: {eng} -->\n\n{body}\n")
            q = quality(body)
            print(f"OK\t{md}\tpaginas={len(pages)} ocr={nocr} motor={eng} qualidade={q['verdict']}")
        except Exception as e:
            ok = False
            print(f"ERRO\t{f}\t{str(e)[:200]}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
