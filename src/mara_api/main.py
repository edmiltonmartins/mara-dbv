# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Edmilton Cabral Martins Junior <junior.edmilton@gmail.com>

"""Aplicação Principal FastAPI + SSE + Static PWA da Mara v2.0."""
from __future__ import annotations

import functools
import io
import json
import logging
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Iterator

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image, ImageDraw

from chatdbv.biblioteca import CATALOGO_BIBLIOTECA
from chatdbv.config import (
    MODELOS_DISPONIVEIS,
    RAIZ,
    Config,
    limpar_chave,
    salvar_configuracoes_no_env,
    verificar_senha_admin,
)
from chatdbv.db import RepositorioRAG, TrechoRecuperado, criar_repositorio
from chatdbv.embeddings import Embedder
from chatdbv.ingestao import (
    CATEGORIAS_VALIDAS,
    ROTULOS_CATEGORIAS,
    calcular_sha256,
    ingerir_arquivo,
    ingerir_pasta,
)
from chatdbv.pdf_export import (
    gerar_pdf_conversa,
    gerar_pdf_guia_biblioteca,
    gerar_pdf_resposta,
)
from chatdbv.rag import MotorRAG

from .schemas import (
    AdminConfigUpdateRequest,
    AdminLoginRequest,
    AdminSenhaUpdateRequest,
    ChatRequest,
    ConversaDetalheDTO,
    ConversaResumoDTO,
    FeedbackRequest,
    MensagemDTO,
    PdfRespostaRequest,
    QuizEstruturadoDTO,
    QuizRequest,
    QuizResponse,
    TrechoDTO,
)
from .security import (
    COOKIE_ADMIN_NOME,
    COOKIE_DEVICE_NOME,
    LimitadorTaxaMemoria,
    exigir_admin_autenticado,
    extrair_device_id,
    extrair_ip_cliente,
    gerar_token_sessao_admin,
    validar_token_sessao_admin,
)

PASTA_LOGOS_DSA = RAIZ / "assets" / "imagens" / "Logos"
PASTA_LOGOS_OFICIAIS = RAIZ / "assets" / "logos"
PASTA_WEB_OUT = RAIZ / "web" / "out"

SUGESTOES_INICIAIS = [
    {
        "id": "rud_bolsos",
        "titulo": "Consultar posição de insígnias no bolso (RUD)",
        "categoria": "UNIFORMES",
        "modo": "consulta",
        "pergunta": "Qual a posição correta dos emblemas e tiras nos bolsos do uniforme de gala segundo o RUD?",
    },
    {
        "id": "classe_amigo",
        "titulo": "Ver requisitos da Classe de Amigo (10 anos)",
        "categoria": "CLASSES",
        "modo": "consulta",
        "pergunta": "Quais são os principais requisitos da Classe de Amigo (10 anos) e Amigo da Natureza?",
    },
    {
        "id": "sistema_unidades",
        "titulo": "Revisar regras do Sistema de Unidades",
        "categoria": "ADMINISTRATIVO",
        "modo": "consulta",
        "pergunta": "Quantos desbravadores formam uma unidade e qual o papel do conselheiro e do capitão?",
    },
    {
        "id": "quiz_ideais",
        "titulo": "Gerar simulado interativo sobre os Ideais DSA",
        "categoria": "HISTORIA_IDEAIS",
        "modo": "simulado",
        "pergunta": "Voto, Lei, Alvo, Lema e Objetivo dos Desbravadores",
    },
]


def gerar_titulo_conversa(primeira_pergunta: str) -> str:
    limpo = " ".join((primeira_pergunta or "").strip().split())
    if len(limpo) <= 46:
        return limpo or "Conversa com a Mara"
    return limpo[:43].rstrip() + "..."


def _trecho_para_dto(t: TrechoRecuperado) -> TrechoDTO:
    return TrechoDTO(
        chunk_id=t.chunk_id,
        manual_titulo=t.manual_titulo,
        arquivo=t.arquivo,
        categoria=t.categoria,
        pagina=t.pagina,
        texto=t.texto,
        similaridade=round(float(t.similaridade), 4),
        score_rrf=round(float(t.score_rrf), 5),
    )


def _dto_para_trecho(d: TrechoDTO) -> TrechoRecuperado:
    return TrechoRecuperado(
        chunk_id=d.chunk_id,
        manual_titulo=d.manual_titulo,
        arquivo=d.arquivo,
        categoria=d.categoria,
        pagina=d.pagina,
        texto=d.texto,
        similaridade=d.similaridade,
        score_rrf=d.score_rrf,
    )


