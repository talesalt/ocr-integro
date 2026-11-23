# ocr-integro

Skill para o [Claude Code](https://claude.com/claude-code) que:

1. **Checa a integridade de textos** por amostragem (poucos tokens): PDF, DOCX, TXT, MD, HTML, JSON, ZIP e imagens. Detecta PDF escaneado sem texto, mojibake/encoding quebrado, lixo de extração, arquivos vazios e JSON/ZIP/DOCX corrompidos.
2. **Faz OCR e salva em Markdown** com [Unlimited-OCR 2](https://github.com/baidu/Unlimited-OCR) (GPU) ou Tesseract. Só as páginas que precisam passam pelo OCR.

Tudo roda por script e imprime uma linha por arquivo, então o modelo quase não gasta tokens.

## Instalação

```powershell
git clone https://github.com/<usuario>/ocr-integro "$HOME\.claude\skills\ocr-integro"
# opcional, para o OCR por GPU:
powershell -ExecutionPolicy Bypass -File "$HOME\.claude\skills\ocr-integro\scripts\setup_unlimited.ps1"
```

Requisitos: Python 3 + `pymupdf` (`pip install pymupdf`). Para OCR: GPU NVIDIA + [uv](https://docs.astral.sh/uv/) (Unlimited-OCR 2) ou [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) com o idioma `por`.

## Uso direto

```bash
python scripts/check_integrity.py minha_pasta/
python scripts/ocr_to_md.py apostila.pdf -o md/
```

Veja `SKILL.md` para todas as opções.

## Licença

MIT. O Unlimited-OCR é da Baidu (MIT) e não está incluído no repositório: o script de setup o baixa.
