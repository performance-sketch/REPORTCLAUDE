"""
log_seguro.py — esconde tokens e chaves em tudo que o script imprime.

Os logs do GitHub Actions deste repositório são públicos. O GitHub só mascara os valores
cadastrados como secrets; tokens derivados (ex.: token de página da Meta) e chaves que aparecem
em URLs de erro vazariam. Importar este módulo e chamar ativar() filtra stdout e stderr,
inclusive tracebacks.
"""

import re
import sys

_PADRAO = re.compile(r"(access_token|apiKey|api_key|appsecret_proof|client_secret|input_token|fb_exchange_token)=[^&\s'\"<>]+")


def limpar(texto):
    return _PADRAO.sub(r"\1=***", str(texto))


class _Filtro:
    def __init__(self, destino):
        self._destino = destino

    def write(self, texto):
        return self._destino.write(limpar(texto))

    def __getattr__(self, nome):
        return getattr(self._destino, nome)


def ativar():
    if not isinstance(sys.stdout, _Filtro):
        sys.stdout = _Filtro(sys.stdout)
    if not isinstance(sys.stderr, _Filtro):
        sys.stderr = _Filtro(sys.stderr)
