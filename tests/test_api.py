"""Testes de contrato e integração da API Mara v2.0 (FastAPI + SSE + Quiz JSON + PDF + Admin)."""
from __future__ import annotations

import sys
import time
from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from chatdbv.config import Config
from chatdbv.db import SqliteRepositorio, TrechoRecuperado
from chatdbv.rag import RespostaRAG, quiz_estruturado_para_markdown, verificar_resposta_zero_token
from mara_api.main import criar_aplicacao


class FakeMotorAPI:
    """Motor determinístico offline para validar SSE, Zero-Token Guard e Quiz Estruturado."""

    def __init__(self) -> None:
        self.ultimo_interaction_id = "inter_fake_v2"
        self._trecho_padrao = TrechoRecuperado(
            chunk_id=1,
            manual_titulo="Regulamento de Uniformes DSA",
            arquivo="02_regulamento_uniformes_dsa.md",
            categoria="UNIFORMES",
            pagina=14,
            texto="O Emblema D1 fica a 50 mm abaixo da costura do ombro direito.",
            similaridade=0.94,
            score_rrf=0.04,
        )

    def recuperar(
        self,
        pergunta: str,
        categoria: str | None = None,
        top_k: int | None = None,
        historico_recente: list[dict] | None = None,
    ) -> list[TrechoRecuperado]:
        if "bolo de chocolate" in pergunta.lower():
            return []
        return [self._trecho_padrao]

    def verificar_resposta_zero_token(
        self,
        pergunta: str,
        trechos: list[TrechoRecuperado],
        conversa_em_andamento: bool = False,
    ) -> str | None:
        return verificar_resposta_zero_token(
            pergunta, trechos, conversa_em_andamento=conversa_em_andamento
        )

    def responder_stream(
        self,
        pergunta: str,
        trechos: list[TrechoRecuperado],
        modo_quiz: bool = False,
        previous_interaction_id: str | None = None,
        historico_recente: list[dict] | None = None,
    ) -> Iterator[str]:
        yield "O **Emblema D1** deve ser aplicado a "
        yield "**50 mm** da costura do ombro direito [Regulamento de Uniformes DSA, pág. 14]."

    def responder(self, **kwargs) -> RespostaRAG:
        return RespostaRAG(
            texto="Resposta síncrona fallback.",
            trechos=[self._trecho_padrao],
            interaction_id="inter_sync",
        )

    def gerar_quiz_estruturado(
        self,
        tema: str,
        categoria: str | None = None,
        quantidade: int = 3,
        nivel: str = "regular",
    ) -> tuple[dict, str, list[TrechoRecuperado]]:
        dados = {
            "titulo": f"Simulado Oficial: {tema}",
            "nivel": nivel,
            "questoes": [
                {
                    "enunciado": f"Questão #{i + 1} sobre {tema}?",
                    "alternativas": [
                        "15 mm da costura",
                        "50 mm abaixo da costura do ombro direito",
                        "Acima do bolso esquerdo",
                        "Na gola da camisa",
                    ],
                    "indice_correto": 1,
                    "explicacao": "Conforme o RUD oficial, o triângulo D1 fica a 50 mm.",
                    "fonte": "Regulamento de Uniformes DSA, pág. 14",
                }
                for i in range(quantidade)
            ],
        }
        md = quiz_estruturado_para_markdown(dados, exibir_fontes=True)
        return dados, md, [self._trecho_padrao]


def _criar_client_teste(tmp_path: Path) -> TestClient:
    repo = SqliteRepositorio(tmp_path / "api_test.sqlite")
    repo.inicializar_esquema()
    cfg = Config(
        database_url="",
        gemini_api_key="AIzaFakeKeyForTesting123456",
        admin_password="senha_diretoria_segura",
        nome_clube="Clube Órion — Teste",
        exibir_detalhes_tecnicos=True,
    )
    app = criar_aplicacao(repo_override=repo, motor_override=FakeMotorAPI(), cfg_override=cfg)
    return TestClient(app)


def test_health_emblems_e_biblioteca(tmp_path: Path) -> None:
    client = _criar_client_teste(tmp_path)

    r_health = client.get("/api/health", headers={"X-Device-Id": "dbv_dispositivo_01"})
    assert r_health.status_code == 200
    body = r_health.json()
    assert body["status"] == "ok"
    assert body["nome_clube"] == "Clube Órion — Teste"
    assert body["total_guias_biblioteca"] >= 8

    r_emb = client.get("/api/emblems/d1")
    assert r_emb.status_code == 200
    assert r_emb.headers["content-type"] in ("image/png", "image/svg+xml")

    r_lib = client.get("/api/library")
    assert r_lib.status_code == 200
    guias = r_lib.json()["guias"]
    assert len(guias) >= 8
    assert guias[0]["pdf_url"].startswith("/api/pdf/guia/")

    r_pdf_guia = client.get(guias[0]["pdf_url"])
    assert r_pdf_guia.status_code == 200
    assert r_pdf_guia.content.startswith(b"%PDF-")


