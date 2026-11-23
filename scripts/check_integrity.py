#!/usr/bin/env python3
"""Checa integridade de textos por AMOSTRAGEM e imprime 1 linha por arquivo.

Uso: python check_integrity.py <arquivos|pastas> [-n 3] [--chars 1200] [-v] [--json]
Vereditos: OK | SUSPEITO | PRECISA_OCR | CORROMPIDO | IGNORADO
Codigo de saida: 0 se tudo OK, 1 se algo nao estiver OK.
"""
import argparse, json, os, random, sys, zipfile, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from textq import quality

TEXT_EXT = {".txt", ".md", ".csv", ".tsv", ".html", ".htm", ".xml", ".tex", ".rtf", ".srt"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def picks(total, n, seed):
    """Indices de amostra: inicio, meio, fim + aleatorios (deterministico)."""
    if total <= n:
        return list(range(total))
    base = {0, total // 2, total - 1}
    rnd = random.Random(seed)
    while len(base) < n:
        base.add(rnd.randrange(total))
    return sorted(base)[:max(n, 3)]


def agg(samples):
    """Agrega vereditos das amostras."""
    vs = [s["verdict"] for s in samples]
    bad = [s for s in samples if s["verdict"] != "OK"]
    if not samples:
        return "SEM_TEXTO", "vazio"
    if all(v == "SEM_TEXTO" for v in vs):
        return "PRECISA_OCR", "sem camada de texto nas amostras"
    if any(v == "SEM_TEXTO" for v in vs):
        k = sum(v == "SEM_TEXTO" for v in vs)
        return "PRECISA_OCR", f"{k}/{len(vs)} amostras sem texto (paginas escaneadas?)"
    if bad:
        return "SUSPEITO", bad[0].get("why", "")
    return "OK", ""


def check_pdf(path, n, chars):
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    try:
        doc = fitz.open(path)
    except Exception as e:
        return "CORROMPIDO", f"nao abre: {e}", {}
    if doc.needs_pass:
        return "CORROMPIDO", "protegido por senha", {}
    total = doc.page_count
    idx = picks(total, n, path)
    samples = []
    for i in idx:
        try:
            samples.append(quality(doc[i].get_text()[:chars]))
        except Exception as e:
            samples.append({"verdict": "SUSPEITO", "why": f"pag {i+1} ilegivel: {e}"})
    v, why = agg(samples)
    return v, why, {"paginas": total, "amostra": [i + 1 for i in idx]}


def sample_text(t, n, chars, seed):
    if len(t) <= chars * n:
        return [t]
    total = len(t) // chars
    return [t[i * chars:(i + 1) * chars] for i in picks(total, n, seed)]


def read_text(path):
    raw = open(path, "rb").read()
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace"), "nao-utf8"


def check_text(path, n, chars):
    t, enc = read_text(path)
    if path.lower().endswith(".html") or path.lower().endswith(".htm"):
        t = re.sub(r"<[^>]+>", " ", t)
    s = [quality(x) for x in sample_text(t, n, chars, path)]
    v, why = agg(s)
    if v == "PRECISA_OCR":
        v, why = "SUSPEITO", "arquivo de texto vazio/quase vazio"
    if enc != "utf-8":
        why = (why + "; " if why else "") + "nao e UTF-8"
        v = "SUSPEITO" if v == "OK" else v
    return v, why, {"chars": len(t)}


def check_json(path, n, chars):
    try:
        json.loads(open(path, "rb").read().decode("utf-8"))
    except Exception as e:
        return "CORROMPIDO", f"JSON invalido: {str(e)[:80]}", {}
    return check_text(path, n, chars)


def check_docx(path, n, chars):
    try:
        with zipfile.ZipFile(path) as z:
            bad = z.testzip()
            if bad:
                return "CORROMPIDO", f"zip com erro em {bad}", {}
            xml = z.read("word/document.xml").decode("utf-8", "replace")
    except Exception as e:
        return "CORROMPIDO", f"docx invalido: {e}", {}
    t = re.sub(r"</w:p>", "\n", xml)
    t = re.sub(r"<[^>]+>", "", t)
    s = [quality(x) for x in sample_text(t, n, chars, path)]
    v, why = agg(s)
    return ("SUSPEITO", "docx sem texto") if v == "PRECISA_OCR" else (v, why)


def check_zip(path, n, chars):
    try:
        with zipfile.ZipFile(path) as z:
            bad = z.testzip()
            k = len(z.namelist())
    except Exception as e:
        return "CORROMPIDO", f"zip invalido: {e}", {}
    return ("CORROMPIDO", f"CRC falhou em {bad}", {}) if bad else ("OK", "", {"itens": k})


def check(path, n, chars):
    ext = os.path.splitext(path)[1].lower()
    if os.path.getsize(path) == 0:
        return "CORROMPIDO", "arquivo vazio (0 bytes)", {}
    if ext == ".pdf":
        return check_pdf(path, n, chars)
    if ext == ".docx":
        r = check_docx(path, n, chars)
        return r if len(r) == 3 else (*r, {})
    if ext == ".json":
        return check_json(path, n, chars)
    if ext == ".zip":
        return check_zip(path, n, chars)
    if ext in IMG_EXT:
        return "PRECISA_OCR", "imagem", {}
    if ext in TEXT_EXT:
        return check_text(path, n, chars)
    return "IGNORADO", f"tipo {ext or '?'}", {}


def walk(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for f in sorted(files):
                    yield os.path.join(root, f)
        elif os.path.exists(p):
            yield p
        else:
            print(f"NAO_ENCONTRADO\t{p}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("-n", type=int, default=3, help="amostras por arquivo (min 3)")
    ap.add_argument("--chars", type=int, default=1200, help="caracteres por amostra")
    ap.add_argument("-v", action="store_true", help="mostrar detalhes")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--all", action="store_true", help="listar tambem IGNORADO")
    a = ap.parse_args()
    cnt, rows = {}, []
    for f in walk(a.paths):
        try:
            v, why, info = check(f, max(a.n, 3), a.chars)
        except Exception as e:
            v, why, info = "CORROMPIDO", f"erro: {e}", {}
        cnt[v] = cnt.get(v, 0) + 1
        rows.append({"arquivo": f, "veredito": v, "motivo": why, **info})
        if a.json or (v == "IGNORADO" and not a.all):
            continue
        extra = f"\t{info}" if a.v and info else ""
        print(f"{v}\t{f}" + (f"\t{why}" if why else "") + extra)
    if a.json:
        print(json.dumps(rows, ensure_ascii=False))
    print("RESUMO\t" + " ".join(f"{k}={v}" for k, v in sorted(cnt.items())))
    sys.exit(0 if set(cnt) <= {"OK", "IGNORADO"} else 1)


if __name__ == "__main__":
    main()
