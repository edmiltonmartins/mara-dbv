"""Camada de persistência e Busca Híbrida (Semântica + Full-Text com Reciprocal Rank Fusion).

Suporta dois backends com a mesma interface:
1. PostgreSQL + pgvector (`PostgresRepositorio`) — arquitetura alvo definitiva, compartilhada
   com a futura migração para Java / Spring AI (`sql/001_init.sql`).
2. SQLite + NumPy (`SqliteRepositorio`) — fallback automático local para testar a PoC
   imediatamente mesmo antes de subir uma instância PostgreSQL.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from .chunking import Chunk
from .config import RAIZ, Config

RRF_K = 60  # constante padrão de Reciprocal Rank Fusion


def filtrar_trechos_relevantes(
    candidatos: list["TrechoRecuperado"],
    top_k: int = 6,
) -> list["TrechoRecuperado"]:
    """Filtra dinamicamente apenas os trechos realmente relevantes à pergunta,
    evitando retornar sempre `top_k` trechos fixos com ruído de baixa relação."""
    if not candidatos:
        return []

    recorte = candidatos[:top_k]
    melhor_sim = max(t.similaridade for t in recorte)
    limiar_rrf_lexical = (1.0 / (RRF_K + 1)) + 1e-6
    tem_algum_lexical = any(t.score_rrf > limiar_rrf_lexical for t in recorte)

    relevantes: list[TrechoRecuperado] = []
    for idx, t in enumerate(recorte):
        tem_lexical = t.score_rrf > limiar_rrf_lexical
        # Descarta trechos sem match lexical e com similaridade muito baixa
        if not tem_lexical and t.similaridade < 0.45:
            continue

        if tem_algum_lexical:
            # Se há trechos que batem nos termos da pergunta, mantém quem tem match lexical
            # com similaridade mínima aceitável ou quem tem similaridade semântica muito próxima do topo
            if tem_lexical and (idx == 0 or t.similaridade >= 0.45):
                relevantes.append(t)
            elif not tem_lexical and t.similaridade >= max(0.66, melhor_sim - 0.05):
                relevantes.append(t)
        else:
            # Consulta puramente conceitual (sem palavras exatas): mantém apenas a faixa de topo
            if t.similaridade >= 0.50 and t.similaridade >= melhor_sim - 0.05:
                relevantes.append(t)

    # Se pelo menos o 1º colocado tinha cara de resposta válida (>= 0.48 ou match lexical), garante retorno
    if not relevantes and (recorte[0].similaridade >= 0.48 or tem_algum_lexical):
        return [recorte[0]]

    return relevantes


@dataclass(frozen=True)
class ManualInfo:
    id: int
    titulo: str
    arquivo: str
    categoria: str
    sha256: str
    paginas: int
    total_chunks: int = 0


@dataclass(frozen=True)
class TrechoRecuperado:
    chunk_id: int
    manual_titulo: str
    arquivo: str
    categoria: str
    pagina: int
    texto: str
    similaridade: float
    score_rrf: float


@dataclass(frozen=True)
class FeedbackInfo:
    id: int
    pergunta: str
    resposta: str
    positivo: bool
    criado_em: str


@dataclass(frozen=True)
class ConversaResumo:
    id: str
    device_id: str
    titulo: str
    modo: str
    categoria: str
    last_interaction_id: str | None
    atualizado_em: str


def serializar_mensagens(mensagens: list[dict]) -> str:
    """Converte a lista de mensagens (incluindo TrechoRecuperado) em JSON seguro."""
    saida: list[dict] = []
    for m in mensagens:
        item = {
            "role": m.get("role", "user"),
            "content": m.get("content", ""),
            "pergunta": m.get("pergunta", ""),
        }
        trechos = m.get("trechos") or []
        item["trechos"] = [
            {
                "chunk_id": t.chunk_id,
                "manual_titulo": t.manual_titulo,
                "arquivo": t.arquivo,
                "categoria": t.categoria,
                "pagina": t.pagina,
                "texto": t.texto,
                "similaridade": t.similaridade,
                "score_rrf": t.score_rrf,
            }
            for t in trechos
            if isinstance(t, TrechoRecuperado)
        ]
        saida.append(item)
    return json.dumps(saida, ensure_ascii=False)


def desserializar_mensagens(mensagens_json: str) -> list[dict]:
    """Reconstrói a lista de mensagens com objetos TrechoRecuperado."""
    try:
        bruto = json.loads(mensagens_json or "[]")
    except Exception:
        return []
    saida: list[dict] = []
    for m in bruto:
        trechos = [
            TrechoRecuperado(
                chunk_id=int(t.get("chunk_id", 0)),
                manual_titulo=str(t.get("manual_titulo", "")),
                arquivo=str(t.get("arquivo", "")),
                categoria=str(t.get("categoria", "GERAL")),
                pagina=int(t.get("pagina", 1)),
                texto=str(t.get("texto", "")),
                similaridade=float(t.get("similaridade", 0.0)),
                score_rrf=float(t.get("score_rrf", 0.0)),
            )
            for t in (m.get("trechos") or [])
        ]
        saida.append(
            {
                "role": m.get("role", "user"),
                "content": m.get("content", ""),
                "pergunta": m.get("pergunta", ""),
                "trechos": trechos,
            }
        )
    return saida


class RepositorioRAG(Protocol):
    nome_backend: str

    def inicializar_esquema(self) -> None: ...
    def manual_ja_indexado(self, arquivo: str, sha256: str) -> bool: ...
    def salvar_manual_com_chunks(
        self,
        titulo: str,
        arquivo: str,
        categoria: str,
        sha256: str,
        paginas: int,
        chunks: list[Chunk],
        vetores: list[np.ndarray],
    ) -> int: ...
    def listar_manuais(self) -> list[ManualInfo]: ...
    def remover_manual(self, manual_id: int) -> None: ...
    def listar_chunks_manual(self, manual_id: int, limite: int = 30) -> list[Chunk]: ...
    def buscar_hibrido(
        self,
        vetor_consulta: np.ndarray,
        texto_consulta: str,
        top_k: int = 6,
        categoria: str | None = None,
    ) -> list[TrechoRecuperado]: ...
    def registrar_feedback(self, pergunta: str, resposta: str, positivo: bool) -> None: ...
    def listar_feedbacks(self, limite: int = 50) -> list[FeedbackInfo]: ...
    def remover_feedback(self, feedback_id: int) -> None: ...
    def salvar_conversa(
        self,
        conversa_id: str,
        device_id: str,
        titulo: str,
        modo: str,
        categoria: str,
        mensagens: list[dict],
        last_interaction_id: str | None = None,
    ) -> None: ...
    def obter_device_id_mais_recente(self) -> str | None: ...
    def listar_conversas_dispositivo(
        self, device_id: str, limite: int = 30
    ) -> list[ConversaResumo]: ...
    def carregar_conversa(
        self, conversa_id: str, device_id: str
    ) -> tuple[ConversaResumo, list[dict]] | None: ...
    def remover_conversa(self, conversa_id: str, device_id: str) -> None: ...


class PostgresRepositorio:
    """Implementação oficial com PostgreSQL + pgvector + tsvector em português."""

    nome_backend = "PostgreSQL + pgvector"

    def __init__(self, database_url: str) -> None:
        import psycopg
        from pgvector.psycopg import register_vector

        self._psycopg = psycopg
        self._register_vector = register_vector
        self.database_url = database_url

    def _conectar(self):
        conn = self._psycopg.connect(self.database_url, autocommit=False)
        try:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            conn.commit()
            self._register_vector(conn)
        except Exception:
            conn.rollback()
            raise
        return conn

    def inicializar_esquema(self) -> None:
        sql_path = RAIZ / "sql" / "001_init.sql"
        ddl = sql_path.read_text(encoding="utf-8")
        with self._conectar() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()

    def manual_ja_indexado(self, arquivo: str, sha256: str) -> bool:
        with self._conectar() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM manuais WHERE arquivo = %s AND sha256 = %s",
                (arquivo, sha256),
            )
            return cur.fetchone() is not None

    def salvar_manual_com_chunks(
        self,
        titulo: str,
        arquivo: str,
        categoria: str,
        sha256: str,
        paginas: int,
        chunks: list[Chunk],
        vetores: list[np.ndarray],
    ) -> int:
        with self._conectar() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM manuais WHERE arquivo = %s", (arquivo,))
                cur.execute(
                    """
                    INSERT INTO manuais (titulo, arquivo, categoria, sha256, paginas)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (titulo, arquivo, categoria, sha256, paginas),
                )
                manual_id = int(cur.fetchone()[0])

                registros = [
                    (manual_id, categoria, c.pagina, c.ordem, c.texto, v)
                    for c, v in zip(chunks, vetores, strict=True)
                ]
                cur.executemany(
                    """
                    INSERT INTO chunks (manual_id, categoria, pagina, ordem, texto, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    registros,
                )
            conn.commit()
            return manual_id

    def listar_manuais(self) -> list[ManualInfo]:
        with self._conectar() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.id, m.titulo, m.arquivo, m.categoria, m.sha256,
                       COALESCE(m.paginas, 0), COUNT(c.id) AS total_chunks
                FROM manuais m
                LEFT JOIN chunks c ON c.manual_id = m.id
                GROUP BY m.id
                ORDER BY m.titulo
                """
            )
            return [
                ManualInfo(
                    id=int(r[0]),
                    titulo=r[1],
                    arquivo=r[2],
                    categoria=r[3],
                    sha256=r[4],
                    paginas=int(r[5]),
                    total_chunks=int(r[6]),
                )
                for r in cur.fetchall()
            ]

    def remover_manual(self, manual_id: int) -> None:
        with self._conectar() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM manuais WHERE id = %s", (manual_id,))
            conn.commit()

    def listar_chunks_manual(self, manual_id: int, limite: int = 30) -> list[Chunk]:
        with self._conectar() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT pagina, ordem, texto
                FROM chunks
                WHERE manual_id = %s
                ORDER BY pagina, ordem
                LIMIT %s
                """,
                (manual_id, limite),
            )
            return [Chunk(pagina=int(r[0]), ordem=int(r[1]), texto=r[2]) for r in cur.fetchall()]

    def buscar_hibrido(
        self,
        vetor_consulta: np.ndarray,
        texto_consulta: str,
        top_k: int = 6,
        categoria: str | None = None,
    ) -> list[TrechoRecuperado]:
        filtro_cat = categoria if (categoria and categoria != "TODAS") else None
        limite_candidatos = max(top_k * 4, 20)

        sql = """
        WITH semantica AS (
            SELECT c.id,
                   1 - (c.embedding <=> %(vec)s) AS similaridade,
                   ROW_NUMBER() OVER (ORDER BY c.embedding <=> %(vec)s) AS rank_sem
            FROM chunks c
            WHERE (%(cat)s::text IS NULL OR c.categoria = %(cat)s)
            ORDER BY c.embedding <=> %(vec)s
            LIMIT %(cand)s
        ),
        lexical AS (
            SELECT c.id,
                   ROW_NUMBER() OVER (
                       ORDER BY ts_rank_cd(c.tsv, websearch_to_tsquery('portuguese', %(q)s)) DESC
                   ) AS rank_lex
            FROM chunks c
            WHERE (%(cat)s::text IS NULL OR c.categoria = %(cat)s)
              AND c.tsv @@ websearch_to_tsquery('portuguese', %(q)s)
            LIMIT %(cand)s
        ),
        combinado AS (
            SELECT COALESCE(s.id, l.id) AS chunk_id,
                   COALESCE(s.similaridade, 0.0) AS similaridade,
                   COALESCE(1.0 / (%(rrf_k)s + s.rank_sem), 0.0)
                   + COALESCE(1.0 / (%(rrf_k)s + l.rank_lex), 0.0) AS score_rrf
            FROM semantica s
            FULL OUTER JOIN lexical l ON s.id = l.id
        )
        SELECT c.id, m.titulo, m.arquivo, c.categoria, c.pagina, c.texto,
               cb.similaridade, cb.score_rrf
        FROM combinado cb
        JOIN chunks c ON c.id = cb.chunk_id
        JOIN manuais m ON m.id = c.manual_id
        ORDER BY cb.score_rrf DESC, cb.similaridade DESC
        LIMIT %(top_k)s;
        """
        params = {
            "vec": vetor_consulta,
            "q": texto_consulta,
            "cat": filtro_cat,
            "cand": limite_candidatos,
            "rrf_k": RRF_K,
            "top_k": top_k,
        }
        with self._conectar() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            brutos = [
                TrechoRecuperado(
                    chunk_id=int(r[0]),
                    manual_titulo=r[1],
                    arquivo=r[2],
                    categoria=r[3],
                    pagina=int(r[4]),
                    texto=r[5],
                    similaridade=float(r[6]),
                    score_rrf=float(r[7]),
                )
                for r in cur.fetchall()
            ]
            return filtrar_trechos_relevantes(brutos, top_k=top_k)

    def registrar_feedback(self, pergunta: str, resposta: str, positivo: bool) -> None:
        with self._conectar() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO feedback (pergunta, resposta, positivo) VALUES (%s, %s, %s)",
                (pergunta, resposta, positivo),
            )
            conn.commit()

    def listar_feedbacks(self, limite: int = 50) -> list[FeedbackInfo]:
        with self._conectar() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, pergunta, resposta, positivo, criado_em::text
                FROM feedback
                ORDER BY id DESC
                LIMIT %s
                """,
                (limite,),
            )
            return [
                FeedbackInfo(
                    id=int(r[0]),
                    pergunta=r[1],
                    resposta=r[2],
                    positivo=bool(r[3]),
                    criado_em=r[4],
                )
                for r in cur.fetchall()
            ]

    def remover_feedback(self, feedback_id: int) -> None:
        with self._conectar() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM feedback WHERE id = %s", (feedback_id,))
            conn.commit()

    def salvar_conversa(
        self,
        conversa_id: str,
        device_id: str,
        titulo: str,
        modo: str,
        categoria: str,
        mensagens: list[dict],
        last_interaction_id: str | None = None,
    ) -> None:
        payload = serializar_mensagens(mensagens)
        with self._conectar() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversas (id, device_id, titulo, modo, categoria, last_interaction_id, mensagens_json, atualizado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (id) DO UPDATE SET
                    titulo = EXCLUDED.titulo,
                    modo = EXCLUDED.modo,
                    categoria = EXCLUDED.categoria,
                    last_interaction_id = EXCLUDED.last_interaction_id,
                    mensagens_json = EXCLUDED.mensagens_json,
                    atualizado_em = now()
                """,
                (conversa_id, device_id, titulo, modo, categoria, last_interaction_id, payload),
            )
            conn.commit()

    def obter_device_id_mais_recente(self) -> str | None:
        with self._conectar() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT device_id FROM conversas ORDER BY atualizado_em DESC LIMIT 1"
            )
            r = cur.fetchone()
            return str(r[0]) if r and r[0] else None

    def listar_conversas_dispositivo(
        self, device_id: str, limite: int = 30
    ) -> list[ConversaResumo]:
        with self._conectar() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, device_id, titulo, modo, categoria, last_interaction_id, atualizado_em::text
                FROM conversas
                WHERE device_id = %s
                ORDER BY atualizado_em DESC
                LIMIT %s
                """,
                (device_id, limite),
            )
            return [
                ConversaResumo(
                    id=str(r[0]),
                    device_id=str(r[1]),
                    titulo=str(r[2]),
                    modo=str(r[3]),
                    categoria=str(r[4]),
                    last_interaction_id=r[5],
                    atualizado_em=str(r[6]),
                )
                for r in cur.fetchall()
            ]

    def carregar_conversa(
        self, conversa_id: str, device_id: str
    ) -> tuple[ConversaResumo, list[dict]] | None:
        with self._conectar() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, device_id, titulo, modo, categoria, last_interaction_id, atualizado_em::text, mensagens_json
                FROM conversas
                WHERE id = %s AND device_id = %s
                """,
                (conversa_id, device_id),
            )
            r = cur.fetchone()
            if not r:
                return None
            resumo = ConversaResumo(
                id=str(r[0]),
                device_id=str(r[1]),
                titulo=str(r[2]),
                modo=str(r[3]),
                categoria=str(r[4]),
                last_interaction_id=r[5],
                atualizado_em=str(r[6]),
            )
            return resumo, desserializar_mensagens(r[7])

    def remover_conversa(self, conversa_id: str, device_id: str) -> None:
        with self._conectar() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM conversas WHERE id = %s AND device_id = %s",
                (conversa_id, device_id),
            )
            conn.commit()


class SqliteRepositorio:
    """Fallback local (SQLite + NumPy) com a mesma estrutura de tabelas e RRF."""

    nome_backend = "SQLite Local + NumPy (Modo PoC Rápida)"

    def __init__(self, caminho_db: Path | None = None) -> None:
        self.caminho_db = caminho_db or (RAIZ / "data" / "chatdbv_local.sqlite")
        self.caminho_db.parent.mkdir(parents=True, exist_ok=True)

    def _conectar(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.caminho_db))
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def inicializar_esquema(self) -> None:
        with self._conectar() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS manuais (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    titulo    TEXT NOT NULL,
                    arquivo   TEXT NOT NULL UNIQUE,
                    categoria TEXT NOT NULL DEFAULT 'GERAL',
                    sha256    TEXT NOT NULL,
                    paginas   INTEGER,
                    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    manual_id INTEGER NOT NULL REFERENCES manuais(id) ON DELETE CASCADE,
                    categoria TEXT NOT NULL,
                    pagina    INTEGER NOT NULL,
                    ordem     INTEGER NOT NULL,
                    texto     TEXT NOT NULL,
                    embedding TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS feedback (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    pergunta  TEXT NOT NULL,
                    resposta  TEXT NOT NULL,
                    positivo  INTEGER NOT NULL,
                    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS conversas (
                    id                  TEXT PRIMARY KEY,
                    device_id           TEXT NOT NULL,
                    titulo              TEXT NOT NULL,
                    modo                TEXT NOT NULL DEFAULT 'consulta',
                    categoria           TEXT NOT NULL DEFAULT 'TODAS',
                    last_interaction_id TEXT,
                    mensagens_json      TEXT NOT NULL DEFAULT '[]',
                    atualizado_em       TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS conversas_device_idx
                    ON conversas (device_id, atualizado_em DESC);
                """
            )

    def manual_ja_indexado(self, arquivo: str, sha256: str) -> bool:
        with self._conectar() as conn:
            cur = conn.execute(
                "SELECT 1 FROM manuais WHERE arquivo = ? AND sha256 = ?",
                (arquivo, sha256),
            )
            return cur.fetchone() is not None

    def salvar_manual_com_chunks(
        self,
        titulo: str,
        arquivo: str,
        categoria: str,
        sha256: str,
        paginas: int,
        chunks: list[Chunk],
        vetores: list[np.ndarray],
    ) -> int:
        with self._conectar() as conn:
            conn.execute("DELETE FROM manuais WHERE arquivo = ?", (arquivo,))
            cur = conn.execute(
                """
                INSERT INTO manuais (titulo, arquivo, categoria, sha256, paginas)
                VALUES (?, ?, ?, ?, ?)
                """,
                (titulo, arquivo, categoria, sha256, paginas),
            )
            manual_id = int(cur.lastrowid)
            registros = [
                (
                    manual_id,
                    categoria,
                    c.pagina,
                    c.ordem,
                    c.texto,
                    json.dumps(v.tolist()),
                )
                for c, v in zip(chunks, vetores, strict=True)
            ]
            conn.executemany(
                """
                INSERT INTO chunks (manual_id, categoria, pagina, ordem, texto, embedding)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                registros,
            )
            return manual_id

    def listar_manuais(self) -> list[ManualInfo]:
        with self._conectar() as conn:
            cur = conn.execute(
                """
                SELECT m.id, m.titulo, m.arquivo, m.categoria, m.sha256,
                       COALESCE(m.paginas, 0), COUNT(c.id)
                FROM manuais m
                LEFT JOIN chunks c ON c.manual_id = m.id
                GROUP BY m.id
                ORDER BY m.titulo
                """
            )
            return [
                ManualInfo(
                    id=int(r[0]),
                    titulo=r[1],
                    arquivo=r[2],
                    categoria=r[3],
                    sha256=r[4],
                    paginas=int(r[5]),
                    total_chunks=int(r[6]),
                )
                for r in cur.fetchall()
            ]

    def remover_manual(self, manual_id: int) -> None:
        with self._conectar() as conn:
            conn.execute("DELETE FROM manuais WHERE id = ?", (manual_id,))

    def listar_chunks_manual(self, manual_id: int, limite: int = 30) -> list[Chunk]:
        with self._conectar() as conn:
            cur = conn.execute(
                """
                SELECT pagina, ordem, texto
                FROM chunks
                WHERE manual_id = ?
                ORDER BY pagina, ordem
                LIMIT ?
                """,
                (manual_id, limite),
            )
            return [Chunk(pagina=int(r[0]), ordem=int(r[1]), texto=r[2]) for r in cur.fetchall()]

    def buscar_hibrido(
        self,
        vetor_consulta: np.ndarray,
        texto_consulta: str,
        top_k: int = 6,
        categoria: str | None = None,
    ) -> list[TrechoRecuperado]:
        filtro_cat = categoria if (categoria and categoria != "TODAS") else None
        sql = """
            SELECT c.id, m.titulo, m.arquivo, c.categoria, c.pagina, c.texto, c.embedding
            FROM chunks c
            JOIN manuais m ON m.id = c.manual_id
        """
        params: tuple = ()
        if filtro_cat:
            sql += " WHERE c.categoria = ?"
            params = (filtro_cat,)

        with self._conectar() as conn:
            linhas = conn.execute(sql, params).fetchall()

        if not linhas:
            return []

        q_vec = np.asarray(vetor_consulta, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        termos = [
            t
            for t in re.findall(r"[a-zA-Zà-úÀ-Ú0-9]{3,}", texto_consulta.lower())
            if t not in {"que", "qual", "quais", "como", "para", "dos", "das", "nos", "nas", "uma", "por"}
        ]

        sims: list[float] = []
        scores_lex: list[float] = []
        termos_unicos = list(dict.fromkeys(termos))
        textos_lower = [linha[5].lower() for linha in linhas]
        n_docs = len(linhas)
        idf = {
            t: math.log((n_docs + 1) / (sum(1 for txt in textos_lower if t in txt) + 1)) + 1.0
            for t in termos_unicos
        }
        bigramas = [f"{termos_unicos[k]} {termos_unicos[k + 1]}" for k in range(len(termos_unicos) - 1)]

        for idx_linha, linha in enumerate(linhas):
            emb = np.asarray(json.loads(linha[6]), dtype=np.float32)
            sims.append(float(np.dot(emb, q_vec)))
            texto_lower = textos_lower[idx_linha]
            score_l = 0.0
            for t in termos_unicos:
                cnt = texto_lower.count(t)
                if cnt > 0:
                    score_l += idf[t] * (1.0 + 0.25 * min(cnt, 4))
            for bg in bigramas:
                if bg in texto_lower:
                    score_l += 2.0
            scores_lex.append(score_l)

        ordem_sem = sorted(range(len(linhas)), key=lambda i: sims[i], reverse=True)
        rank_sem = {idx: pos + 1 for pos, idx in enumerate(ordem_sem)}

        indices_com_match = [i for i, sc in enumerate(scores_lex) if sc > 0]
        ordem_lex = sorted(indices_com_match, key=lambda i: scores_lex[i], reverse=True)
        rank_lex = {idx: pos + 1 for pos, idx in enumerate(ordem_lex)}

        resultados: list[TrechoRecuperado] = []
        for i, linha in enumerate(linhas):
            rrf = 1.0 / (RRF_K + rank_sem[i])
            if i in rank_lex:
                rrf += 1.0 / (RRF_K + rank_lex[i])
            resultados.append(
                TrechoRecuperado(
                    chunk_id=int(linha[0]),
                    manual_titulo=linha[1],
                    arquivo=linha[2],
                    categoria=linha[3],
                    pagina=int(linha[4]),
                    texto=linha[5],
                    similaridade=sims[i],
                    score_rrf=rrf,
                )
            )

        resultados.sort(key=lambda r: (r.score_rrf, r.similaridade), reverse=True)
        return filtrar_trechos_relevantes(resultados, top_k=top_k)

    def registrar_feedback(self, pergunta: str, resposta: str, positivo: bool) -> None:
        with self._conectar() as conn:
            conn.execute(
                "INSERT INTO feedback (pergunta, resposta, positivo) VALUES (?, ?, ?)",
                (pergunta, resposta, 1 if positivo else 0),
            )

    def listar_feedbacks(self, limite: int = 50) -> list[FeedbackInfo]:
        with self._conectar() as conn:
            cur = conn.execute(
                """
                SELECT id, pergunta, resposta, positivo, criado_em
                FROM feedback
                ORDER BY id DESC
                LIMIT ?
                """,
                (limite,),
            )
            return [
                FeedbackInfo(
                    id=int(r[0]),
                    pergunta=r[1],
                    resposta=r[2],
                    positivo=bool(r[3]),
                    criado_em=str(r[4]),
                )
                for r in cur.fetchall()
            ]

    def remover_feedback(self, feedback_id: int) -> None:
        with self._conectar() as conn:
            conn.execute("DELETE FROM feedback WHERE id = ?", (feedback_id,))

    def salvar_conversa(
        self,
        conversa_id: str,
        device_id: str,
        titulo: str,
        modo: str,
        categoria: str,
        mensagens: list[dict],
        last_interaction_id: str | None = None,
    ) -> None:
        payload = serializar_mensagens(mensagens)
        with self._conectar() as conn:
            conn.execute(
                """
                INSERT INTO conversas (id, device_id, titulo, modo, categoria, last_interaction_id, mensagens_json, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                    titulo = excluded.titulo,
                    modo = excluded.modo,
                    categoria = excluded.categoria,
                    last_interaction_id = excluded.last_interaction_id,
                    mensagens_json = excluded.mensagens_json,
                    atualizado_em = datetime('now')
                """,
                (conversa_id, device_id, titulo, modo, categoria, last_interaction_id, payload),
            )

    def obter_device_id_mais_recente(self) -> str | None:
        with self._conectar() as conn:
            cur = conn.execute(
                "SELECT device_id FROM conversas ORDER BY atualizado_em DESC LIMIT 1"
            )
            r = cur.fetchone()
            return str(r[0]) if r and r[0] else None

    def listar_conversas_dispositivo(
        self, device_id: str, limite: int = 30
    ) -> list[ConversaResumo]:
        with self._conectar() as conn:
            cur = conn.execute(
                """
                SELECT id, device_id, titulo, modo, categoria, last_interaction_id, atualizado_em
                FROM conversas
                WHERE device_id = ?
                ORDER BY atualizado_em DESC
                LIMIT ?
                """,
                (device_id, limite),
            )
            return [
                ConversaResumo(
                    id=str(r[0]),
                    device_id=str(r[1]),
                    titulo=str(r[2]),
                    modo=str(r[3]),
                    categoria=str(r[4]),
                    last_interaction_id=r[5],
                    atualizado_em=str(r[6]),
                )
                for r in cur.fetchall()
            ]

    def carregar_conversa(
        self, conversa_id: str, device_id: str
    ) -> tuple[ConversaResumo, list[dict]] | None:
        with self._conectar() as conn:
            cur = conn.execute(
                """
                SELECT id, device_id, titulo, modo, categoria, last_interaction_id, atualizado_em, mensagens_json
                FROM conversas
                WHERE id = ? AND device_id = ?
                """,
                (conversa_id, device_id),
            )
            r = cur.fetchone()
            if not r:
                return None
            resumo = ConversaResumo(
                id=str(r[0]),
                device_id=str(r[1]),
                titulo=str(r[2]),
                modo=str(r[3]),
                categoria=str(r[4]),
                last_interaction_id=r[5],
                atualizado_em=str(r[6]),
            )
            return resumo, desserializar_mensagens(str(r[7]))

    def remover_conversa(self, conversa_id: str, device_id: str) -> None:
        with self._conectar() as conn:
            conn.execute(
                "DELETE FROM conversas WHERE id = ? AND device_id = ?",
                (conversa_id, device_id),
            )


def criar_repositorio(cfg: Config) -> RepositorioRAG:
    """Seleciona PostgreSQL + pgvector quando DATABASE_URL aponta para Postgres;
    caso contrário usa o repositório SQLite local para não bloquear testes da PoC."""
    url = (cfg.database_url or "").strip()
    if url.startswith(("postgresql://", "postgres://")):
        return PostgresRepositorio(url)
    return SqliteRepositorio()
