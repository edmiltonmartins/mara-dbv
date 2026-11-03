"""Extração de texto e divisão em chunks.

Regra de projeto: um chunk NUNCA atravessa páginas. Assim a citação de página
("Manual X, pág. 42") é sempre exata, requisito central do Chat DBV.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

TAMANHO_ALVO = 1000      # caracteres por chunk (aprox. 200-250 tokens em PT-BR)
SOBREPOSICAO = 150       # caracteres repetidos entre chunks consecutivos da mesma página


@dataclass(frozen=True)
class Pagina:
    numero: int          # 1-based
    texto: str


@dataclass(frozen=True)
class Chunk:
    pagina: int
    ordem: int
    texto: str


def limpar_texto(texto: str) -> str:
    """Normaliza quebras de linha típicas de PDF preservando parágrafos."""
    texto = texto.replace("\r", "")
    texto = re.sub(r"-\n(?=[a-zà-ú])", "", texto)          # palavra hifenizada na quebra de linha
    texto = re.sub(r"(?<!\n)\n(?!\n)", " ", texto)         # quebra simples -> espaço
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def extrair_paginas(caminho: Path) -> list[Pagina]:
    sufixo = caminho.suffix.lower()
    if sufixo == ".pdf":
        leitor = PdfReader(str(caminho))
        return [
            Pagina(i, limpar_texto(p.extract_text() or ""))
            for i, p in enumerate(leitor.pages, start=1)
        ]
    if sufixo in (".txt", ".md"):
        bruto = caminho.read_text(encoding="utf-8")
        partes = re.split(r"(?m)^---\s*PAGINA\s+(\d+)\s*---\s*$", bruto)
        if len(partes) > 1:
            paginas: list[Pagina] = []
            if partes[0].strip():
                paginas.append(Pagina(1, limpar_texto(partes[0])))
            for idx in range(1, len(partes), 2):
                num = int(partes[idx])
                conteudo = limpar_texto(partes[idx + 1]) if idx + 1 < len(partes) else ""
                if conteudo:
                    paginas.append(Pagina(num, conteudo))
            return paginas
        return [Pagina(1, limpar_texto(bruto))]
    raise ValueError(f"Formato não suportado: {caminho.name}")


def _quebrar_paragrafo_longo(paragrafo: str, tamanho: int) -> list[str]:
    """Quebra um parágrafo gigante por sentenças, sem cortar palavras."""
    sentencas = re.split(r"(?<=[.!?;:])\s+", paragrafo)
    partes: list[str] = []
    atual = ""
    for s in sentencas:
        while len(s) > tamanho:                            # sentença única maior que o limite
            corte = s.rfind(" ", 0, tamanho)
            corte = corte if corte > 0 else tamanho
            partes.append(s[:corte].strip())
            s = s[corte:].strip()
        if atual and len(atual) + 1 + len(s) > tamanho:
            partes.append(atual)
            atual = s
        else:
            atual = f"{atual} {s}".strip()
    if atual:
        partes.append(atual)
    return partes


def dividir_pagina(
    pagina: Pagina,
    ordem_inicial: int = 0,
    tamanho: int = TAMANHO_ALVO,
    sobreposicao: int = SOBREPOSICAO,
) -> list[Chunk]:
    if not pagina.texto:
        return []

    unidades: list[str] = []
    for par in (p.strip() for p in pagina.texto.split("\n\n")):
        if not par:
            continue
        unidades.extend(_quebrar_paragrafo_longo(par, tamanho) if len(par) > tamanho else [par])

    blocos: list[str] = []
    atual = ""
    for u in unidades:
        if atual and len(atual) + 2 + len(u) > tamanho:
            blocos.append(atual)
            # sobreposição: reaproveita o final do bloco anterior, sem cortar palavra
            cauda = atual[-sobreposicao:] if sobreposicao else ""
            if cauda and " " in cauda:
                cauda = cauda.split(" ", 1)[1]
            atual = f"{cauda} {u}".strip() if cauda else u
        else:
            atual = f"{atual}\n\n{u}".strip() if atual else u
    if atual:
        blocos.append(atual)

    return [Chunk(pagina.numero, ordem_inicial + i, b) for i, b in enumerate(blocos)]


def dividir_documento(paginas: list[Pagina]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for pagina in paginas:
        chunks.extend(dividir_pagina(pagina, ordem_inicial=len(chunks)))
    return chunks
