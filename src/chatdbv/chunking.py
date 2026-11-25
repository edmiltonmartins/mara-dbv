# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Edmilton Cabral Martins Junior <junior.edmilton@gmail.com>

"""Extração estruturada de texto (PyMuPDF + fallback pypdf) e divisão em chunks.

Regra de projeto: um chunk NUNCA atravessa páginas. Assim a citação de página
("Manual X, pág. 42") é sempre exata, requisito central da Mara.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

try:
    import pymupdf as _fitz  # PyMuPDF >= 1.25
except Exception:  # pragma: no cover
    try:
        import fitz as _fitz
    except Exception:
        _fitz = None

TAMANHO_ALVO = 1100      # caracteres por chunk (~220-280 tokens em PT-BR)
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
    """Normaliza quebras de linha típicas de texto corrido preservando parágrafos."""
    texto = texto.replace("\r", "")
    texto = re.sub(r"-\n(?=[a-zà-ú])", "", texto)          # palavra hifenizada na quebra de linha
    texto = re.sub(r"(?<!\n)\n(?!\n)", " ", texto)         # quebra simples -> espaço
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def limpar_texto_estruturado_pdf(texto: str) -> str:
    """Limpa texto extraído de PDFs diagramados preservando listas numeradas,
    marcadores (bullets), cabeçalhos e linhas de tabela."""
    texto = texto.replace("\r", "").replace("\x00", "")
    # Desfaz hifenização de fim de linha
    texto = re.sub(r"-\n(?=[a-zà-ú])", "", texto)

    linhas_brutas = [re.sub(r"[ \t]+", " ", ln).strip() for ln in texto.split("\n")]
    padrao_item_lista = re.compile(
        r"^(?:[-•▪◦*]|(?:\d{1,2}|[a-zA-Z]|[IVXLC]{1,5})[\.\)\-]\s|\|)"
    )

    blocos: list[str] = []
    acumulador = ""
    for ln in linhas_brutas:
        if not ln:
            if acumulador:
                blocos.append(acumulador)
                acumulador = ""
            continue
        # Ignora numeração isolada de rodapé/cabeçalho (ex.: "12" ou "Página 12")
        if re.fullmatch(r"(?:p[áa]g(?:ina)?\.?\s*)?\d{1,4}", ln, flags=re.IGNORECASE):
            continue

        eh_lista_ou_tabela = bool(padrao_item_lista.match(ln)) or ln.isupper()
        if eh_lista_ou_tabela:
            if acumulador:
                blocos.append(acumulador)
                acumulador = ""
            blocos.append(ln)
        else:
            acumulador = f"{acumulador} {ln}".strip() if acumulador else ln

    if acumulador:
        blocos.append(acumulador)

    saida = "\n\n".join(blocos)
    saida = re.sub(r"\n{3,}", "\n\n", saida)
    return saida.strip()


def _extrair_pdf_pymupdf(caminho: Path) -> list[Pagina]:
    paginas: list[Pagina] = []
    with _fitz.open(str(caminho)) as doc:
        for idx, page in enumerate(doc, start=1):
            blocos_raw = page.get_text("blocks") or []
            # Ordena blocos de texto (tipo 0) de cima para baixo, esquerda para direita
            blocos_txt = sorted(
                (b for b in blocos_raw if len(b) >= 7 and b[6] == 0 and str(b[4]).strip()),
                key=lambda b: (round(b[1] / 12.0), round(b[0] / 20.0)),
            )
            bruto = "\n\n".join(str(b[4]).strip() for b in blocos_txt)
            limpo = limpar_texto_estruturado_pdf(bruto)
            if limpo:
                paginas.append(Pagina(idx, limpo))
    return paginas


def extrair_paginas(caminho: Path) -> list[Pagina]:
    sufixo = caminho.suffix.lower()
    if sufixo == ".pdf":
        if _fitz is not None:
            try:
                pags = _extrair_pdf_pymupdf(caminho)
                if pags:
                    return pags
            except Exception:
                pass
        leitor = PdfReader(str(caminho))
        return [
            Pagina(i, limpar_texto_estruturado_pdf(p.extract_text() or ""))
            for i, p in enumerate(leitor.pages, start=1)
            if (p.extract_text() or "").strip()
        ]
    if sufixo in (".txt", ".md"):
        bruto = caminho.read_text(encoding="utf-8")
        partes = re.split(r"(?m)^---\s*PAGINA\s+(\d+)\s*---\s*$", bruto)
        if len(partes) > 1:
            paginas: list[Pagina] = []
            if partes[0].strip():
                paginas.append(Pagina(1, limpar_texto_estruturado_pdf(partes[0])))
            for idx in range(1, len(partes), 2):
                num = int(partes[idx])
                conteudo = limpar_texto_estruturado_pdf(partes[idx + 1]) if idx + 1 < len(partes) else ""
                if conteudo:
                    paginas.append(Pagina(num, conteudo))
            return paginas
        return [Pagina(1, limpar_texto_estruturado_pdf(bruto))]
    raise ValueError(f"Formato não suportado: {caminho.name}")


def _quebrar_paragrafo_longo(paragrafo: str, tamanho: int) -> list[str]:
    """Quebra um parágrafo gigante por sentenças, sem cortar palavras."""
    sentencas = re.split(r"(?<=[.!?;:])\s+", paragrafo)
    partes: list[str] = []
    atual = ""
    for s in sentencas:
        while len(s) > tamanho:
            corte = s.rfind(" ", 0, tamanho)
            corte = corte if corte > 0 else tamanho
            partes.append(s[:corte].strip())
            s = s[corte:].strip()
        if atual and len(atual) + 1 + len(s) > tamanho:
            partes.append(atual)
            atual = s
        else:
            atual = f"{atual} {s}".strip() if atual else u if False else f"{atual} {s}".strip()
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
