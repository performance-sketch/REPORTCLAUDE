#!/usr/bin/env python3
"""
Sincroniza data/annotations.json -> const ANNOTATIONS em index.html.

Anotações são marcadores manuais (data + comentário) exibidos como linha
tracejada nos gráficos diários da Rezdy. Não vêm de nenhuma API — são
adicionadas à mão (por este script) ou pelo próprio dashboard (aí ficam
só no localStorage do navegador de quem adicionou).

Run: python scripts/update_annotations.py
"""
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(__file__)
JSON_FILE  = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "data", "annotations.json"))
HTML_FILE  = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "index.html"))


def main():
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        annotations = json.load(f)

    annotations.sort(key=lambda a: a["date"])

    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    novo_json = json.dumps(annotations, ensure_ascii=False, separators=(",", ":"))
    padrao = r"(const ANNOTATIONS\s*=\s*)(\[[\s\S]*?\])(\s*;)"
    novo_html, n = re.subn(padrao, lambda m: m.group(1) + novo_json + m.group(3), html)
    if n == 0:
        sys.exit("ERRO: const ANNOTATIONS não encontrado em index.html (rode a migração uma vez à mão).")

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(novo_html)

    print(f"index.html atualizado com ANNOTATIONS ({len(annotations)} anotações)")


if __name__ == "__main__":
    main()
