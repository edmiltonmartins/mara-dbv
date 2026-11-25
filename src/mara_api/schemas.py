# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Edmilton Cabral Martins Junior <junior.edmilton@gmail.com>

"""Esquemas Pydantic v2 da API Mara v2.0."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TrechoDTO(BaseModel):
    chunk_id: int = 0
    manual_titulo: str
    arquivo: str
    categoria: str
    pagina: int
    texto: str
    similaridade: float
    score_rrf: float = 0.0


class QuestaoQuizDTO(BaseModel):
    enunciado: str
    alternativas: list[str]
    indice_correto: int
    explicacao: str
    fonte: str = ""


class QuizEstruturadoDTO(BaseModel):
    titulo: str
    nivel: str = "regular"
    questoes: list[QuestaoQuizDTO] = Field(default_factory=list)


class ChatRequest(BaseModel):
    pergunta: str = Field(..., min_length=1, max_length=1200)
    conversa_id: str | None = None
    categoria: str = "TODAS"
    modo_quiz: bool = False


class QuizRequest(BaseModel):
    tema: str = Field(..., min_length=1, max_length=600)
    conversa_id: str | None = None
    categoria: str = "TODAS"
    quantidade: int = Field(default=3, ge=2, le=10)
    nivel: Literal["aspirante", "regular", "lideranca"] = "regular"


class QuizResponse(BaseModel):
    conversa_id: str
    titulo_conversa: str
    quiz: QuizEstruturadoDTO
    markdown: str
    trechos: list[TrechoDTO] = Field(default_factory=list)


class MensagemDTO(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    pergunta: str = ""
    trechos: list[TrechoDTO] = Field(default_factory=list)
    quiz: dict[str, Any] | None = None


class ConversaResumoDTO(BaseModel):
    id: str
    titulo: str
    modo: str
    categoria: str
    atualizado_em: str


class ConversaDetalheDTO(BaseModel):
    resumo: ConversaResumoDTO
    mensagens: list[MensagemDTO]


class PdfRespostaRequest(BaseModel):
    pergunta: str = ""
    resposta_md: str
    trechos: list[TrechoDTO] = Field(default_factory=list)
    categoria: str = "TODAS"
    modo_quiz: bool = False


class FeedbackRequest(BaseModel):
    pergunta: str
    resposta: str
    positivo: bool


class AdminLoginRequest(BaseModel):
    senha: str


class AdminConfigUpdateRequest(BaseModel):
    nome_clube: str | None = None
    gemini_api_key: str | None = None
    modelo_chat: str | None = None
    top_k: int | None = Field(default=None, ge=2, le=12)
    database_url: str | None = None
    exibir_detalhes_tecnicos: bool | None = None
    chat_ativo: bool | None = None
    mensagem_manutencao: str | None = None


class AdminSenhaUpdateRequest(BaseModel):
    nova_senha: str = Field(..., min_length=4, max_length=128)