def test_chat_sse_persistencia_e_rate_limit(tmp_path: Path) -> None:
    client = _criar_client_teste(tmp_path)
    headers = {"X-Device-Id": "dbv_dispositivo_sse01"}

    r_sse = client.post(
        "/api/chat/stream",
        headers=headers,
        json={
            "pergunta": "Qual a medida do Emblema D1 na manga direita?",
            "categoria": "UNIFORMES",
            "modo_quiz": False,
        },
    )
    assert r_sse.status_code == 200
    assert "event: token" in r_sse.text
    assert "50 mm" in r_sse.text
    assert "event: done" in r_sse.text

    # Disparo consecutivo imediato (< 2s) deve acionar rate-limit 429
    r_flood = client.post(
        "/api/chat/stream",
        headers=headers,
        json={"pergunta": "Outra pergunta seguida sem esperar"},
    )
    assert r_flood.status_code == 429

    # Pergunta acima de 1200 caracteres deve retornar 422
    r_longa = client.post(
        "/api/chat/stream",
        headers={"X-Device-Id": "dbv_outro_dev_99"},
        json={"pergunta": "A" * 1220},
    )
    assert r_longa.status_code == 422

    # Verifica que a conversa ficou salva no histórico do dispositivo
    r_convs = client.get("/api/conversations", headers=headers)
    assert r_convs.status_code == 200
    lista = r_convs.json()
    assert len(lista) == 1
    conv_id = lista[0]["id"]

    # Exporta caderno completo da conversa em PDF
    r_pdf_conv = client.get(f"/api/pdf/conversa/{conv_id}", headers=headers)
    assert r_pdf_conv.status_code == 200
    assert r_pdf_conv.content.startswith(b"%PDF-")


def test_quiz_interativo_estruturado_e_reidratacao(tmp_path: Path) -> None:
    client = _criar_client_teste(tmp_path)
    headers = {"X-Device-Id": "dbv_quiz_tester_01"}

    r_quiz = client.post(
        "/api/quiz/generate",
        headers=headers,
        json={
            "tema": "Posição dos emblemas no Uniforme de Gala",
            "categoria": "UNIFORMES",
            "quantidade": 3,
            "nivel": "regular",
        },
    )
    assert r_quiz.status_code == 200
    dados = r_quiz.json()
    assert len(dados["quiz"]["questoes"]) == 3
    assert dados["quiz"]["questoes"][0]["indice_correto"] == 1
    assert "Gabarito Comentado da Mara" in dados["markdown"]

    # Ao reabrir a conversa salva, o objeto `quiz` estruturado deve estar preservado
    conv_id = dados["conversa_id"]
    r_det = client.get(f"/api/conversations/{conv_id}", headers=headers)
    assert r_det.status_code == 200
    msgs = r_det.json()["mensagens"]
    assert msgs[-1]["quiz"] is not None
    assert len(msgs[-1]["quiz"]["questoes"]) == 3

    # Exclusão da conversa
    time.sleep(0.05)
    r_del = client.delete(f"/api/conversations/{conv_id}", headers=headers)
    assert r_del.status_code == 204
    assert client.get("/api/conversations", headers=headers).json() == []


def test_autenticacao_e_painel_diretoria(tmp_path: Path) -> None:
    client = _criar_client_teste(tmp_path)

    # Sem login deve bloquear com 401
    assert client.get("/api/admin/dashboard").status_code == 401

    # Senha incorreta -> 401
    assert client.post("/api/admin/login", json={"senha": "errada"}).status_code == 401

    # Senha correta -> grava cookie HttpOnly assinado
    r_ok = client.post("/api/admin/login", json={"senha": "senha_diretoria_segura"})
    assert r_ok.status_code == 200
    assert r_ok.json()["autenticado"] is True

    # Consulta dashboard autenticado via cookie
    client.post(
        "/api/feedback",
        json={"pergunta": "Onde fica o D1?", "resposta": "Na manga direita.", "positivo": True},
    )
    r_dash = client.get("/api/admin/dashboard")
    assert r_dash.status_code == 200
    dash = r_dash.json()
    assert dash["metricas"]["avaliacoes"] == 1
    assert dash["metricas"]["taxa_aprovacao"] == "100%"

    # Logout invalida sessão
    client.post("/api/admin/logout")
    assert client.get("/api/admin/dashboard").status_code == 401


def test_servir_pwa_estatico_manifest_e_service_worker(tmp_path: Path) -> None:
    client = _criar_client_teste(tmp_path)
    pasta_out = RAIZ / "web" / "out"
    if not (pasta_out / "index.html").exists():
        return

    r_home = client.get("/")
    assert r_home.status_code == 200
    assert "text/html" in r_home.headers["content-type"]
    assert "Mara" in r_home.text

    r_manifest = client.get("/manifest.webmanifest")
    assert r_manifest.status_code == 200
    assert "application/manifest+json" in r_manifest.headers["content-type"]
    assert r_manifest.json()["id"] == "/"

    r_sw = client.get("/sw.js")
    assert r_sw.status_code == 200
    assert r_sw.headers.get("service-worker-allowed") == "/"
