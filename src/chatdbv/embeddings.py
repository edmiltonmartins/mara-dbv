# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Edmilton Cabral Martins Junior <junior.edmilton@gmail.com>

"""Embeddings via Gemini (gemini-embedding-001, 768 dimensões) com suporte a
Vertex AI Express Mode (chaves AQ...) e fallback vetorial local quando o endpoint
de embeddings exigir projeto GCP."""
from __future__ import annotations

import hashlib
import re
import time
import unicodedata
from typing import Literal

import numpy as np
from google import genai
from google.genai import types

from .config import Config, criar_cliente_genai

TipoTarefa = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]
LOTE = 50


def normalizar(vetor: list[float] | np.ndarray) -> np.ndarray:
    """gemini-embedding-001 só devolve vetores normalizados em 3072 dims; abaixo disso
    é obrigatório normalizar manualmente (docs oficiais) para a similaridade de cosseno valer."""
    v = np.asarray(vetor, dtype=np.float32)
    norma = np.linalg.norm(v)
    return v / norma if norma > 0 else v


_SINONIMOS_DOMINIO_DBV: tuple[tuple[tuple[str, ...], str], ...] = (
    (("gema", "gemas", "verso", "versos", "versiculo", "versiculos", "biblico", "biblicos", "biblia", "decorar"), "gemas versos versiculos biblicos descoberta espiritual memorizar"),
    (("casamento", "noivo", "noiva", "teto", "honra", "cerimonia"), "casamento noivos guarda honra teto aco omd 009"),
    (("idade", "idades", "aniversario", "corte", "ingresso"), "idades corte etario aniversario ano civil omd 011"),
    (("livro", "livros", "leitura"), "livros leitura clube livro juvenil omd 021"),
    (("calma", "autismo", "autista", "tea", "tdah", "neurodivergente", "girassol", "inclusao"), "espaco calma map inclusao cordao girassol tea"),
    (("rud", "gala", "caqui", "insignia", "insignias", "bolso", "manga"), "rud regulamento uniforme gala insignias bolsos mangas"),
    (("arganel", "prendedor", "lenco"), "lenco arganel prendedor"),
    (("sabado", "desfile", "civico", "7 de setembro"), "desfile sabado civico omd 004"),
    (("apresentar", "apresentacao", "abertura", "comando", "silvos", "apito"), "civismo abertura reuniao capitao apresenta unidade diretor senhor logo vem permissao entrar forma"),
)

_SUFIXOS_PT = (
    "acoes", "acao", "amentos", "amento", "idades", "idade", "mente",
    "arem", "erem", "irem", "ando", "endo", "indo", "aram", "eram", "iram",
    "adas", "ados", "ada", "ado", "avas", "avam", "ava", "iam", "ias",
    "oes", "aes", "ais", "eis", "ois", "ores", "oras", "or",
    "ar", "er", "ir", "am", "em", "os", "as", "es", "a", "o", "e",
)


def radical_pt(palavra: str) -> str:
    """Extrai radical morfológico leve em português (ex.: apresentar/apresentação/apresentam -> apresent)."""
    if len(palavra) <= 4:
        return palavra
    for suf in _SUFIXOS_PT:
        if palavra.endswith(suf) and len(palavra) - len(suf) >= 4:
            return palavra[: -len(suf)]
    return palavra[:6]


