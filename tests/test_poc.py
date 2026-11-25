# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Edmilton Cabral Martins Junior <junior.edmilton@gmail.com>

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
    arquivos_teste = sorted(manuais_dir.glob("0*.md"))[:4]
    for arq in arquivos_teste:
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


def test_exportacao_pdf_consulta_simulado_e_biblioteca() -> None:
    import io
    from pypdf import PdfReader
    from chatdbv.biblioteca import CATALOGO_BIBLIOTECA
    from chatdbv.db import TrechoRecuperado
    from chatdbv.pdf_export import (
        gerar_pdf_conversa,
        gerar_pdf_guia_biblioteca,
        gerar_pdf_resposta,
    )

    trecho = TrechoRecuperado(
        chunk_id=10,
        manual_titulo="Regulamento de Uniformes",
        arquivo="02_regulamento_uniformes_dsa.md",
        categoria="UNIFORMES",
        pagina=3,
        texto="A Insígnia de Excelência é usada acima da tampa do bolso esquerdo.",
        similaridade=0.95,
        score_rrf=0.032,
    )

    # 1. PDF de resposta de consulta com acentuação e emojis
    pdf_consulta = gerar_pdf_resposta(
        pergunta="Onde fica a Insígnia de Excelência no uniforme de gala?",
        resposta_md="## Posição Oficial\n\n- Fica **acima da tampa do bolso esquerdo** ✅.",
        trechos=[trecho],
        nome_clube="Clube Órion",
        categoria="UNIFORMES",
        modo_quiz=False,
    )
    assert pdf_consulta.startswith(b"%PDF-")
    leitor1 = PdfReader(io.BytesIO(pdf_consulta))
    assert len(leitor1.pages) >= 1

    # 2. PDF de simulado com bloco <details> de gabarito (deve separar prova na pág. 1 e gabarito na pág. 2)
    resposta_quiz = (
        "## 🎯 Simulado de Uniformes\n\n"
        "1. Onde fica a Insígnia de Excelência?\n"
        "A) No bolso direito\n"
        "B) Acima da tampa do bolso esquerdo\n\n"
        "<details><summary>Ver Gabarito Comentado</summary>\n"
        "1. **B** — Conforme o Regulamento de Uniformes (pág. 3).\n"
        "</details>"
    )
    pdf_quiz = gerar_pdf_resposta(
        pergunta="Simulado sobre uniformes",
        resposta_md=resposta_quiz,
        trechos=[trecho],
        nome_clube="Clube Órion",
        categoria="UNIFORMES",
        modo_quiz=True,
    )
    assert pdf_quiz.startswith(b"%PDF-")
    leitor2 = PdfReader(io.BytesIO(pdf_quiz))
    assert len(leitor2.pages) >= 2
    texto_pag1 = leitor2.pages[0].extract_text()
    texto_pag2 = leitor2.pages[1].extract_text()
    assert "GABARITO COMENTADO" not in texto_pag1.upper()
    assert "INSTRUTOR" in texto_pag2.upper()

    # 2b. Simulado com cabeçalho Markdown de Gabarito (sem tag <details>) também deve separar páginas
    resposta_quiz_md = (
        "1. Qual a distância do Emblema D1?\n"
        "A) 15 mm\n"
        "B) 50 mm\n\n"
        "### Gabarito Comentado da Mara\n"
        "1. **B** — 50 mm abaixo da costura do ombro direito."
    )
    pdf_quiz_md = gerar_pdf_resposta(
        pergunta="Distância do D1",
        resposta_md=resposta_quiz_md,
        trechos=[trecho],
        nome_clube="Clube Órion",
        categoria="UNIFORMES",
        modo_quiz=True,
    )
    leitor_md = PdfReader(io.BytesIO(pdf_quiz_md))
    assert len(leitor_md.pages) >= 2

    # 3. PDF de conversa completa e de guia da Biblioteca (tabela completa sem truncamento em 42 chars)
    pdf_conv = gerar_pdf_conversa(
        titulo="Estudo de Uniformes",
        mensagens=[
            {"role": "user", "content": "Onde fica a Insígnia de Excelência?"},
            {"role": "assistant", "content": resposta_quiz, "trechos": [trecho]},
        ],
        nome_clube="Clube Órion",
        categoria="UNIFORMES",
        modo_quiz=True,
    )
    assert pdf_conv.startswith(b"%PDF-")

    item_bib = CATALOGO_BIBLIOTECA[0]
    pdf_bib = gerar_pdf_guia_biblioteca(
        titulo=item_bib.titulo,
        subtitulo=item_bib.subtitulo,
        badge=item_bib.badge,
        resumo_md=item_bib.resumo_markdown,
        nome_clube="Clube Órion",
        logo_relativo=item_bib.logo_relativo,
    )
    assert pdf_bib.startswith(b"%PDF-")
    leitor_bib = PdfReader(io.BytesIO(pdf_bib))
    texto_bib = leitor_bib.pages[0].extract_text()
    assert "50 mm (5,0 cm) abaixo da costura do ombro" in texto_bib


