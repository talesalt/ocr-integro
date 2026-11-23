"""Roda DENTRO do venv do Unlimited-OCR. Le um JSON {"images": [...], "out": "x.json"}
e grava {"pages": [markdown_por_pagina]}. Nao imprime nada alem de 1 linha de status."""
import json, os, sys, io, contextlib, tempfile, re

cfg = json.load(open(sys.argv[1], encoding="utf-8"))
base = os.environ.get("OCR_INTEGRO_HOME", os.path.join(os.path.expanduser("~"), ".cache", "ocr-integro"))
sys.path.insert(0, base)
try:
    from process_unlimitedOCR2 import convert
except Exception:
    convert = None


def to_md(raw):
    if convert:
        try:
            return convert(raw)
        except Exception:
            pass
    t = re.sub(r"\[\d+,\s*\d+,\s*\d+,\s*\d+\]", "", raw)
    t = re.sub(r"</?(PAGE|BLOCK|LEVEL\d|FORK)[^>]*>", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


quiet = io.StringIO()
with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
    import torch
    from transformers import AutoModel, AutoTokenizer
    name = os.environ.get("UOCR_MODEL", "baidu/Unlimited-OCR-2")
    tok = AutoTokenizer.from_pretrained(name, trust_remote_code=True)
    model = AutoModel.from_pretrained(name, trust_remote_code=True, use_safetensors=True,
                                      torch_dtype=torch.bfloat16).eval().cuda()
    pages = []
    tmp = tempfile.mkdtemp(prefix="uocr_")
    for img in cfg["images"]:
        r = model.infer(tok, image_file=img, output_path=tmp, save_results=False)
        raw = r[0] if isinstance(r, tuple) else r
        pages.append(to_md(raw or ""))
        torch.cuda.empty_cache()

json.dump({"pages": pages}, open(cfg["out"], "w", encoding="utf-8"), ensure_ascii=False)
print(f"uocr ok {len(pages)} pag")
