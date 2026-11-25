# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Edmilton Cabral Martins Junior <junior.edmilton@gmail.com>

"""Segurança da API Mara v2.0: Rate Limiting por sessão/IP e Autenticação Admin HMAC."""
from __future__ import annotations

import hashlib
import hmac
import threading
import time
import uuid

from fastapi import HTTPException, Request, status

from chatdbv.config import Config, verificar_senha_admin

MAX_CHARS_PERGUNTA = 1200
MAX_PERGUNTAS_POR_MINUTO = 12
COOLDOWN_SEGUNDOS = 2.0
COOKIE_ADMIN_NOME = "mara_admin_session"
COOKIE_DEVICE_NOME = "dbv_device_id"


class LimitadorTaxaMemoria:
    """Rate limiter leve e thread-safe por chave de cliente (device_id + IP)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._historico: dict[str, list[float]] = {}
        self._tentativas_login: dict[str, list[float]] = {}

    def validar_pergunta(self, chave_cliente: str, texto: str) -> str:
        limpo = (texto or "").strip()
        if not limpo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Digite uma pergunta ou tema válido.",
            )
        if len(limpo) > MAX_CHARS_PERGUNTA:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Sua pergunta ultrapassou o limite de {MAX_CHARS_PERGUNTA} caracteres "
                    f"({len(limpo)} digitados). Resuma sua dúvida para garantir precisão."
                ),
            )

        agora = time.time()
        with self._lock:
            janela = [t for t in self._historico.get(chave_cliente, []) if agora - t < 60.0]
            if len(janela) >= MAX_PERGUNTAS_POR_MINUTO:
                self._historico[chave_cliente] = janela
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Limite de 12 perguntas por minuto atingido. Aguarde alguns segundos.",
                )
            if janela and (agora - janela[-1] < COOLDOWN_SEGUNDOS):
                self._historico[chave_cliente] = janela
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Aguarde 2 segundos entre mensagens consecutivas.",
                )
            janela.append(agora)
            self._historico[chave_cliente] = janela
        return limpo

    def registrar_tentativa_login(self, ip: str, sucesso: bool) -> None:
        agora = time.time()
        with self._lock:
            falhas = [t for t in self._tentativas_login.get(ip, []) if agora - t < 300.0]
            if len(falhas) >= 8:
                self._tentativas_login[ip] = falhas
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Muitas tentativas incorretas. Aguarde 5 minutos.",
                )
            if sucesso:
                self._tentativas_login.pop(ip, None)
            else:
                falhas.append(agora)
                self._tentativas_login[ip] = falhas


def extrair_ip_cliente(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def extrair_device_id(request: Request) -> str:
    bruto = (
        request.headers.get("x-device-id")
        or request.cookies.get(COOKIE_DEVICE_NOME)
        or ""
    ).strip()
    # Sanitiza para aceitar apenas caracteres alfanuméricos, hífen e sublinhado
    seguro = "".join(c for c in bruto if c.isalnum() or c in ("_", "-"))
    if len(seguro) >= 8:
        return seguro[:48]
    return f"dbv_{uuid.uuid4().hex[:12]}"


def _segredo_sessao_admin(cfg: Config) -> bytes:
    semente = f"mara_v2_secret::{cfg.admin_password}::{cfg.gemini_api_key[:8]}"
    return hashlib.sha256(semente.encode("utf-8")).digest()


def gerar_token_sessao_admin(cfg: Config, duracao_segundos: int = 43200) -> str:
    expira = int(time.time()) + duracao_segundos
    payload = f"admin:{expira}"
    assinatura = hmac.new(
        _segredo_sessao_admin(cfg), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{assinatura}"


def validar_token_sessao_admin(token: str | None, cfg: Config) -> bool:
    if not token or "." not in token:
        return False
    payload, assinatura = token.rsplit(".", 1)
    esperada = hmac.new(
        _segredo_sessao_admin(cfg), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(assinatura.encode("utf-8"), esperada.encode("utf-8")):
        return False
    try:
        _, exp_str = payload.split(":", 1)
        return int(exp_str) > int(time.time())
    except Exception:
        return False


def exigir_admin_autenticado(request: Request, cfg: Config) -> None:
    token = request.cookies.get(COOKIE_ADMIN_NOME) or request.headers.get("x-admin-token")
    if not validar_token_sessao_admin(token, cfg):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão administrativa expirada ou não autenticada.",
        )


__all__ = [
    "COOKIE_ADMIN_NOME",
    "COOKIE_DEVICE_NOME",
    "LimitadorTaxaMemoria",
    "exigir_admin_autenticado",
    "extrair_device_id",
    "extrair_ip_cliente",
    "gerar_token_sessao_admin",
    "validar_token_sessao_admin",
    "verificar_senha_admin",
]
