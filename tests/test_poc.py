"""Testes automatizados da PoC do Chat DBV."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from chatdbv.chunking import Pagina, dividir_documento, extrair_paginas, limpar_texto
from chatdbv.config import verificar_senha_admin
from chatdbv.db import SqliteRepositorio
from chatdbv.embeddings import normalizar
from chatdbv.ingestao import inferir_categoria, ingerir_arquivo
from chatdbv.rag import montar_prompt_usuario


class FakeEmbedder:
    """Embedder determinístico para testes offline da busca híbrida."""

    def _vetor_para_texto(self, texto: str) -> np.ndarray:
        t = texto.lower()
        v = np.zeros(768, dtype=np.float32)
        if "uniforme" in t or "excelência" in t or "manga" in t:
            v[0] = 1.0
        if "lais de guia" in t or "nó" in t or "amigo" in t:
            v[1] = 1.0
        if "triângulo" in t or "voto" in t or "sarli" in t:
            v[2] = 1.0
        if "unidade" in t or "sentido" in t or "maranata" in t:
            v[3] = 1.0
        if np.linalg.norm(v) == 0:
            v[4] = 1.0
        return normalizar(v.tolist())

    def documentos(self, textos: list[str]) -> list[np.ndarray]:
        return [self._vetor_para_texto(t) for t in textos]

    def consulta(self, pergunta: str) -> np.ndarray:
        return self._vetor_para_texto(pergunta)


def test_limpar_texto_e_marcadores_de_pagina() -> None:
    txt = "Palavra hife-\nnizada em duas linhas.\nQuebra simples.\n\nNovo parágrafo."
    limpo = limpar_texto(txt)
    assert "hifenizada" in limpo
    assert "\n\nNovo parágrafo." in limpo

    manual_1 = RAIZ / "data" / "manuais" / "01_historia_e_ideais_desbravadores_dsa.md"
    paginas = extrair_paginas(manual_1)
    assert len(paginas) == 3
    assert [p.numero for p in paginas] == [1, 2, 3]


def test_chunk_nunca_atravessa_paginas() -> None:
    p1 = Pagina(1, "Parágrafo da página um. " * 60)
    p2 = Pagina(2, "Parágrafo da página dois. " * 60)
    chunks = dividir_documento([p1, p2])
    assert len(chunks) >= 4
    for c in chunks:
        if "página um" in c.texto:
            assert "página dois" not in c.texto
            assert c.pagina == 1
        if "página dois" in c.texto:
            assert "página um" not in c.texto
            assert c.pagina == 2


def test_normalizacao_embedding_768d() -> None:
    bruto = [float(i) for i in range(1, 769)]
    normed = normalizar(bruto)
    assert normed.shape == (768,)
    assert np.isclose(np.linalg.norm(normed), 1.0, atol=1e-6)


def test_ingestao_idempotente_busca_hibrida_e_admin(tmp_path: Path) -> None:
    repo = SqliteRepositorio(tmp_path / "teste.sqlite")
    repo.inicializar_esquema()
    embedder = FakeEmbedder()

    manuais_dir = RAIZ / "data" / "manuais"
    for arq in sorted(manuais_dir.glob("*.md")):
        res = ingerir_arquivo(arq, repo, embedder)
        assert not res.ignorado_por_cache
        assert res.chunks > 0
        # Segunda chamada deve bater no cache SHA-256
        res2 = ingerir_arquivo(arq, repo, embedder)
        assert res2.ignorado_por_cache

    # Busca sobre Insígnia de Excelência no filtro UNIFORMES
    pergunta = "Onde fica a Insígnia de Excelência no uniforme de gala?"
    vetor_q = embedder.consulta(pergunta)
    trechos = repo.buscar_hibrido(vetor_q, pergunta, top_k=3, categoria="UNIFORMES")
    assert len(trechos) >= 1
    assert trechos[0].categoria == "UNIFORMES"
    assert any("Insígnia de Excelência" in t.texto for t in trechos)

    prompt = montar_prompt_usuario(pergunta, trechos)
    assert "CONTEXTO DOS MANUAIS OFICIAIS" in prompt
    assert f"pág. {trechos[0].pagina}" in prompt

    # Métodos do Painel Administrativo (chunks, feedbacks e remoção de manual)
    manuais = repo.listar_manuais()
    assert len(manuais) == 4
    chunks_m0 = repo.listar_chunks_manual(manuais[0].id)
    assert len(chunks_m0) > 0

    repo.registrar_feedback("Pergunta teste?", "Resposta teste.", True)
    fbs = repo.listar_feedbacks()
    assert len(fbs) == 1
    assert fbs[0].positivo is True
    repo.remover_feedback(fbs[0].id)
    assert len(repo.listar_feedbacks()) == 0

    repo.remover_manual(manuais[0].id)
    assert len(repo.listar_manuais()) == 3


def test_autenticacao_admin_safe_equal() -> None:
    assert verificar_senha_admin("admin123", "admin123") is True
    assert verificar_senha_admin("errada", "admin123") is False
    assert verificar_senha_admin("", "admin123") is False


def test_inferencia_de_categoria() -> None:
    assert inferir_categoria("02_regulamento_uniformes_dsa.md") == "UNIFORMES"
    assert inferir_categoria("03_classes_regulares_e_lideranca_dsa.md") == "CLASSES"
    assert inferir_categoria("01_historia_e_ideais_desbravadores_dsa.md") == "HISTORIA_IDEAIS"
    assert inferir_categoria("04_manual_administrativo_e_ordem_unida_dsa.md") == "ADMINISTRATIVO"


def test_persistencia_conversas_navegador_e_biblioteca(tmp_path: Path) -> None:
    from chatdbv.biblioteca import CATALOGO_BIBLIOTECA
    from chatdbv.db import TrechoRecuperado
    from chatdbv.ingestao import CATEGORIAS_VALIDAS

    assert len(CATALOGO_BIBLIOTECA) >= 8
    for item in CATALOGO_BIBLIOTECA:
        assert item.categoria in CATEGORIAS_VALIDAS

    repo = SqliteRepositorio(tmp_path / "conv.sqlite")
    repo.inicializar_esquema()

    trecho_fake = TrechoRecuperado(
        chunk_id=1,
        manual_titulo="Regulamento de Uniformes",
        arquivo="02_regulamento_uniformes_dsa.md",
        categoria="UNIFORMES",
        pagina=2,
        texto="O Emblema D1 fica na manga direita.",
        similaridade=0.92,
        score_rrf=0.03,
    )
    msgs = [
        {"role": "user", "content": "Onde fica o D1?"},
        {
            "role": "assistant",
            "content": "Na manga direita.",
            "pergunta": "Onde fica o D1?",
            "trechos": [trecho_fake],
        },
    ]

    repo.salvar_conversa(
        conversa_id="conv_123",
        device_id="dbv_device_abc",
        titulo="Onde fica o D1?",
        modo="consulta",
        categoria="UNIFORMES",
        mensagens=msgs,
        last_interaction_id="inter_001",
    )

    lista = repo.listar_conversas_dispositivo("dbv_device_abc")
    assert len(lista) == 1
    assert lista[0].titulo == "Onde fica o D1?"

    carregada = repo.carregar_conversa("conv_123", "dbv_device_abc")
    assert carregada is not None
    resumo, msgs_lidas = carregada
    assert resumo.categoria == "UNIFORMES"
    assert len(msgs_lidas) == 2
    assert msgs_lidas[1]["trechos"][0].manual_titulo == "Regulamento de Uniformes"

    repo.remover_conversa("conv_123", "dbv_device_abc")
    assert len(repo.listar_conversas_dispositivo("dbv_device_abc")) == 0