def test_blindagem_zero_token_guard_e_limites() -> None:
    from chatdbv.db import TrechoRecuperado
    from chatdbv.rag import (
        MAX_CARACTERES_PERGUNTA,
        MAX_OUTPUT_TOKENS,
        RESPOSTA_FORA_DE_ESCOPO_PADRAO,
        RESPOSTA_SAUDACAO_PADRAO,
        verificar_resposta_zero_token,
    )

    assert MAX_CARACTERES_PERGUNTA == 1200
    assert MAX_OUTPUT_TOKENS == 4096

    # 1. Saudações sem trechos devem retornar saudação padrão sem gastar tokens
    assert verificar_resposta_zero_token("Olá Mara!", []) == RESPOSTA_SAUDACAO_PADRAO
    assert verificar_resposta_zero_token("Maranata", []) == RESPOSTA_SAUDACAO_PADRAO
    assert verificar_resposta_zero_token("Bom dia!", []) == RESPOSTA_SAUDACAO_PADRAO

    # 2. Pergunta fora de escopo sem trechos nos manuais
    assert (
        verificar_resposta_zero_token("Como fazer bolo de chocolate?", [])
        == RESPOSTA_FORA_DE_ESCOPO_PADRAO
    )

    # 3. Pergunta com trechos relevantes não deve ser interceptada pelo guardião
    trecho_valido = TrechoRecuperado(
        chunk_id=1,
        manual_titulo="Uniformes",
        arquivo="02_uniformes.md",
        categoria="UNIFORMES",
        pagina=1,
        texto="Uniforme de gala padrão DSA",
        similaridade=0.88,
        score_rrf=0.03,
    )
    assert (
        verificar_resposta_zero_token(
            "Qual a cor do lenço de desbravador?", [trecho_valido]
        )
        is None
    )


def test_failover_cooldown_modelos_503() -> None:
    from chatdbv.rag import (
        _MODELOS_INDISPONIVEIS_ATE,
        _erro_indisponibilidade_modelo,
        _lista_modelos,
        _marcar_modelo_indisponivel,
    )

    _MODELOS_INDISPONIVEIS_ATE.clear()
    assert _erro_indisponibilidade_modelo(RuntimeError("503 UNAVAILABLE: high demand")) is True
    assert _erro_indisponibilidade_modelo(RuntimeError("504 DEADLINE_EXCEEDED")) is True
    assert _erro_indisponibilidade_modelo(ValueError("erro sintatico qualquer")) is False

    _marcar_modelo_indisponivel("gemini-3.8-flash")
    ordem = _lista_modelos("gemini-3.8-flash")
    assert ordem[0] == "gemini-3.5-flash-lite"
    assert ordem[-1] == "gemini-3.8-flash"
    _MODELOS_INDISPONIVEIS_ATE.clear()


def test_supressao_saudacao_conversa_em_andamento() -> None:
    from chatdbv.rag import (
        RESPOSTA_SAUDACAO_EM_ANDAMENTO,
        RESPOSTA_SAUDACAO_PADRAO,
        montar_prompt_usuario,
        remover_saudacao_inicial_repetida,
        verificar_resposta_zero_token,
    )

    assert verificar_resposta_zero_token("Oi", [], conversa_em_andamento=False) == RESPOSTA_SAUDACAO_PADRAO
    assert verificar_resposta_zero_token("Oi", [], conversa_em_andamento=True) == RESPOSTA_SAUDACAO_EM_ANDAMENTO

    bruto = "Maranata, desbravador! Que alegria responder isso!\n\nSegundo a OMD 009, os noivos devem estar investidos."
    limpo = remover_saudacao_inicial_repetida(bruto)
    assert not limpo.lower().startswith("maranata")
    assert limpo.startswith("Segundo a OMD 009")

    # Garante que conteúdo legítimo sobre a palavra Maranata não é cortado
    conteudo_real = "O significado da saudação Maranata vem do aramaico e quer dizer Ora vem, Senhor Jesus."
    assert remover_saudacao_inicial_repetida(conteudo_real) == conteudo_real

    prompt_cont = montar_prompt_usuario(
        "E no bolso direito?",
        [],
        historico_recente=[{"role": "user", "content": "Como organizar o bolso esquerdo?"}],
    )
    assert "JÁ ESTÁ EM ANDAMENTO" in prompt_cont



