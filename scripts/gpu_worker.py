"""Roda DENTRO do venv da GPU (~/.cache/ocr-integro/venv-uocr).
Entrada: JSON {"engine": "unlimited"|"dharma", "images": [...], "out": "x.json"}
Saida:   JSON {"pages": [markdown_por_pagina], "secs": [segundos_por_pagina]}
Imprime so 1 linha de status."""
import json, os, sys, io, contextlib, tempfile, re, time

cfg = json.load(open(sys.argv[1], encoding="utf-8"))
BASE = os.environ.get("OCR_INTEGRO_HOME", os.path.join(os.path.expanduser("~"), ".cache", "ocr-integro"))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from textq import dedupe_fields


# ---------- Unlimited-OCR 2 (Baidu) ----------
def unlimited_runner():
    import torch
    from transformers import AutoModel, AutoTokenizer
    try:
        from process_unlimitedOCR2 import convert
    except Exception:
        convert = None
    name = os.environ.get("UOCR_MODEL", "baidu/Unlimited-OCR-2")
    tok = AutoTokenizer.from_pretrained(name, trust_remote_code=True)
    model = AutoModel.from_pretrained(name, trust_remote_code=True, use_safetensors=True,
                                      torch_dtype=torch.bfloat16).eval().cuda()
    tmp = tempfile.mkdtemp(prefix="uocr_")

    def to_md(raw):
        if convert:
            try:
                return convert(raw)
            except Exception:
                pass
        t = re.sub(r"\[\d+,\s*\d+,\s*\d+,\s*\d+\]", "", raw)
        t = re.sub(r"</?(PAGE|BLOCK|LEVEL\d|FORK)[^>]*>", "\n", t)
        return re.sub(r"\n{3,}", "\n\n", t).strip()

    def run(img):
        r = model.infer(tok, image_file=img, output_path=tmp, save_results=False)
        torch.cuda.empty_cache()
        return to_md((r[0] if isinstance(r, tuple) else r) or "")
    return run


# ---------- DharmaOCR Lite (Qwen2.5-VL 3B, PT-BR) ----------
SYS = "Você é um assistente de transcrição de documentos, sua função é extrair todo o texto de uma imagem"
ASK = "Extraia todo o texto e todas as tabelas deste documento. Transcreva todas as tabelas caso existam multiplas."


def dharma_to_md(out):
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", out.strip())
    try:
        d = json.loads(s)
    except Exception:
        m = re.search(r'"text"\s*:\s*"(.*)"\s*[,}]', s, re.S)
        if not m:
            return out.strip()
        try:
            d = {"text": json.loads('"' + m.group(1) + '"')}
        except Exception:
            return out.strip()
    text = d.get("text") or ""
    parts = []
    for k, lab in (("header", "cabecalho"), ("margin", "margem")):
        v = (d.get(k) or "").strip()
        if v:
            text = text.replace(v, "", 1) if text.startswith(v) else text  # remove repeticao exata
            parts.append(f"<!-- {lab}: {v} -->")
    parts.append(text.strip())
    f = (d.get("footer") or "").strip()
    if f:
        parts.append(f"<!-- rodape: {f} -->" if f in text else f"\n---\n{f}")
    return "\n\n".join(parts)


def dharma_runner():
    import torch
    from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
    from qwen_vl_utils import process_vision_info
    bf16 = os.path.join(BASE, "models", "dharma-ocr-lite-bf16")   # gerado por dharma_to_bf16.py
    fp8 = os.path.join(BASE, "models", "dharma-ocr-lite")
    name = os.environ.get("DHARMA_MODEL") or next(
        (d for d in (bf16, fp8) if os.path.isfile(os.path.join(d, "config.json"))), "Dharma-AI/Dharma-OCR-LITE")
    kw = {}
    if name != bf16:  # checkpoint FP8: descomprime ao carregar (mais lento em GPUs sem FP8)
        try:
            from transformers import CompressedTensorsConfig
            kw["quantization_config"] = CompressedTensorsConfig(run_compressed=False)
        except Exception:
            pass
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        name, torch_dtype=torch.bfloat16, device_map="cuda", attn_implementation="sdpa", **kw).eval()
    maxpx = int(os.environ.get("DHARMA_MAX_PIXELS", 1600 * 28 * 28))
    proc = AutoProcessor.from_pretrained(name, min_pixels=256 * 28 * 28, max_pixels=maxpx)

    def run(img):
        msgs = [{"role": "system", "content": SYS},
                {"role": "user", "content": [{"type": "image", "image": img}, {"type": "text", "text": ASK}]}]
        text = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        ii, vi = process_vision_info(msgs)
        inp = proc(text=[text], images=ii, videos=vi, padding=True, return_tensors="pt").to(model.device)
        with torch.inference_mode():
            g = model.generate(**inp, max_new_tokens=int(os.environ.get("DHARMA_MAX_TOKENS", 6144)),
                               do_sample=False, repetition_penalty=1.05)
        out = proc.batch_decode(g[:, inp.input_ids.shape[1]:], skip_special_tokens=True)[0]
        torch.cuda.empty_cache()
        return dharma_to_md(out)
    return run


quiet = io.StringIO()
pages, secs = [], []
with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
    run = dharma_runner() if cfg["engine"] == "dharma" else unlimited_runner()
    for img in cfg["images"]:
        t0 = time.time()
        pages.append(run(img))
        secs.append(round(time.time() - t0, 1))

json.dump({"pages": pages, "secs": secs}, open(cfg["out"], "w", encoding="utf-8"), ensure_ascii=False)
print(f"{cfg['engine']} ok {len(pages)} pag")
