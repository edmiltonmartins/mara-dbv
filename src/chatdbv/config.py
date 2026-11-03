"""Configuração central do Chat DBV, carregada de variáveis de ambiente / .env.

Inclui autenticação administrativa (inspirada no projeto irmão infinito-games)
e persistência centralizada das configurações do sistema.
"""
from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, load_dotenv, set_key
from google import genai

RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO_ENV = RAIZ / ".env"

MODELOS_DISPONIVEIS = (
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-pro-preview",
    "gemini-3.1-flash-lite",
)


def limpar_chave(valor: str | None) -> str:
    if not valor:
        return ""
    limpo = valor.strip().strip('"').strip("'")
    if limpo.startswith("GEMINI_API_KEY="):
        limpo = limpo.split("=", 1)[1].strip()
    return limpo


def verificar_senha_admin(senha_informada: str, senha_esperada: str) -> bool:
    """Comparação em tempo constante (equivalente ao safeEqual do infinito-games)."""
    a = (senha_informada or "").encode("utf-8")
    b = (senha_esperada or "").encode("utf-8")
    if len(a) != len(b):
        return False
    return hmac.compare_digest(a, b)


def criar_cliente_genai(cfg: "Config") -> genai.Client:
    """Cria o cliente oficial google-genai para a Gemini Developer API (suporta chaves AIza... e AQ...)."""
    chave = limpar_chave(cfg.gemini_api_key)
    if cfg.usa_vertex_express:
        return genai.Client(vertexai=True, api_key=chave)
    return genai.Client(api_key=chave)


def salvar_configuracoes_no_env(atualizacoes: dict[str, str]) -> None:
    """Persiste múltiplas chaves de configuração no arquivo .env."""
    if not ARQUIVO_ENV.exists():
        ARQUIVO_ENV.write_text(
            "GEMINI_API_KEY=\nDATABASE_URL=\nMODELO_CHAT=gemini-3.8-flash\nADMIN_PASSWORD=admin123\n",
            encoding="utf-8",
        )
    for chave, valor in atualizacoes.items():
        val_limpo = limpar_chave(valor) if chave == "GEMINI_API_KEY" else str(valor).strip()
        set_key(str(ARQUIVO_ENV), chave, val_limpo, quote_mode="never")
        os.environ[chave] = val_limpo


def salvar_chave_no_env(nova_chave: str) -> str:
    """Atalho para salvar a GEMINI_API_KEY diretamente no arquivo .env."""
    limpa = limpar_chave(nova_chave)
    salvar_configuracoes_no_env({"GEMINI_API_KEY": limpa})
    return limpa


def _to_int(valor: str | None, padrao: int) -> int:
    try:
        v = int(valor or "")
        return v if v > 0 else padrao
    except ValueError:
        return padrao


def _to_bool(valor: str | None, padrao: bool = True) -> bool:
    if valor is None or valor == "":
        return padrao
    return valor.strip().lower() not in ("0", "false", "nao", "não", "no", "off")


@dataclass(frozen=True)
class Config:
    database_url: str
    gemini_api_key: str
    modelo_chat: str = "gemini-3.8-flash"
    modelo_embedding: str = "gemini-embedding-001"
    dimensao: int = 768
    pasta_manuais: Path = RAIZ / "data" / "manuais"
    top_k: int = 6
    admin_password: str = "admin123"
    nome_clube: str = "Divisão Sul-Americana (DSA)"
    chat_ativo: bool = True
    exibir_detalhes_tecnicos: bool = False
    mensagem_manutencao: str = (
        "A Mara está em manutenção pela Diretoria para atualização de manuais. Voltamos em breve!"
    )

    @property
    def usa_vertex_express(self) -> bool:
        return os.environ.get("USE_VERTEXAI", "").lower() in ("1", "true", "yes")

    @staticmethod
    def carregar() -> "Config":
        load_dotenv(ARQUIVO_ENV, override=True)
        v = dotenv_values(ARQUIVO_ENV) if ARQUIVO_ENV.exists() else {}

        def obter(chave: str, padrao: str = "") -> str:
            val = v.get(chave)
            if val is None:
                val = os.environ.get(chave, padrao)
            return val

        return Config(
            database_url=obter("DATABASE_URL", "").strip(),
            gemini_api_key=limpar_chave(obter("GEMINI_API_KEY", "")),
            modelo_chat=obter("MODELO_CHAT", "gemini-3.8-flash").strip() or "gemini-3.8-flash",
            top_k=_to_int(obter("TOP_K", "6"), 6),
            admin_password=obter("ADMIN_PASSWORD", "admin123") or "admin123",
            nome_clube=obter("NOME_CLUBE", "Divisão Sul-Americana (DSA)").strip()
            or "Divisão Sul-Americana (DSA)",
            chat_ativo=_to_bool(obter("CHAT_ATIVO", "true"), True),
            exibir_detalhes_tecnicos=_to_bool(obter("EXIBIR_DETALHES_TECNICOS", "false"), False),
            mensagem_manutencao=obter(
                "MENSAGEM_MANUTENCAO",
                "A Mara está em manutenção pela Diretoria para atualização de manuais. Voltamos em breve!",
            ),
        )

    @property
    def dimensao_embedding(self) -> int:
        return self.dimensao

    @staticmethod
    def from_env() -> "Config":
        return Config.carregar()

    def validar(self) -> None:
        faltando = [
            nome
            for nome, valor in (
                ("DATABASE_URL", self.database_url),
                ("GEMINI_API_KEY", self.gemini_api_key),
            )
            if not valor
        ]
        if faltando:
            raise RuntimeError(
                "Variáveis ausentes no arquivo .env: " + ", ".join(faltando)
                + ". Veja o README.md (seção Configuração)."
            )
