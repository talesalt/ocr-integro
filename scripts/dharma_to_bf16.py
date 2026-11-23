"""Converte 1x o DharmaOCR Lite (FP8 compressed-tensors) para bf16 puro.
Motivo: em GPUs sem FP8 nativo (RTX 20/30xx) o caminho compressed-tensors tem overhead
por camada que deixa a geracao ~5x mais lenta. Roda no venv-dharma.
Uso: python dharma_to_bf16.py <dir_fp8> <dir_bf16>"""
import json, os, shutil, sys, torch
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor, CompressedTensorsConfig

src, dst = sys.argv[1], sys.argv[2]
m = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    src, torch_dtype=torch.bfloat16, device_map="cpu",
    quantization_config=CompressedTensorsConfig(run_compressed=False))
sd = {k: v.contiguous() for k, v in m.state_dict().items() if not k.endswith(("_scale", "_zero_point"))}
cfg = json.load(open(os.path.join(src, "config.json"), encoding="utf-8"))
cfg.pop("quantization_config", None)
cfg["torch_dtype"] = "bfloat16"
os.makedirs(dst, exist_ok=True)
from transformers import AutoConfig
conf = AutoConfig.from_pretrained(src)
if hasattr(conf, "quantization_config"):
    del conf.quantization_config
clean = Qwen2_5_VLForConditionalGeneration._from_config(conf, torch_dtype=torch.bfloat16)
missing, unexpected = clean.load_state_dict(sd, strict=False)
clean.save_pretrained(dst, safe_serialization=True, max_shard_size="4GB")
json.dump(cfg, open(os.path.join(dst, "config.json"), "w", encoding="utf-8"), indent=2)
for f in os.listdir(src):  # tokenizer/processor/template
    if f.endswith((".json", ".txt", ".jinja")) and not f.startswith(("config", "model.safetensors")):
        shutil.copy(os.path.join(src, f), dst)
print(f"bf16 ok missing={len(missing)} unexpected={len(unexpected)}")
