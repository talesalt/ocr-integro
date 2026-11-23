"""Motores de OCR e a regra de escolha automatica (usada por ocr_to_md e bench_ocr)."""
import json, os, shutil, subprocess, sys, tempfile, time
from textq import lang_guess

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("OCR_INTEGRO_HOME", os.path.join(os.path.expanduser("~"), ".cache", "ocr-integro"))
def _vpy(name):
    return os.path.join(BASE, name, "Scripts" if os.name == "nt" else "bin",
                        "python.exe" if os.name == "nt" else "python")


# cada motor tem seu venv: Unlimited exige transformers 4.52.1, Dharma (FP8) exige 4.57+
VPY = {"unlimited": _vpy("venv-uocr"), "dharma": _vpy("venv-dharma")}
LONG_DOC = 40  # paginas a partir das quais o Unlimited-OCR compensa (fora do PT)
CONF_OK = 80   # confianca media do Tesseract acima da qual o scan e considerado limpo


def tesseract_bin():
    t = shutil.which("tesseract")
    if not t and os.name == "nt":
        c = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        t = c if os.path.exists(c) else None
    return t


def available():
    """Motores instalados (marcadores gravados pelo setup)."""
    a = []
    if os.path.exists(VPY["dharma"]) and os.path.exists(os.path.join(BASE, "dharma.ok")):
        a.append("dharma")
    if os.path.exists(VPY["unlimited"]) and os.path.exists(os.path.join(BASE, "process_unlimitedOCR2.py")):
        a.append("unlimited")
    if tesseract_bin():
        a.append("tesseract")
    return a


def run(engine, images, lang="por"):
    """Retorna (paginas_md, segundos_por_pagina)."""
    if not images:
        return [], []
    if engine in ("dharma", "unlimited"):
        tmp = tempfile.mkdtemp(prefix="ocrmd_")
        cfg, out = os.path.join(tmp, "cfg.json"), os.path.join(tmp, "out.json")
        json.dump({"engine": engine, "images": images, "out": out}, open(cfg, "w", encoding="utf-8"))
        r = subprocess.run([VPY[engine], os.path.join(HERE, "gpu_worker.py"), cfg], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0 or not os.path.exists(out):
            tail = (r.stderr or r.stdout).strip().splitlines()[-3:]
            raise RuntimeError(f"{engine} falhou: " + " | ".join(tail))
        d = json.load(open(out, encoding="utf-8"))
        shutil.rmtree(tmp, ignore_errors=True)
        return d["pages"], d.get("secs", [])
    t = tesseract_bin()
    pages, secs = [], []
    for img in images:
        t0 = time.time()
        r = subprocess.run([t, img, "stdout", "-l", lang, "--psm", "3"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        pages.append(r.stdout.strip())
        secs.append(round(time.time() - t0, 1))
    return pages, secs


def choose(probe, n_ocr_pages, want="auto"):
    """Escolhe o motor a partir da sonda das amostras. Retorna (motor, motivo).
    Regra (calibrada em bench_ocr.py, ver README):
      - Tesseract confiante (scan limpo)   -> tesseract (mesma qualidade, ~50x mais rapido)
      - scan dificil + portugues           -> dharma   (especializado em PT-BR, ~1 min/pag)
      - scan dificil + outro idioma/longo  -> unlimited
    """
    av = available()
    if want != "auto":
        if want not in av:
            sys.exit(f"Motor '{want}' nao instalado. Disponiveis: {av or 'nenhum'} (veja setup_gpu.ps1)")
        return want, "escolhido pelo usuario"
    if not av:
        sys.exit("Nenhum motor de OCR instalado: rode setup_gpu.ps1 ou instale o Tesseract (por).")
    conf, lang = probe.get("conf"), lang_guess(" ".join(probe.get("texts", [])))
    tag = f"conf={conf:.0f} idioma={lang}" if conf is not None else f"idioma={lang}"
    gpu = [e for e in ("dharma", "unlimited") if e in av]
    if "tesseract" in av and (not gpu or (conf is not None and conf >= CONF_OK)):
        return "tesseract", f"scan limpo ({tag})"
    if n_ocr_pages >= LONG_DOC and "unlimited" in av and lang != "pt":
        return "unlimited", f"documento longo ({n_ocr_pages} pag, {tag})"
    if lang == "pt" and "dharma" in av:
        return "dharma", f"scan dificil em portugues ({tag})"
    if "unlimited" in av:
        return "unlimited", f"scan dificil ({tag})"
    return gpu[0] if gpu else av[0], tag


def probe(page_images, k=2, lang="por"):
    """Sonda barata: Tesseract (CPU) em ate k paginas de amostra (inicio e meio).
    Retorna {"texts": [...], "conf": confianca_media_0_100 ou None}."""
    t = tesseract_bin()
    if not t or not page_images:
        return {"texts": [], "conf": None}
    idx = sorted({0, len(page_images) // 2})[:k]
    texts, confs = [], []
    for i in idx:
        r = subprocess.run([t, page_images[i], "stdout", "-l", lang, "--psm", "3", "tsv"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        words = []
        for row in r.stdout.splitlines()[1:]:
            c = row.split(chr(9))
            if len(c) == 12 and c[11].strip():
                try:
                    cf = float(c[10])
                except ValueError:
                    continue
                if cf >= 0:
                    confs.append(cf)
                    words.append(c[11])
        texts.append(" ".join(words)[:2000])
    return {"texts": texts, "conf": sum(confs) / len(confs) if confs else 0.0}
