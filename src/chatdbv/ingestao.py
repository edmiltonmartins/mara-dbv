# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Edmilton Cabral Martins Junior <junior.edmilton@gmail.com>

"""Pipeline de ingestão de documentos (PDF, Markdown, TXT) com suporte a
precedência normativa de OMDs (Orientações do Ministério de Desbravadores) e Camporis."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .chunking import Chunk, dividir_documento, extrair_paginas
from .db import RepositorioRAG
from .embeddings import Embedder

CATEGORIAS_VALIDAS = (
    "HISTORIA_IDEAIS",
    "UNIFORMES",
    "CLASSES",
    "ADMINISTRATIVO",
    "ESPECIALIDADES",
    "CAMPORI",
    "GERAL",
)

ROTULOS_CATEGORIAS = {
    "TODAS": "Todos os Manuais",
    "HISTORIA_IDEAIS": "História, Ideais e Emblemas",
    "UNIFORMES": "Regulamento de Uniformes (DSA)",
    "CLASSES": "Classes Regulares e Liderança",
    "ADMINISTRATIVO": "Manual Administrativo & Ordem Unida",
    "ESPECIALIDADES": "Especialidades e Mestrados",
    "CAMPORI": "Campori Sul-Americano & Eventos DSA",
    "GERAL": "Geral / Outros",
}


@dataclass(frozen=True)
class ResultadoIngestao:
    arquivo: str
    titulo: str
    categoria: str
    paginas: int
    chunks: int
    ignorado_por_cache: bool


def calcular_sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()


def inferir_categoria(nome_arquivo: str) -> str:
    nome = nome_arquivo.lower()
    if any(p in nome for p in ("campori", "camporí", "boletim")):
        return "CAMPORI"
    if any(p in nome for p in ("especialidade", "mestrado", "biosseguranca", "biossegurança", "omd_017", "omd-17")):
        return "ESPECIALIDADES"
    if any(p in nome for p in ("rud", "uniforme", "insignia", "insígnia", "gala", "lenço", "lenco", "casamento", "departamental")):
        return "UNIFORMES"
    if any(
        p in nome
        for p in (
            "classe",
            "cartao",
            "cartão",
            "cartoes",
            "cartões",
            "amigo",
            "companheiro",
            "pesquisador",
            "pioneiro",
            "excursionista",
            "guia_exploracao",
            "classe_guia",
            "classes",
            "lider",
            "líder",
            "_idades",
            "omd_001",
            "omd_002",
            "omd_005",
            "omd_006",
            "omd_007",
            "omd_011",
            "omd_013",
            "omd_014",
            "omd_015",
            "omd_021",
            "omd021",
            "gemas",
        )
    ):
        return "CLASSES"
    if any(
        p in nome
        for p in (
            "administrativo",
            "ordem_unida",
            "ordem-unida",
            "diretoria",
            "unidade",
            "seguranca",
            "sgc",
            "sabado",
            "sábado",
            "nomes_de_clubes",
            "nomes-de-clubes",
            "espaco_da_calma",
            "espaco-da-calma",
            "orientacoes",
            "orientações",
            "fundando_clube",
            "omd_003",
            "omd_004",
            "omd_010",
            "omd_012",
            "omd_016",
            "omd_018",
            "omd_019",
            "omd_020",
        )
    ):
        return "ADMINISTRATIVO"
    if any(p in nome for p in ("historia", "história", "ideais", "voto", "hino", "triangulo", "simbolos", "símbolos", "joias", "pathfinder")):
        return "HISTORIA_IDEAIS"
    return "GERAL"


def eh_norma_atualizadora(nome_arquivo: str, titulo: str) -> bool:
    comb = f"{nome_arquivo} {titulo}".lower()
    return bool(
        re.search(r"\bomd[\s_\-]?\d+", comb)
        or "retifica" in comb
        or "orientacoes_2026" in comb
        or "orientações para desbravadores e aventureiros 2026" in comb
    )


def formatar_titulo(caminho: Path) -> str:
    nome = caminho.stem
    partes = nome.split("_")
    if partes and partes[0].isdigit():
        partes = partes[1:]
    titulo = " ".join(partes).replace("-", " ").strip()
    # Preserva siglas oficiais em caixa alta
    palavras = []
    for p in titulo.split():
        if p.upper() in {"DSA", "OMD", "RUD", "SGC", "MDA", "MAP", "LMA", "LM", "VI", "UCB"}:
            palavras.append(p.upper())
        else:
            palavras.append(p.capitalize())
    return " ".join(palavras) if palavras else caminho.stem


def ingerir_arquivo(
    caminho: Path,
    repo: RepositorioRAG,
    embedder: Embedder,
    categoria: str | None = None,
    titulo: str | None = None,
    forcar: bool = False,
) -> ResultadoIngestao:
    sha = calcular_sha256(caminho)
    nome_relativo = caminho.name
    cat = categoria if categoria in CATEGORIAS_VALIDAS else inferir_categoria(nome_relativo)
    tit = titulo or formatar_titulo(caminho)

    if not forcar and repo.manual_ja_indexado(nome_relativo, sha):
        return ResultadoIngestao(
            arquivo=nome_relativo,
            titulo=tit,
            categoria=cat,
            paginas=0,
            chunks=0,
            ignorado_por_cache=True,
        )

    paginas = extrair_paginas(caminho)
    chunks = dividir_documento(paginas)
    if not chunks:
        raise ValueError(f"Nenhum texto extraído do arquivo '{nome_relativo}'.")

    # Carimba normas retificadoras (OMDs / Diretrizes 2026) ou contexto do manual em cada chunk
    if eh_norma_atualizadora(nome_relativo, tit):
        selo = f"[NORMA ATUALIZADORA OFICIAL DSA — {tit}: prevalece sobre edições anteriores]\n"
    else:
        selo = f"[{tit}]\n"
    chunks = [
        Chunk(pagina=c.pagina, ordem=c.ordem, texto=f"{selo}{c.texto}")
        for c in chunks
    ]

    vetores = embedder.documentos([c.texto for c in chunks])
    repo.salvar_manual_com_chunks(
        titulo=tit,
        arquivo=nome_relativo,
        categoria=cat,
        sha256=sha,
        paginas=len(paginas),
        chunks=chunks,
        vetores=vetores,
    )
    return ResultadoIngestao(
        arquivo=nome_relativo,
        titulo=tit,
        categoria=cat,
        paginas=len(paginas),
        chunks=len(chunks),
        ignorado_por_cache=False,
    )


def ingerir_pasta(
    pasta: Path,
    repo: RepositorioRAG,
    embedder: Embedder,
    forcar: bool = False,
) -> list[ResultadoIngestao]:
    repo.inicializar_esquema()
    arquivos = sorted(
        p
        for p in pasta.iterdir()
        if p.is_file() and p.suffix.lower() in (".pdf", ".md", ".txt")
    )
    resultados: list[ResultadoIngestao] = []
    for arq in arquivos:
        resultados.append(ingerir_arquivo(arq, repo, embedder, forcar=forcar))
    return resultados
