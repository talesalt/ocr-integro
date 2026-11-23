# ocr-integro

Skill para o [Claude Code](https://claude.com/claude-code) que:

1. **Checa a integridade de textos** por amostragem, gastando poucos tokens: PDF, DOCX, TXT, MD, HTML, JSON, ZIP e imagens. Detecta PDF escaneado sem texto, mojibake/encoding quebrado, lixo de extração, arquivos vazios e JSON/ZIP/DOCX corrompidos.
2. **Faz OCR e salva em Markdown**, escolhendo o motor a partir de amostras do próprio documento. As opções são [Tesseract](https://github.com/tesseract-ocr/tesseract), [DharmaOCR Lite](https://huggingface.co/Dharma-AI/Dharma-OCR-LITE) e [Unlimited-OCR 2](https://github.com/baidu/Unlimited-OCR). Só passam pelo OCR as páginas que precisam.

Tudo roda por script e imprime uma linha por arquivo.

## Como o motor é escolhido

O Tesseract lê 1–2 páginas de amostra e mede a confiança média:

| Situação nas amostras | Motor |
|---|---|
| confiança ≥ 80 (scan limpo) | Tesseract |
| scan difícil, português | DharmaOCR Lite |
| scan difícil, outro idioma / ≥ 40 páginas | Unlimited-OCR 2 |

### Benchmark que embasou a regra

Apostila de Psicologia Social (PT-BR), páginas 1, 5 e 9, num total de 967 palavras. O gabarito é a camada de texto do PDF. GPU: RTX 3080 10 GB, Windows.

| Motor | WER limpo | WER scan ruim* | acentos (ruim) | s/pág |
|---|---|---|---|---|
| Tesseract 5 (`por`) | 0,072 | 0,817 | 29% | ~1 |
| DharmaOCR Lite (bf16) | 0,073 | **0,093** | 97% | 66 |
| Unlimited-OCR 2 | **0,066** | 0,102 | 96% | 105 |

\* `--degrade`: 110 dpi, rotação de 1,2°, desfoque, ruído e JPEG q35.

Em scan limpo, os três empatam e o Tesseract é cerca de 60× mais rápido. Em scan ruim, o Tesseract colapsa, e o Dharma é o mais preciso e o mais rápido entre os modelos de GPU. O Unlimited-OCR não foi testado em documentos longos nem em outros idiomas, que é onde ele deveria se destacar.

Notas de implementação:
- O Dharma repete notas de rodapé e cabeçalhos no campo `footer`/`header`. O `dedupe_fields` remove essas repetições, e isso derrubou o WER de 0,173 para 0,073.
- O checkpoint do Dharma é FP8 (`compressed-tensors`). Em GPUs sem FP8 nativo (RTX 20/30xx), ele é convertido uma vez para bf16, o que deixa a geração cerca de 2× mais rápida.
- No Windows, os pesos são baixados com `local_dir`, porque os symlinks do cache do Hugging Face falham sem o modo desenvolvedor.

## Instalação

```powershell
git clone https://github.com/talesalt/ocr-integro "$HOME\.claude\skills\ocr-integro"
pip install pymupdf
# motores de GPU (opcional; ~25 GB de downloads):
powershell -ExecutionPolicy Bypass -File "$HOME\.claude\skills\ocr-integro\scripts\setup_gpu.ps1"
```

Requisitos: Python 3 + `pymupdf`; Tesseract com o idioma `por`. Para a GPU: NVIDIA com ~10 GB e [uv](https://docs.astral.sh/uv/).

## Licenças

- Código desta skill: MIT.
- Unlimited-OCR 2: MIT (Baidu). Não está incluído no repositório; o setup baixa.
- **DharmaOCR Lite: licença não comercial da DHARMA-AI S.A. que exclui uso por ou para entidades públicas, incluindo universidades públicas, sem licença escrita.** Não está incluído; o setup baixa. Para pular: `$env:OCR_INTEGRO_SKIP_DHARMA="1"`.
