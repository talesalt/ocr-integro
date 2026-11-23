# Instala o backend Unlimited-OCR 2 (baidu/Unlimited-OCR-2) num venv isolado.
# Uso: powershell -ExecutionPolicy Bypass -File setup_unlimited.ps1
# Requer: uv, GPU NVIDIA. Baixa torch (~2-3 GB) e, no primeiro uso, os pesos do modelo.
$ErrorActionPreference = "Stop"
$Base = if ($env:OCR_INTEGRO_HOME) { $env:OCR_INTEGRO_HOME } else { Join-Path $HOME ".cache\ocr-integro" }
$Venv = Join-Path $Base "venv-uocr"
New-Item -ItemType Directory -Force $Base | Out-Null

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw "uv nao encontrado. Instale: winget install astral-sh.uv" }

if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
    uv venv --python 3.10 $Venv
}
$Py = Join-Path $Venv "Scripts\python.exe"

# torch com CUDA detectado automaticamente pelo uv; versoes fixadas pelo README do Unlimited-OCR
uv pip install --python $Py --torch-backend auto "torch==2.13.0" torchvision
uv pip install --python $Py pillow "transformers==4.52.1" "huggingface-hub==0.36.0" "tokenizers==0.21.4" "addict==2.4.0" "einops==0.8.2" "easydict==1.13" pymupdf
# o codigo remoto do modelo importa triton; no Windows o pacote e triton-windows
if ($IsWindows -or $env:OS -eq "Windows_NT") { uv pip install --python $Py triton-windows } else { uv pip install --python $Py triton }

# Conversor oficial raw -> Markdown (stdlib only)
$Conv = Join-Path $Base "process_unlimitedOCR2.py"
Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/baidu/Unlimited-OCR/main/utils/process_unlimitedOCR2.py" -OutFile $Conv

& $Py -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available())"
Write-Output "OK: backend instalado em $Venv"