@functools.lru_cache(maxsize=64)
def _processar_emblema_png(caminho_str: str, altura_max: int = 160) -> bytes:
    caminho = Path(caminho_str)
    img = Image.open(caminho).convert("RGBA")
    w, h = img.size
    for sx, sy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (0, h // 2)]:
        try:
            r, g, b, a = img.getpixel((sx, sy))
            if a > 0 and r > 235 and g > 235 and b > 235:
                ImageDraw.floodfill(img, (sx, sy), (255, 255, 255, 0), thresh=28)
        except Exception:
            pass
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    if img.height > altura_max:
        prop = altura_max / float(img.height)
        img = img.resize((max(1, int(img.width * prop)), altura_max), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def criar_aplicacao(
    repo_override: RepositorioRAG | None = None,
    motor_override: object | None = None,
    cfg_override: Config | None = None,
) -> FastAPI:
    limitador = LimitadorTaxaMemoria()

    @asynccontextmanager
    async def lifespan(app_inst: FastAPI):
        cfg_boot = app_inst.state.cfg_override or Config.carregar()
        repo_boot = app_inst.state.repo_override or criar_repositorio(cfg_boot)
        app_inst.state.repo_singleton = repo_boot
        try:
            repo_boot.inicializar_esquema()
            pasta_manuais = RAIZ / "data" / "manuais"
            if (
                cfg_boot.gemini_api_key
                and app_inst.state.repo_override is None
                and pasta_manuais.exists()
            ):
                arquivos_disco = [
                    p
                    for p in pasta_manuais.iterdir()
                    if p.is_file() and p.suffix.lower() in (".pdf", ".md", ".txt")
                ]
                precisa_sincronizar = any(
                    not repo_boot.manual_ja_indexado(p.name, calcular_sha256(p))
                    for p in arquivos_disco
                )
                if precisa_sincronizar:
                    def _sincronizar_acervo_bg() -> None:
                        try:
                            emb = Embedder(cfg_boot)
                            ingerir_pasta(pasta_manuais, repo_boot, emb)
                        except Exception as exc:
                            logging.getLogger("mara_api").warning(
                                "Falha na sincronização incremental em background: %s", exc
                            )

                    threading.Thread(
                        target=_sincronizar_acervo_bg,
                        name="mara-rag-sync",
                        daemon=True,
                    ).start()
        except Exception:
            pass
        yield

    app = FastAPI(
        title="Mara — API Oficial (IA dos Desbravadores · Infinito Soft)",
        version="2.0.0",
        lifespan=lifespan,
    )
    app.state.repo_override = repo_override
    app.state.motor_override = motor_override
    app.state.cfg_override = cfg_override
    app.state.repo_singleton = repo_override
    app.state.limitador = limitador

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8501",
            "https://mara.infinitosoft.com",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def obter_cfg() -> Config:
        return app.state.cfg_override or Config.carregar()

    def obter_repo(cfg: Config = Depends(obter_cfg)) -> RepositorioRAG:
        if app.state.repo_override is not None:
            return app.state.repo_override
        if getattr(app.state, "repo_singleton", None) is None:
            r = criar_repositorio(cfg)
            r.inicializar_esquema()
            app.state.repo_singleton = r
        return app.state.repo_singleton

    def obter_motor(
        cfg: Config = Depends(obter_cfg),
        repo: RepositorioRAG = Depends(obter_repo),
    ):
        if app.state.motor_override is not None:
            return app.state.motor_override
        if not cfg.gemini_api_key:
            return None
        assinatura = (
            cfg.gemini_api_key,
            cfg.modelo_chat,
            cfg.top_k,
            cfg.exibir_detalhes_tecnicos,
        )
        atual = getattr(app.state, "motor_singleton", None)
        if atual is None or getattr(app.state, "motor_assinatura", None) != assinatura:
            atual = MotorRAG(cfg=cfg, repo=repo)
            app.state.motor_singleton = atual
            app.state.motor_assinatura = assinatura
        return atual

    # ==================== ROTAS PÚBLICAS DE METADADOS E ATIVOS ====================
    @app.get("/api/health")
    def api_health(
        request: Request,
        response: Response,
        cfg: Config = Depends(obter_cfg),
        repo: RepositorioRAG = Depends(obter_repo),
    ):
        dev_id = extrair_device_id(request)
        if not request.cookies.get(COOKIE_DEVICE_NOME):
            response.set_cookie(
                COOKIE_DEVICE_NOME,
                dev_id,
                max_age=31536000,
                httponly=False,
                samesite="lax",
                path="/",
            )
        try:
            manuais = repo.listar_manuais()
        except Exception:
            manuais = []
        total_chunks = sum(m.total_chunks for m in manuais)
        return {
            "status": "ok",
            "versao": "2.0.0",
            "device_id": dev_id,
            "nome_clube": cfg.nome_clube,
            "chat_ativo": cfg.chat_ativo,
            "mensagem_manutencao": cfg.mensagem_manutencao,
            "exibir_detalhes_tecnicos": cfg.exibir_detalhes_tecnicos,
            "api_configurada": bool(cfg.gemini_api_key) or (app.state.motor_override is not None),
            "total_manuais": len(manuais) or 4,
            "total_chunks": total_chunks,
            "total_guias_biblioteca": len(CATALOGO_BIBLIOTECA),
            "categorias": [
                {"id": "TODAS", "rotulo": "Todos os Manuais"},
                *[
                    {"id": cid, "rotulo": ROTULOS_CATEGORIAS.get(cid, cid)}
                    for cid in CATEGORIAS_VALIDAS
                    if cid != "GERAL"
                ],
            ],
            "sugestoes_iniciais": SUGESTOES_INICIAIS,
        }

    @app.get("/api/emblems/{caminho_rel:path}")
    def api_emblems(caminho_rel: str):
        limpo = caminho_rel.strip("/")
        if ".." in limpo:
            raise HTTPException(status_code=400, detail="Caminho inválido.")

        atalhos = {
            "d1": PASTA_LOGOS_OFICIAIS / "emblema_d1_triangulo.png",
            "lider": PASTA_LOGOS_DSA / "L1" / "globo-lider-desbravador.jpg",
            "guia": PASTA_LOGOS_DSA / "Classes" / "b6_guia.png",
            "infinito": PASTA_LOGOS_OFICIAIS / "infinito-logo-vetorial-dark.svg",
            "infinito-png": PASTA_LOGOS_OFICIAIS / "infinito-logo-transparente.png",
        }
        alvo = atalhos.get(limpo.lower()) or (PASTA_LOGOS_DSA / limpo)
        if not alvo.exists() or not alvo.is_file():
            fallback_svg = RAIZ / "assets" / "emblema_d1.svg"
            if fallback_svg.exists():
                return FileResponse(
                    fallback_svg,
                    media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=604800"},
                )
            raise HTTPException(status_code=404, detail="Emblema não encontrado.")

        if alvo.suffix.lower() == ".svg":
            return FileResponse(
                alvo,
                media_type="image/svg+xml",
                headers={"Cache-Control": "public, max-age=604800, immutable"},
            )

        png_bytes = _processar_emblema_png(str(alvo), altura_max=192)
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=604800, immutable"},
        )

    # ==================== BIBLIOTECA OFICIAL (CACHEÁVEL OFFLINE PELO PWA) ====================
    @app.get("/api/library")
    def api_library(repo: RepositorioRAG = Depends(obter_repo)):
        itens = [
            {
                "id": item.id,
                "titulo": item.titulo,
                "subtitulo": item.subtitulo,
                "categoria": item.categoria,
                "categoria_rotulo": ROTULOS_CATEGORIAS.get(item.categoria, item.categoria),
                "badge": item.badge,
                "emblema_url": f"/api/emblems/{item.logo_relativo}",
                "resumo_markdown": item.resumo_markdown,
                "pergunta_consulta": item.pergunta_consulta,
                "tema_simulado": item.tema_simulado,
                "pdf_url": f"/api/pdf/guia/{item.id}",
            }
            for item in CATALOGO_BIBLIOTECA
        ]
        try:
            manuais = [
                {
                    "id": m.id,
                    "titulo": m.titulo,
                    "arquivo": m.arquivo,
                    "categoria": m.categoria,
                    "categoria_rotulo": ROTULOS_CATEGORIAS.get(m.categoria, m.categoria),
                    "paginas": m.paginas,
                    "total_chunks": m.total_chunks,
                }
                for m in repo.listar_manuais()
            ]
        except Exception:
            manuais = []
        return {"guias": itens, "manuais": manuais}

    # ==================== HISTÓRICO DE CONVERSAS DO DISPOSITIVO ====================
    @app.get("/api/conversations", response_model=list[ConversaResumoDTO])
    def api_listar_conversas(
        request: Request,
        repo: RepositorioRAG = Depends(obter_repo),
    ):
        dev_id = extrair_device_id(request)
        conversas = repo.listar_conversas_dispositivo(dev_id, limite=30)
        return [
            ConversaResumoDTO(
                id=c.id,
                titulo=c.titulo,
                modo=c.modo,
                categoria=c.categoria,
                atualizado_em=c.atualizado_em,
            )
            for c in conversas
        ]

    @app.get("/api/conversations/{conversa_id}", response_model=ConversaDetalheDTO)
    def api_obter_conversa(
        conversa_id: str,
        request: Request,
        repo: RepositorioRAG = Depends(obter_repo),
    ):
        dev_id = extrair_device_id(request)
        carregada = repo.carregar_conversa(conversa_id, dev_id)
        if not carregada:
            raise HTTPException(status_code=404, detail="Conversa não encontrada neste dispositivo.")
        resumo, msgs = carregada
        return ConversaDetalheDTO(
            resumo=ConversaResumoDTO(
                id=resumo.id,
                titulo=resumo.titulo,
                modo=resumo.modo,
                categoria=resumo.categoria,
                atualizado_em=resumo.atualizado_em,
            ),
            mensagens=[
                MensagemDTO(
                    role=m.get("role", "user"),
                    content=m.get("content", ""),
                    pergunta=m.get("pergunta", ""),
                    trechos=[_trecho_para_dto(t) for t in (m.get("trechos") or [])],
                    quiz=m.get("quiz"),
                )
                for m in msgs
            ],
        )

    @app.delete("/api/conversations/{conversa_id}", status_code=status.HTTP_204_NO_CONTENT)
    def api_excluir_conversa(
        conversa_id: str,
        request: Request,
        repo: RepositorioRAG = Depends(obter_repo),
    ):
        dev_id = extrair_device_id(request)
        repo.remover_conversa(conversa_id, dev_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # ==================== CHAT STREAMING (SSE) & SIMULADO INTERATIVO ====================
    @app.post("/api/chat/stream")
    def api_chat_stream(
        payload: ChatRequest,
        request: Request,
        cfg: Config = Depends(obter_cfg),
        repo: RepositorioRAG = Depends(obter_repo),
        motor=Depends(obter_motor),
    ):
        if not cfg.chat_ativo:
            raise HTTPException(status_code=503, detail=cfg.mensagem_manutencao)
        if motor is None:
            raise HTTPException(
                status_code=503,
                detail="Chave da API Gemini pendente. Configure no Painel da Diretoria.",
            )

        dev_id = extrair_device_id(request)
        ip_cli = extrair_ip_cliente(request)
        pergunta_limpa = app.state.limitador.validar_pergunta(
            f"{dev_id}:{ip_cli}", payload.pergunta
        )

        conv_id = payload.conversa_id or f"conv_{uuid.uuid4().hex[:10]}"
        mensagens_previas: list[dict] = []
        last_inter_id: str | None = None
        if payload.conversa_id:
            existente = repo.carregar_conversa(payload.conversa_id, dev_id)
            if existente:
                resumo_ant, mensagens_previas = existente
                last_inter_id = resumo_ant.last_interaction_id

        categoria = payload.categoria or "TODAS"
        modo_quiz = bool(payload.modo_quiz)

        def _gerador_sse() -> Iterator[str]:
            def _evento(tipo: str, dados: dict) -> str:
                return f"event: {tipo}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"

            yield _evento("status", {"etapa": "Consultando os manuais oficiais da DSA..."})
            try:
                ja_iniciada = len(mensagens_previas) > 0
                trechos = motor.recuperar(
                    pergunta_limpa,
                    categoria=categoria,
                    historico_recente=mensagens_previas,
                )
                resp_zero = motor.verificar_resposta_zero_token(
                    pergunta_limpa, trechos, conversa_em_andamento=ja_iniciada
                )

                texto_final = ""
                novo_inter_id = last_inter_id

                if resp_zero is not None and not modo_quiz:
                    texto_final = resp_zero
                    trechos = []
                    yield _evento("token", {"delta": texto_final})
                else:
                    yield _evento(
                        "status",
                        {
                            "etapa": "Elaborando simulado oficial..."
                            if modo_quiz
                            else "Redigindo resposta fundamentada..."
                        },
                    )
                    acumulado = ""
                    try:
                        for pedaco in motor.responder_stream(
                            pergunta=pergunta_limpa,
                            trechos=trechos,
                            modo_quiz=modo_quiz,
                            previous_interaction_id=last_inter_id,
                            historico_recente=mensagens_previas,
                        ):
                            if pedaco:
                                acumulado += pedaco
                                yield _evento("token", {"delta": pedaco})
                    except Exception:
                        if acumulado:
                            yield _evento("reset", {})
                        acumulado = ""

                    if not acumulado.strip():
                        resp_sync = motor.responder(
                            pergunta=pergunta_limpa,
                            categoria=categoria,
                            modo_quiz=modo_quiz,
                            previous_interaction_id=last_inter_id,
                            trechos_pre_recuperados=trechos,
                            historico_recente=mensagens_previas,
                        )
                        texto_final = resp_sync.texto
                        novo_inter_id = resp_sync.interaction_id or last_inter_id
                        yield _evento("token", {"delta": texto_final})
                    else:
                        texto_final = acumulado
                        if getattr(motor, "ultimo_interaction_id", None):
                            novo_inter_id = motor.ultimo_interaction_id

                trechos_dto = [
                    _trecho_para_dto(t).model_dump()
                    for t in (trechos if cfg.exibir_detalhes_tecnicos else [])
                ]
                if trechos_dto:
                    yield _evento("sources", {"trechos": trechos_dto})

                # Salva histórico completo (mantendo trechos internos para exportação de PDF)
                novas_msgs = [
                    *mensagens_previas,
                    {"role": "user", "content": pergunta_limpa},
                    {
                        "role": "assistant",
                        "content": texto_final,
                        "pergunta": pergunta_limpa,
                        "trechos": trechos,
                    },
                ]
                primeira_user = next(
                    (m["content"] for m in novas_msgs if m.get("role") == "user"),
                    pergunta_limpa,
                )
                titulo_conv = gerar_titulo_conversa(primeira_user)
                try:
                    repo.salvar_conversa(
                        conversa_id=conv_id,
                        device_id=dev_id,
                        titulo=titulo_conv,
                        modo="simulado" if modo_quiz else "consulta",
                        categoria=categoria,
                        mensagens=novas_msgs,
                        last_interaction_id=novo_inter_id,
                    )
                except Exception:
                    pass

                yield _evento(
                    "done",
                    {
                        "conversa_id": conv_id,
                        "titulo": titulo_conv,
                        "content": texto_final,
                        "trechos": [_trecho_para_dto(t).model_dump() for t in trechos],
                        "exibir_fontes": cfg.exibir_detalhes_tecnicos,
                    },
                )
            except Exception as exc:
                yield _evento(
                    "error",
                    {"detail": f"Não foi possível concluir a resposta agora ({exc})."},
                )

        return StreamingResponse(
            _gerador_sse(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/api/quiz/generate", response_model=QuizResponse)
    def api_quiz_generate(
        payload: QuizRequest,
        request: Request,
        cfg: Config = Depends(obter_cfg),
        repo: RepositorioRAG = Depends(obter_repo),
        motor=Depends(obter_motor),
    ):
        if not cfg.chat_ativo:
            raise HTTPException(status_code=503, detail=cfg.mensagem_manutencao)
        if motor is None:
            raise HTTPException(
                status_code=503,
                detail="Chave da API Gemini pendente. Configure no Painel da Diretoria.",
            )

        dev_id = extrair_device_id(request)
        ip_cli = extrair_ip_cliente(request)
        tema_limpo = app.state.limitador.validar_pergunta(f"{dev_id}:{ip_cli}", payload.tema)

        conv_id = payload.conversa_id or f"conv_{uuid.uuid4().hex[:10]}"
        mensagens_previas: list[dict] = []
        if payload.conversa_id:
            existente = repo.carregar_conversa(payload.conversa_id, dev_id)
            if existente:
                _, mensagens_previas = existente

        dados_quiz, md_texto, trechos = motor.gerar_quiz_estruturado(
            tema=tema_limpo,
            categoria=payload.categoria,
            quantidade=payload.quantidade,
            nivel=payload.nivel,
        )

        rotulo_user = f"Simulado ({payload.quantidade} questões): {tema_limpo}"
        novas_msgs = [
            *mensagens_previas,
            {"role": "user", "content": rotulo_user},
            {
                "role": "assistant",
                "content": md_texto,
                "pergunta": tema_limpo,
                "trechos": trechos,
                "quiz": dados_quiz if dados_quiz.get("questoes") else None,
            },
        ]
        primeira_user = next(
            (m["content"] for m in novas_msgs if m.get("role") == "user"),
            tema_limpo,
        )
        titulo_conv = gerar_titulo_conversa(primeira_user)
        try:
            repo.salvar_conversa(
                conversa_id=conv_id,
                device_id=dev_id,
                titulo=titulo_conv,
                modo="simulado",
                categoria=payload.categoria or "TODAS",
                mensagens=novas_msgs,
                last_interaction_id=None,
            )
        except Exception:
            pass

        return QuizResponse(
            conversa_id=conv_id,
            titulo_conversa=titulo_conv,
            quiz=QuizEstruturadoDTO(**dados_quiz),
            markdown=md_texto,
            trechos=[_trecho_para_dto(t) for t in trechos],
        )

    # ==================== EXPORTAÇÃO EDITORIAL EM PDF ====================
    @app.post("/api/pdf/resposta")
    def api_pdf_resposta(
        payload: PdfRespostaRequest,
        cfg: Config = Depends(obter_cfg),
    ):
        trechos_obj = [_dto_para_trecho(t) for t in payload.trechos]
        eh_quiz = payload.modo_quiz or ("gabarito" in payload.resposta_md.lower()) or ("<details" in payload.resposta_md.lower())
        pdf_bytes = gerar_pdf_resposta(
            pergunta=payload.pergunta,
            resposta_md=payload.resposta_md,
            trechos=trechos_obj,
            nome_clube=cfg.nome_clube,
            categoria=payload.categoria,
            modo_quiz=eh_quiz,
        )
        prefixo = "simulado_mara" if eh_quiz else "estudo_mara"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{prefixo}.pdf"'},
        )

    @app.get("/api/pdf/conversa/{conversa_id}")
    def api_pdf_conversa(
        conversa_id: str,
        request: Request,
        cfg: Config = Depends(obter_cfg),
        repo: RepositorioRAG = Depends(obter_repo),
    ):
        dev_id = extrair_device_id(request)
        carregada = repo.carregar_conversa(conversa_id, dev_id)
        if not carregada:
            raise HTTPException(status_code=404, detail="Conversa não encontrada.")
        resumo, msgs = carregada
        eh_quiz = resumo.modo == "simulado"
        pdf_bytes = gerar_pdf_conversa(
            titulo=resumo.titulo,
            mensagens=msgs,
            nome_clube=cfg.nome_clube,
            categoria=resumo.categoria,
            modo_quiz=eh_quiz,
        )
        nome_arq = f"{'simulado' if eh_quiz else 'caderno'}_{resumo.id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{nome_arq}"'},
        )

    @app.get("/api/pdf/guia/{item_id}")
    def api_pdf_guia(item_id: str, cfg: Config = Depends(obter_cfg)):
        item = next((i for i in CATALOGO_BIBLIOTECA if i.id == item_id), None)
        if item is None:
            raise HTTPException(status_code=404, detail="Guia da Biblioteca não encontrado.")
        pdf_bytes = gerar_pdf_guia_biblioteca(
            titulo=item.titulo,
            subtitulo=item.subtitulo,
            badge=item.badge,
            resumo_md=item.resumo_markdown,
            nome_clube=cfg.nome_clube,
            logo_relativo=item.logo_relativo,
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="guia_mara_{item.id}.pdf"'},
        )

    # ==================== FEEDBACK PÚBLICO ====================
    @app.post("/api/feedback")
    def api_feedback(
        payload: FeedbackRequest,
        repo: RepositorioRAG = Depends(obter_repo),
    ):
        repo.registrar_feedback(payload.pergunta[:600], payload.resposta[:4000], payload.positivo)
        return {"ok": True}

    # ==================== PAINEL DA DIRETORIA (ADMIN) ====================
    @app.get("/api/admin/session")
    def api_admin_session(request: Request, cfg: Config = Depends(obter_cfg)):
        token = request.cookies.get(COOKIE_ADMIN_NOME) or request.headers.get("x-admin-token")
        return {"autenticado": validar_token_sessao_admin(token, cfg)}

    @app.post("/api/admin/login")
    def api_admin_login(
        payload: AdminLoginRequest,
        request: Request,
        response: Response,
        cfg: Config = Depends(obter_cfg),
    ):
        ip_cli = extrair_ip_cliente(request)
        ok = verificar_senha_admin(payload.senha, cfg.admin_password)
        app.state.limitador.registrar_tentativa_login(ip_cli, sucesso=ok)
        if not ok:
            raise HTTPException(status_code=401, detail="Senha administrativa incorreta.")

        token = gerar_token_sessao_admin(cfg)
        response.set_cookie(
            COOKIE_ADMIN_NOME,
            token,
            max_age=43200,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
            path="/",
        )
        return {"autenticado": True}

    @app.post("/api/admin/logout")
    def api_admin_logout(response: Response):
        response.delete_cookie(COOKIE_ADMIN_NOME, path="/")
        return {"autenticado": False}

    @app.get("/api/admin/dashboard")
    def api_admin_dashboard(
        request: Request,
        cfg: Config = Depends(obter_cfg),
        repo: RepositorioRAG = Depends(obter_repo),
    ):
        exigir_admin_autenticado(request, cfg)
        manuais = repo.listar_manuais()
        feedbacks = repo.listar_feedbacks(limite=100)
        positivos = sum(1 for f in feedbacks if f.positivo)
        taxa = f"{int((positivos / len(feedbacks)) * 100)}%" if feedbacks else "—"
        return {
            "backend": repo.nome_backend,
            "metricas": {
                "manuais": len(manuais),
                "trechos": sum(m.total_chunks for m in manuais),
                "avaliacoes": len(feedbacks),
                "taxa_aprovacao": taxa,
            },
            "config": {
                "nome_clube": cfg.nome_clube,
                "modelo_chat": cfg.modelo_chat,
                "modelos_disponiveis": list(MODELOS_DISPONIVEIS),
                "top_k": cfg.top_k,
                "database_url": cfg.database_url,
                "exibir_detalhes_tecnicos": cfg.exibir_detalhes_tecnicos,
                "chat_ativo": cfg.chat_ativo,
                "mensagem_manutencao": cfg.mensagem_manutencao,
                "api_key_configurada": bool(cfg.gemini_api_key),
                "categorias_validas": [
                    {"id": c, "rotulo": ROTULOS_CATEGORIAS.get(c, c)}
                    for c in CATEGORIAS_VALIDAS
                ],
            },
            "manuais": [
                {
                    "id": m.id,
                    "titulo": m.titulo,
                    "arquivo": m.arquivo,
                    "categoria": m.categoria,
                    "paginas": m.paginas,
                    "total_chunks": m.total_chunks,
                }
                for m in manuais
            ],
            "feedbacks": [
                {
                    "id": f.id,
                    "pergunta": f.pergunta,
                    "resposta": f.resposta,
                    "positivo": f.positivo,
                    "criado_em": f.criado_em,
                }
                for f in feedbacks
            ],
        }

    @app.put("/api/admin/config")
    def api_admin_salvar_config(
        payload: AdminConfigUpdateRequest,
        request: Request,
        cfg: Config = Depends(obter_cfg),
    ):
        exigir_admin_autenticado(request, cfg)
        atualizacoes: dict[str, str] = {}
        if payload.nome_clube is not None:
            atualizacoes["NOME_CLUBE"] = payload.nome_clube.strip() or "Clube de Desbravadores — DSA"
        if payload.gemini_api_key is not None and payload.gemini_api_key.strip():
            atualizacoes["GEMINI_API_KEY"] = limpar_chave(payload.gemini_api_key)
        if payload.modelo_chat is not None:
            atualizacoes["MODELO_CHAT"] = payload.modelo_chat.strip()
        if payload.top_k is not None:
            atualizacoes["TOP_K"] = str(payload.top_k)
        if payload.database_url is not None:
            atualizacoes["DATABASE_URL"] = payload.database_url.strip()
        if payload.exibir_detalhes_tecnicos is not None:
            atualizacoes["EXIBIR_DETALHES_TECNICOS"] = "true" if payload.exibir_detalhes_tecnicos else "false"
        if payload.chat_ativo is not None:
            atualizacoes["CHAT_ATIVO"] = "true" if payload.chat_ativo else "false"
        if payload.mensagem_manutencao is not None:
            atualizacoes["MENSAGEM_MANUTENCAO"] = payload.mensagem_manutencao.strip()

        if atualizacoes:
            salvar_configuracoes_no_env(atualizacoes)
            if app.state.repo_override is None:
                app.state.repo_singleton = None
        return {"ok": True}

    @app.put("/api/admin/password")
    def api_admin_trocar_senha(
        payload: AdminSenhaUpdateRequest,
        request: Request,
        response: Response,
        cfg: Config = Depends(obter_cfg),
    ):
        exigir_admin_autenticado(request, cfg)
        nova = payload.nova_senha.strip()
        salvar_configuracoes_no_env({"ADMIN_PASSWORD": nova})
        novo_cfg = Config.carregar()
        novo_token = gerar_token_sessao_admin(novo_cfg)
        response.set_cookie(
            COOKIE_ADMIN_NOME,
            novo_token,
            max_age=43200,
            httponly=True,
            samesite="lax",
            path="/",
        )
        return {"ok": True}

    @app.post("/api/admin/manuals/upload")
    async def api_admin_upload_manuais(
        request: Request,
        categoria: str = Form("GERAL"),
        forcar: bool = Form(True),
        arquivos: list[UploadFile] = File(...),
        cfg: Config = Depends(obter_cfg),
        repo: RepositorioRAG = Depends(obter_repo),
    ):
        exigir_admin_autenticado(request, cfg)
        if not cfg.gemini_api_key:
            raise HTTPException(
                status_code=400,
                detail="Configure a chave GEMINI_API_KEY antes de indexar novos manuais.",
            )
        cat_alvo = categoria if categoria in CATEGORIAS_VALIDAS else "GERAL"
        pasta_manuais = RAIZ / "data" / "manuais"
        pasta_manuais.mkdir(parents=True, exist_ok=True)
        emb = Embedder(cfg)
        resultados = []
        for arq in arquivos:
            nome_seguro = Path(arq.filename or "manual.md").name
            ext = Path(nome_seguro).suffix.lower()
            if ext not in (".pdf", ".md", ".txt"):
                continue
            conteudo = await arq.read()
            destino = pasta_manuais / nome_seguro
            destino.write_bytes(conteudo)
            res = ingerir_arquivo(
                caminho=destino,
                repo=repo,
                embedder=emb,
                categoria=cat_alvo,
                forcar=forcar,
            )
            resultados.append(
                {
                    "arquivo": res.arquivo,
                    "paginas": res.paginas,
                    "chunks": res.chunks,
                    "ignorado_por_cache": res.ignorado_por_cache,
                }
            )
        return {"ok": True, "resultados": resultados}

    @app.delete("/api/admin/manuals/{manual_id}")
    def api_admin_remover_manual(
        manual_id: int,
        request: Request,
        cfg: Config = Depends(obter_cfg),
        repo: RepositorioRAG = Depends(obter_repo),
    ):
        exigir_admin_autenticado(request, cfg)
        repo.remover_manual(manual_id)
        return {"ok": True}

    @app.delete("/api/admin/feedback/{feedback_id}")
    def api_admin_remover_feedback(
        feedback_id: int,
        request: Request,
        cfg: Config = Depends(obter_cfg),
        repo: RepositorioRAG = Depends(obter_repo),
    ):
        exigir_admin_autenticado(request, cfg)
        repo.remover_feedback(feedback_id)
        return {"ok": True}

    # ==================== SERVIDOR ESTÁTICO DO APP PWA (NEXT.JS STATIC EXPORT) ====================
    @app.get("/{caminho_web:path}", include_in_schema=False)
    def servir_pwa_estatico(caminho_web: str):
        if caminho_web.startswith("api/"):
            raise HTTPException(status_code=404, detail="Endpoint da API não encontrado.")
        if not PASTA_WEB_OUT.exists():
            return Response(
                content="Mara API v2.0 ativa. Execute `npm run build` em `web/` para servir o App PWA.",
                media_type="text/plain; charset=utf-8",
            )

        limpo = caminho_web.strip("/")
        candidatos: list[Path] = []
        if not limpo:
            candidatos.append(PASTA_WEB_OUT / "index.html")
        else:
            candidatos.extend(
                [
                    PASTA_WEB_OUT / limpo,
                    PASTA_WEB_OUT / f"{limpo}.html",
                    PASTA_WEB_OUT / limpo / "index.html",
                ]
            )

        for cand in candidatos:
            try:
                resolvido = cand.resolve()
                if resolvido.is_file() and str(resolvido).startswith(str(PASTA_WEB_OUT.resolve())):
                    cache_hdr = (
                        "public, max-age=31536000, immutable"
                        if "/_next/static/" in f"/{limpo}"
                        else "no-cache"
                    )
                    headers_resp = {"Cache-Control": cache_hdr}
                    media_type: str | None = None
                    if resolvido.suffix.lower() == ".webmanifest":
                        media_type = "application/manifest+json"
                    elif resolvido.name == "sw.js":
                        media_type = "application/javascript; charset=utf-8"
                        headers_resp["Service-Worker-Allowed"] = "/"
                    return FileResponse(resolvido, media_type=media_type, headers=headers_resp)
            except Exception:
                continue

        # Fallback SPA para index.html
        idx_html = PASTA_WEB_OUT / "index.html"
        if idx_html.exists():
            return FileResponse(idx_html, headers={"Cache-Control": "no-cache"})
        raise HTTPException(status_code=404, detail="Página não encontrada.")

    return app


app = criar_aplicacao()
