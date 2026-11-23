"""Metricas baratas de qualidade de texto (stdlib). Compartilhado pelos scripts."""
import re

STOP = set("""de a o que e do da em um para é com não uma os no se na por mais as dos como mas
foi ao ele das tem à seu sua ou ser quando muito há nos já está eu também só pelo pela até isso
ela entre era depois sem mesmo aos ter seus quem nas me esse eles estão você tinha foram essa num
nem suas meu às minha têm numa pelos elas havia seja qual será nós tenho lhe deles essas esses
pelas este fosse dele the of and to in is that for it on with as are this by be""".split())
MOJIBAKE = re.compile(r"Ã[\x80-\xbf§£¡©ª³µ¢]|â€|Â[\xa0-\xbf]|ï¿½")
WORD = re.compile(r"[A-Za-zÀ-ÿ]+")


def quality(text: str) -> dict:
    """Retorna metricas e um veredito: OK, SUSPEITO, SEM_TEXTO."""
    t = text or ""
    n = len(t.strip())
    if n < 40:
        return {"chars": n, "verdict": "SEM_TEXTO", "why": "pouco ou nenhum texto"}
    letters = sum(c.isalpha() for c in t)
    nonspace = sum(not c.isspace() for c in t) or 1
    words = WORD.findall(t)
    nw = len(words) or 1
    stop = sum(w.lower() in STOP for w in words) / nw
    avgw = sum(map(len, words)) / nw
    repl = t.count("�")
    moj = len(MOJIBAKE.findall(t))
    ctrl = sum(1 for c in t if ord(c) < 32 and c not in "\n\r\t\f")
    singles = sum(len(w) == 1 for w in words) / nw
    m = {"chars": n, "letras": round(letters / nonspace, 2), "stop": round(stop, 2),
         "palavra_media": round(avgw, 1), "ufffd": repl, "mojibake": moj, "ctrl": ctrl}
    why = []
    if repl or ctrl > 3:
        why.append("caracteres invalidos")
    if moj > 2:
        why.append("encoding quebrado (mojibake)")
    if letters / nonspace < 0.55:
        why.append("poucas letras (lixo/simbolos)")
    if nw > 30 and stop < 0.08:
        why.append("nao parece lingua natural")
    if avgw > 12 or (nw > 30 and singles > 0.35):
        why.append("palavras coladas/fragmentadas")
    m["verdict"] = "SUSPEITO" if why else "OK"
    if why:
        m["why"] = "; ".join(why)
    return m
