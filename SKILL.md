---
name: ocr-integro
description: Checa se textos/documentos estão íntegros por amostragem (PDF, DOCX, TXT, MD, JSON, ZIP, imagens) e converte PDFs escaneados/imagens em Markdown via OCR (Unlimited-OCR 2 na GPU, ou Tesseract). Use quando o usuário pedir para verificar integridade, checar se um texto está corrompido/ilegível, se um PDF tem texto ou precisa de OCR, ou para fazer OCR / extrair texto de PDF ou imagem para .md. Tudo por script, gastando o mínimo de tokens.
---

# ocr-integro

Tudo é feito por script. **Não leia os documentos nem as saídas .md inteiras**: confie nas linhas de status dos scripts. Só abra trechos se o usuário pedir.

`S` = pasta `scripts/` desta skill (ex.: `~/.claude/skills/ocr-integro/scripts`). Rode com `py -3` (Windows) ou `python3`.

## 1. Checar integridade (amostragem)

```bash
py -3 "$S/check_integrity.py" <arquivos ou pastas> [-n 3] [--chars 1200] [-v]
```

- Lê só ~3 amostras por arquivo (início, meio, fim) e imprime **1 linha por arquivo** + `RESUMO`.
- Vereditos: `OK`, `SUSPEITO` (mojibake, lixo, palavras coladas, não-UTF-8), `PRECISA_OCR` (PDF sem camada de texto/escaneado, imagem), `CORROMPIDO` (não abre, 0 bytes, JSON/ZIP/DOCX inválido).
- Código-fonte (.js, .css, .py) e tipos desconhecidos são ignorados (`--all` para listá-los).
- Exit 0 = tudo OK.

## 2. OCR → Markdown

```bash
py -3 "$S/ocr_to_md.py" <pdf|imagem|pasta> [-o saida/] [--engine auto|unlimited|tesseract] [--force-ocr] [--lang por]
```

- Grava `<nome>.md` ao lado do arquivo (ou em `-o`), com `<!-- pagina N -->` entre páginas.
- Páginas com texto bom são **extraídas direto** (sem OCR); só as ruins/escaneadas vão para OCR. `--force-ocr` força OCR em tudo.
- `auto`: Unlimited-OCR 2 se o backend estiver instalado, senão Tesseract (`--lang por`).
- Imprime 1 linha: `OK <md> paginas=N ocr=K motor=X qualidade=...`.

Fluxo típico: rode o passo 1; para os `PRECISA_OCR`/`SUSPEITO` que forem PDF/imagem, rode o passo 2; depois rode o passo 1 de novo sobre os `.md` gerados para confirmar.

## Instalar o backend Unlimited-OCR 2 (uma vez, GPU NVIDIA)

```powershell
powershell -ExecutionPolicy Bypass -File "$S/setup_unlimited.ps1"
```

Cria um venv Python 3.10 em `~/.cache/ocr-integro/venv-uocr` (torch CUDA + transformers 4.52.1) e baixa o conversor oficial raw→Markdown. Os pesos (`baidu/Unlimited-OCR-2`) vêm do Hugging Face no primeiro uso. Sem GPU, use `--engine tesseract`.