def _sem_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _vetor_hashing_local(texto: str, dimensao: int = 768) -> np.ndarray:
    """Vetorizador denso 768d com normalização sem acentos, radicais morfológicos PT-BR,
    n-gramas de subpalavras e expansão semântica de sinônimos do domínio Desbravadores."""
    v = np.zeros(dimensao, dtype=np.float32)
    limpo = _sem_acentos(texto)

    # Expansão de sinônimos do domínio DSA para aproximar vocabulário coloquial do texto normativo
    expansoes: list[str] = []
    for gatilhos, termos_exp in _SINONIMOS_DOMINIO_DBV:
        if any(g in limpo for g in gatilhos):
            expansoes.append(termos_exp)
    if expansoes:
        limpo = f"{limpo} {' '.join(expansoes)}"

    palavras = re.findall(r"[a-z0-9]{2,}", limpo)
    features: list[tuple[str, float]] = []
    for i, p in enumerate(palavras):
        peso_palavra = 2.6 if re.fullmatch(r"(?:d[1-4]|l[1-4]|lm|lma|omd|rud|sgc|dsa|\d{3})", p) else 2.0
        rad = radical_pt(p)
        features.append((f"w:{p}", peso_palavra))
        if len(rad) >= 4:
            features.append((f"st:{rad}", 1.85))
        if i + 1 < len(palavras):
            rad_next = radical_pt(palavras[i + 1])
            features.append((f"b:{p}_{palavras[i + 1]}", 2.4))
            features.append((f"sb:{rad}_{rad_next}", 2.1))
        if len(p) >= 4:
            for j in range(len(p) - 2):
                features.append((f"c:{p[j : j + 3]}", 0.40))

    for token, peso in features:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        h = int.from_bytes(digest, "little")
        idx = h % dimensao
        sinal = 1.0 if ((h >> 32) & 1) == 0 else -1.0
        v[idx] += sinal * peso

    if np.linalg.norm(v) == 0:
        v[0] = 1.0
    return normalizar(v)


_CACHE_CONSULTA: dict[tuple[str, int], np.ndarray] = {}


class Embedder:
    def __init__(self, cfg: Config, client: genai.Client | None = None) -> None:
        self.cfg = cfg
        self.client = client or criar_cliente_genai(cfg)
        chave_aq = (cfg.gemini_api_key or "").strip().upper().startswith("AQ.")
        self.usando_fallback_local = bool(cfg.usa_vertex_express or chave_aq)

    def _embed_lote(self, textos: list[str], tarefa: TipoTarefa) -> list[np.ndarray]:
        if self.usando_fallback_local:
            return [_vetor_hashing_local(t, self.cfg.dimensao) for t in textos]

        espera = 2.0
        for tentativa in range(3):
            try:
                resp = self.client.models.embed_content(
                    model=self.cfg.modelo_embedding,
                    contents=textos,
                    config=types.EmbedContentConfig(
                        task_type=tarefa,
                        output_dimensionality=self.cfg.dimensao,
                    ),
                )
                return [normalizar(e.values) for e in resp.embeddings]
            except Exception as exc:
                if _transitorio(exc) and tentativa < 2:
                    time.sleep(espera)
                    espera *= 2
                    continue
                # Em chaves Vertex AI Express Mode (AQ...), o endpoint :predict de embeddings
                # pode exigir project/location; nesse caso ativamos o vetorizador local 768d
                # para que a indexação e a busca híbrida funcionem sem interrupção.
                if self.cfg.usa_vertex_express or _erro_endpoint_embedding_vertex(exc):
                    self.usando_fallback_local = True
                    return [_vetor_hashing_local(t, self.cfg.dimensao) for t in textos]
                raise
        raise RuntimeError("inalcançável")

    def documentos(self, textos: list[str]) -> list[np.ndarray]:
        saida: list[np.ndarray] = []
        for i in range(0, len(textos), LOTE):
            saida.extend(self._embed_lote(textos[i : i + LOTE], "RETRIEVAL_DOCUMENT"))
        return saida

    def consulta(self, pergunta: str) -> np.ndarray:
        chave = (pergunta.strip().lower(), self.cfg.dimensao)
        if chave in _CACHE_CONSULTA:
            return _CACHE_CONSULTA[chave]
        vetor = self._embed_lote([pergunta], "RETRIEVAL_QUERY")[0]
        if len(_CACHE_CONSULTA) < 256:
            _CACHE_CONSULTA[chave] = vetor
        return vetor


def _transitorio(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(t in msg for t in ("429", "resource_exhausted", "503", "unavailable", "timeout"))


def _erro_endpoint_embedding_vertex(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(
        t in msg
        for t in ("project", "location", "404", "not_found", "permission_denied", "403", "400")
    )
