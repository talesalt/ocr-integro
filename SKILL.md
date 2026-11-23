---
name: ocr-integro
description: Checa se textos/documentos estão íntegros por amostragem (PDF, DOCX, TXT, MD, JSON, ZIP, imagens) e converte PDFs escaneados/imagens em Markdown via OCR, escolhendo o motor pelas amostras (Tesseract para scans limpos, DharmaOCR para scans difíceis em português, Unlimited-OCR para outros idiomas/documentos longos). Use quando o usuário pedir para verificar integridade, checar se um texto está corrompido/ilegível, se um PDF tem texto ou precisa de OCR, ou para fazer OCR / extrair texto de PDF ou imagem para .md. Tudo por script, gastando o mínimo de tokens.
---

# ocr-integro

Tudo é feito por script. **Não leia os documentos nem as saídas .md inteiras**: confie nas linhas de status. Só abra trechos se o usuário pedir.

`S` = pasta `scripts/` desta skill (ex.: `~/.claude/skills/ocr-integro/scripts`). Rode com `py -3` (Windows) ou `python3`.

## 1. Checar integridade (amostragem)

```bash
py -3 "$S/check_integrity.py" <arquivos ou pastas> [-n 3] [--chars 1200] [-v]
```

- Lê ~3 amostras por arquivo (início, meio, fim); imprime **1 linha por arquivo** + `RESUMO`. Exit 0 = tudo OK.
- `OK` | `SUSPEITO` (mojibake, lixo, palavras coladas, não-UTF-8) | `PRECISA_OCR` (PDF escaneado, imagem) | `CORROMPIDO` (não abre, 0 bytes, JSON/ZIP/DOCX inválido).
- Código-fonte e tipos desconhecidos são ignorados (`--all` lista).

## 2. OCR → Markdown

```bash
py -3 "$S/ocr_to_md.py" <pdf|imagem|pasta> [-o saida/] [--engine auto|dharma|unlimited|tesseract] [--force-ocr] [--lang por]
```

- Grava `<nome>.md` (ao lado ou em `-o`) com `<!-- pagina N -->`. Páginas com texto bom são extraídas direto, sem OCR.
- `auto` decide pelas **amostras**: o Tesseract lê 1–2 páginas e mede a confiança média.
  - confiança ≥ 80 (scan limpo) → **tesseract** (mesma qualidade, ~50× mais rápido)
  - scan difícil em português → **dharma** (melhor WER e acentos; ~1 min/pág na GPU)
  - scan difícil em outro idioma, ou ≥ 40 páginas fora do PT → **unlimited**
- Saída: `OK <md> paginas=N ocr=K motor=X (motivo) qualidade=...`. A GPU leva ~1 min/página: rode em segundo plano em documentos grandes.

Fluxo: passo 1 → passo 2 nos `PRECISA_OCR`/`SUSPEITO` → passo 1 de novo nos `.md`.

## 3. Comparar motores (opcional)

```bash
py -3 "$S/bench_ocr.py" base_digital.pdf [-k 3] [--degrade] [--engines tesseract,dharma,unlimited]
```

Usa a camada de texto de um PDF digital como gabarito; `--degrade` simula scan ruim. Imprime WER, % de acentos e s/pág por motor, e a recomendação. Resultados ficam em cache.

## Instalar os motores de GPU (uma vez)

```powershell
powershell -ExecutionPolicy Bypass -File "$S/setup_gpu.ps1"
```

Cria `~/.cache/ocr-integro/venv-uocr` e `venv-dharma`, baixa os modelos e converte o Dharma para bf16. Sem GPU, só o Tesseract (`por`) é usado.

⚠️ **Licença do DharmaOCR**: não comercial, e **exclui uso por/para entidades públicas, inclusive universidades públicas**, sem licença escrita da Dharma-AI. Avise o usuário; para pular: `$env:OCR_INTEGRO_SKIP_DHARMA="1"` antes do setup, ou `--engine unlimited`.
