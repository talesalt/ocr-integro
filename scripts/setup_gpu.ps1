# Instala os motores de GPU em venvs isolados:
#   venv-uocr   -> Unlimited-OCR 2 (Baidu, MIT)          transformers 4.52.1
#   venv-dharma -> DharmaOCR Lite (Dharma-AI, nao-comercial) transformers 4.57.3
# Uso: powershell -ExecutionPolicy Bypass -File setup_gpu.ps1
#      $env:OCR_INTEGRO_SKIP_DHARMA="1"   para nao instalar o Dharma
#      $env:OCR_INTEGRO_SKIP_UNLIMITED="1" para nao instalar o Unlimited
# Requer: uv e GPU NVIDIA (~10 GB VRAM). Downloads: torch ~2.5 GB por venv, modelos ~5-7 GB cada.
$ErrorActionPreference = "Stop"
$Base = if ($env:OCR_INTEGRO_HOME) { $env:OCR_INTEGRO_HOME } else { Join-Path $HOME ".cache\ocr-integro" }
New-Item -ItemType Directory -Force (Join-Path $Base "models") | Out-Null
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw "uv nao encontrado. Instale: winget install astral-sh.uv" }

function New-Venv($name) {
    $v = Join-Path $Base $name
    if (-not (Test-Path (Join-Path $v "Scripts\python.exe"))) { uv venv --python 3.10 $v }
    $py = Join-Path $v "Scripts\python.exe"
    uv pip install --python $py --torch-backend auto "torch==2.13.0" torchvision
    return $py
}

if (-not $env:OCR_INTEGRO_SKIP_UNLIMITED) {
    $Py = New-Venv "venv-uocr"
    uv pip install --python $Py pillow "transformers==4.52.1" "huggingface-hub==0.36.0" "tokenizers==0.21.4" "addict==2.4.0" "einops==0.8.2" "easydict==1.13"
    # o codigo remoto do modelo importa triton; no Windows o pacote e triton-windows
    uv pip install --python $Py triton-windows
    # conversor oficial raw -> Markdown (stdlib). Os pesos baixam no primeiro uso (cache do HF).
    Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/baidu/Unlimited-OCR/main/utils/process_unlimitedOCR2.py" -OutFile (Join-Path $Base "process_unlimitedOCR2.py")
    & $Py -c "import torch;print('unlimited: torch',torch.__version__,'cuda',torch.cuda.is_available())"
}

# DharmaOCR Lite: LICENCA NAO-COMERCIAL que EXCLUI uso por/para entidades publicas
# (inclui universidades publicas) sem licenca escrita da DHARMA-AI S.A. Leia antes de usar.
if (-not $env:OCR_INTEGRO_SKIP_DHARMA) {
    $Py = New-Venv "venv-dharma"
    uv pip install --python $Py pillow "transformers==4.57.3" compressed-tensors qwen-vl-utils accelerate
    # local_dir evita os symlinks do cache do HF (falham no Windows sem modo desenvolvedor)
    $Fp8 = Join-Path $Base "models\dharma-ocr-lite"
    $Bf16 = Join-Path $Base "models\dharma-ocr-lite-bf16"
    & $Py -c "import sys; from huggingface_hub import snapshot_download as s; s('Dharma-AI/Dharma-OCR-LITE', local_dir=sys.argv[1], allow_patterns=['*.json','*.safetensors','*.txt','*.jinja'])" $Fp8
    # checkpoint e FP8; em GPUs sem FP8 nativo (RTX 20/30xx) bf16 puro e ~2x mais rapido
    if (-not (Test-Path (Join-Path $Bf16 "config.json"))) {
        & $Py (Join-Path $PSScriptRoot "dharma_to_bf16.py") $Fp8 $Bf16
    }
    if ($LASTEXITCODE -eq 0) { Set-Content -Path (Join-Path $Base "dharma.ok") -Value $Bf16 }
}
Write-Output "OK: motores instalados em $Base"
