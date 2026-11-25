// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Edmilton Cabral Martins Junior <junior.edmilton@gmail.com>

"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { AdminView } from "@/components/AdminView";
import { Composer } from "@/components/Composer";
import {
  IconBook,
  IconChat,
  IconDownload,
  IconMenu,
  IconOffline,
  IconQuiz,
  IconThumbDown,
  IconThumbUp,
} from "@/components/Icons";
import { LibraryView } from "@/components/LibraryView";
import { MarkdownContent } from "@/components/MarkdownContent";
import { QuizCard } from "@/components/QuizCard";
import { AbaAtiva, SidebarRail } from "@/components/SidebarRail";
import {
  baixarPdfConversa,
  baixarPdfResposta,
  buscarBiblioteca,
  buscarHealth,
  carregarConversa,
  enviarFeedback,
  enviarPerguntaStream,
  excluirConversa,
  gerarSimuladoInterativo,
  listarConversas,
  resolverUrlApi,
} from "@/lib/api";
import type {
  CategoriaItem,
  ConversaResumo,
  GuiaBiblioteca,
  HealthMetadata,
  MensagemChat,
  SugestaoInicial,
} from "@/lib/types";

const CATEGORIAS_PADRAO: CategoriaItem[] = [
  { id: "TODAS", rotulo: "Todos os Manuais" },
  { id: "UNIFORMES", rotulo: "Uniformes (RUD)" },
  { id: "CLASSES", rotulo: "Cartões de Classes" },
  { id: "ADMINISTRATIVO", rotulo: "Manual Administrativo" },
  { id: "HISTORIA_IDEAIS", rotulo: "História e Ideais" },
  { id: "ESPECIALIDADES", rotulo: "Especialidades" },
];

const SUGESTOES_FALLBACK: SugestaoInicial[] = [
  {
    id: "rud_bolsos",
    titulo: "Consultar posição de insígnias no bolso (RUD)",
    categoria: "UNIFORMES",
    modo: "consulta",
    pergunta:
      "Qual a posição correta dos emblemas e tiras nos bolsos do uniforme de gala segundo o RUD?",
  },
  {
    id: "classe_amigo",
    titulo: "Ver requisitos da Classe de Amigo (10 anos)",
    categoria: "CLASSES",
    modo: "consulta",
    pergunta:
      "Quais são os principais requisitos da Classe de Amigo (10 anos) e Amigo da Natureza?",
  },
  {
    id: "sistema_unidades",
    titulo: "Revisar regras do Sistema de Unidades",
    categoria: "ADMINISTRATIVO",
    modo: "consulta",
    pergunta:
      "Quantos desbravadores formam uma unidade e qual o papel do conselheiro e do capitão?",
  },
  {
    id: "quiz_ideais",
    titulo: "Gerar simulado interativo sobre os Ideais DSA",
    categoria: "HISTORIA_IDEAIS",
    modo: "simulado",
    pergunta: "Voto, Lei, Alvo, Lema e Objetivo dos Desbravadores",
  },
];

export default function MaraAppPage() {
  const [abaAtiva, setAbaAtiva] = useState<AbaAtiva>("chat");
  const [railRecolhida, setRailRecolhida] = useState(false);
  const [mobileMenuAberto, setMobileMenuAberto] = useState(false);
  const [online, setOnline] = useState(true);

  const [health, setHealth] = useState<HealthMetadata | null>(null);
  const [conversas, setConversas] = useState<ConversaResumo[]>([]);
  const [conversaAtivaId, setConversaAtivaId] = useState<string | null>(null);
  const [mensagens, setMensagens] = useState<MensagemChat[]>([]);

  // Controles do Composer
  const [textoEntrada, setTextoEntrada] = useState("");
  const [modo, setModo] = useState<"consulta" | "simulado">("consulta");
  const [qtdQuestoes, setQtdQuestoes] = useState<number>(3);
  const [nivelQuiz, setNivelQuiz] = useState<"aspirante" | "regular" | "lideranca">("regular");
  const [categoriaAtiva, setCategoriaAtiva] = useState<string>("TODAS");
  const [carregandoResposta, setCarregandoResposta] = useState(false);
  const [baixandoCaderno, setBaixandoCaderno] = useState(false);

  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const fimThreadRef = useRef<HTMLDivElement | null>(null);

  const atualizarMetadados = useCallback(async () => {
    try {
      const [h, convs] = await Promise.all([buscarHealth(), listarConversas()]);
      setHealth(h);
      setConversas(convs);
    } catch {
      // Operando offline com cache local
    }
  }, []);

  // Inicialização + pré-aquecimento da Biblioteca para uso offline no acampamento
  useEffect(() => {
    if (typeof window !== "undefined") {
      setOnline(navigator.onLine);
      const hash = window.location.hash.replace("#", "");
      if (hash === "biblioteca" || hash === "diretoria") {
        setAbaAtiva(hash);
      }

      const onOnline = () => setOnline(true);
      const onOffline = () => setOnline(false);
      window.addEventListener("online", onOnline);
      window.addEventListener("offline", onOffline);

      atualizarMetadados();
      // Pré-carrega catálogo da Biblioteca em background para o Modo Acampamento
      buscarBiblioteca().catch(() => {});

      return () => {
        window.removeEventListener("online", onOnline);
        window.removeEventListener("offline", onOffline);
      };
    }
  }, [atualizarMetadados]);

  function mudarAba(novaAba: AbaAtiva) {
    setAbaAtiva(novaAba);
    if (typeof window !== "undefined") {
      const novoHash = novaAba === "chat" ? "" : `#${novaAba}`;
      window.history.replaceState(null, "", novoHash || window.location.pathname);
    }
  }

  function iniciarNovaConversa() {
    setConversaAtivaId(null);
    setMensagens([]);
    mudarAba("chat");
    requestAnimationFrame(() => inputRef.current?.focus());
  }

  async function abrirConversaExistente(id: string) {
    try {
      const det = await carregarConversa(id);
      setConversaAtivaId(det.resumo.id);
      setCategoriaAtiva(det.resumo.categoria || "TODAS");
      setModo(det.resumo.modo === "simulado" ? "simulado" : "consulta");
      setMensagens(
        det.mensagens.map((m, idx) => ({
          id: `${det.resumo.id}_${idx}`,
          role: m.role,
          content: m.content,
          pergunta: m.pergunta,
          trechos: m.trechos || [],
          quiz: m.quiz || null,
        })),
      );
      mudarAba("chat");
    } catch {
      // ignora se indisponível
    }
  }

  async function handleExcluirConversa(id: string) {
    await excluirConversa(id);
    if (conversaAtivaId === id) {
      setConversaAtivaId(null);
      setMensagens([]);
    }
    const lista = await listarConversas();
    setConversas(lista);
  }

  const dispararEnvio = useCallback(
    async (opcoesOverride?: {
      texto: string;
      modoForcado: "consulta" | "simulado";
      categoriaForcada: string;
    }) => {
      const pergunta = (opcoesOverride ? opcoesOverride.texto : textoEntrada).trim();
      const modoAtual = opcoesOverride ? opcoesOverride.modoForcado : modo;
      const catAtual = opcoesOverride ? opcoesOverride.categoriaForcada : categoriaAtiva;

      if (!pergunta || carregandoResposta) return;

      if (!opcoesOverride) {
        setTextoEntrada("");
      }
      mudarAba("chat");
      setCarregandoResposta(true);

      const idMsgUser = `u_${Date.now()}`;
      const idMsgBot = `a_${Date.now() + 1}`;
      const rotuloExibido =
        modoAtual === "simulado" ? `Simulado (${qtdQuestoes} questões): ${pergunta}` : pergunta;

      setMensagens((prev) => [
        ...prev,
        { id: idMsgUser, role: "user", content: rotuloExibido },
        {
          id: idMsgBot,
          role: "assistant",
          content: "",
          pergunta,
          streaming: true,
          etapaStatus:
            modoAtual === "simulado"
              ? "Elaborando simulado interativo nos manuais da DSA..."
              : "Consultando manuais oficiais da DSA...",
        },
      ]);

      requestAnimationFrame(() => {
        fimThreadRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
      });

      try {
        if (modoAtual === "simulado") {
          const resultado = await gerarSimuladoInterativo({
            tema: pergunta,
            conversa_id: conversaAtivaId,
            categoria: catAtual,
            quantidade: qtdQuestoes,
            nivel: nivelQuiz,
          });
          setConversaAtivaId(resultado.conversa_id);
          setMensagens((prev) =>
            prev.map((m) =>
              m.id === idMsgBot
                ? {
                    ...m,
                    content: resultado.markdown,
                    quiz: resultado.quiz?.questoes?.length ? resultado.quiz : null,
                    trechos: resultado.trechos,
                    streaming: false,
                    etapaStatus: undefined,
                  }
                : m,
            ),
          );
        } else {
          let acumulado = "";
          await enviarPerguntaStream(
            {
              pergunta,
              conversa_id: conversaAtivaId,
              categoria: catAtual,
              modo_quiz: false,
            },
            {
              onStatus: (etapa) => {
                setMensagens((prev) =>
                  prev.map((m) => (m.id === idMsgBot ? { ...m, etapaStatus: etapa } : m)),
                );
              },
              onReset: () => {
                acumulado = "";
                setMensagens((prev) =>
                  prev.map((m) => (m.id === idMsgBot ? { ...m, content: "" } : m)),
                );
              },
              onToken: (delta) => {
                acumulado += delta;
                const copia = acumulado;
                setMensagens((prev) =>
                  prev.map((m) =>
                    m.id === idMsgBot ? { ...m, content: copia, etapaStatus: undefined } : m,
                  ),
                );
              },
              onSources: (trechos) => {
                setMensagens((prev) =>
                  prev.map((m) => (m.id === idMsgBot ? { ...m, trechos } : m)),
                );
              },
              onDone: (finalPayload) => {
                setConversaAtivaId(finalPayload.conversa_id);
                setMensagens((prev) =>
                  prev.map((m) =>
                    m.id === idMsgBot
                      ? {
                          ...m,
                          content: finalPayload.content || acumulado,
                          trechos: finalPayload.exibir_fontes ? finalPayload.trechos : [],
                          streaming: false,
                          etapaStatus: undefined,
                        }
                      : m,
                  ),
                );
              },
              onError: (detalhe) => {
                setMensagens((prev) =>
                  prev.map((m) =>
                    m.id === idMsgBot
                      ? {
                          ...m,
                          content: `Não foi possível concluir a consulta: ${detalhe}`,
                          streaming: false,
                          etapaStatus: undefined,
                        }
                      : m,
                  ),
                );
              },
            },
          );
        }

        const listaAtualizada = await listarConversas();
        setConversas(listaAtualizada);
      } catch (err) {
        const msgErro = err instanceof Error ? err.message : "Falha na conexão com a Mara.";
        setMensagens((prev) =>
          prev.map((m) =>
            m.id === idMsgBot
              ? {
                  ...m,
                  content: `Não foi possível concluir agora: ${msgErro}`,
                  streaming: false,
                  etapaStatus: undefined,
                }
              : m,
          ),
        );
      } finally {
        setCarregandoResposta(false);
        requestAnimationFrame(() => inputRef.current?.focus());
      }
    },
    [
      textoEntrada,
      modo,
      categoriaAtiva,
      carregandoResposta,
      qtdQuestoes,
      conversaAtivaId,
      nivelQuiz,
    ],
  );

  function handleConsultarGuia(guia: GuiaBiblioteca) {
    setCategoriaAtiva(guia.categoria);
    setModo("consulta");
    dispararEnvio({
      texto: guia.pergunta_consulta,
      modoForcado: "consulta",
      categoriaForcada: guia.categoria,
    });
  }

  function handleSimuladoGuia(guia: GuiaBiblioteca) {
    setCategoriaAtiva(guia.categoria);
    setModo("simulado");
    dispararEnvio({
      texto: guia.tema_simulado,
      modoForcado: "simulado",
      categoriaForcada: guia.categoria,
    });
  }

  const categorias = health?.categorias?.length ? health.categorias : CATEGORIAS_PADRAO;
  const sugestoes = health?.sugestoes_iniciais?.length
    ? health.sugestoes_iniciais
    : SUGESTOES_FALLBACK;
  const nomeClube = health?.nome_clube || "Clube de Desbravadores — DSA";
  const chatEmManutencao = health ? !health.chat_ativo : false;

  return (
    <div className="app-shell">
      <SidebarRail
        abaAtiva={abaAtiva}
        onSelecionarAba={mudarAba}
        recolhida={railRecolhida}
        onToggleRecolhida={() => setRailRecolhida((p) => !p)}
        mobileAberta={mobileMenuAberto}
        onFecharMobile={() => setMobileMenuAberto(false)}
        conversas={conversas}
        conversaAtivaId={conversaAtivaId}
        onNovaConversa={iniciarNovaConversa}
        onAbrirConversa={abrirConversaExistente}
        onExcluirConversa={handleExcluirConversa}
      />

      <div className="main-stage">
        {/* Barra Superior Compacta (< 12% viewport, única linha) */}
        <header className="top-bar">
          <div className="top-bar-left">
            <button
              type="button"
              aria-label="Abrir menu de navegação"
              onClick={() => setMobileMenuAberto(true)}
              className="icon-btn mobile-menu-trigger"
            >
              <IconMenu size={19} />
            </button>

            <div className="club-pill">
              <img
                src={resolverUrlApi("/api/emblems/d1")}
                alt=""
                width={22}
                height={22}
                style={{ objectFit: "contain" }}
              />
              <span className="club-pill-name">{nomeClube}</span>
            </div>
          </div>

          <div className="top-bar-right">
            <span className="eyebrow-mono top-bar-stats" style={{ display: "inline-block" }}>
              {health?.total_manuais || 4} Manuais DSA · {health?.total_guias_biblioteca || 10} Guias
            </span>

            {abaAtiva === "chat" && conversaAtivaId && online && (
              <button
                type="button"
                disabled={baixandoCaderno}
                onClick={async () => {
                  setBaixandoCaderno(true);
                  try {
                    await baixarPdfConversa(conversaAtivaId);
                  } finally {
                    setBaixandoCaderno(false);
                  }
                }}
                className="btn-base"
              >
                <IconDownload size={14} />
                <span>{baixandoCaderno ? "Exportando..." : "Caderno PDF"}</span>
              </button>
            )}
          </div>
        </header>

        {!online && (
          <div role="status" className="offline-banner">
            <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <IconOffline size={16} />
              <span>
                <strong>Modo Acampamento Offline:</strong> sem sinal de internet. A Biblioteca
                Oficial e seus estudos salvos continuam disponíveis.
              </span>
            </div>
            {abaAtiva !== "biblioteca" && (
              <button
                type="button"
                onClick={() => mudarAba("biblioteca")}
                className="btn-base"
              >
                <IconBook size={14} />
                <span>Abrir Biblioteca Offline</span>
              </button>
            )}
          </div>
        )}

        {abaAtiva === "biblioteca" && (
          <LibraryView
            categorias={categorias}
            online={online}
            onConsultarGuia={handleConsultarGuia}
            onGerarSimuladoGuia={handleSimuladoGuia}
          />
        )}

        {abaAtiva === "diretoria" && <AdminView onConfigAtualizada={atualizarMetadados} />}

        {abaAtiva === "chat" && (
          <main className="chat-viewport">
            {chatEmManutencao && (
              <div
                role="alert"
                style={{
                  marginTop: 20,
                  padding: "14px 18px",
                  borderRadius: "var(--r-md)",
                  background: "var(--p-warn-bg)",
                  border: "1px solid rgba(154, 91, 0, 0.25)",
                  color: "var(--p-warn)",
                }}
              >
                {health?.mensagem_manutencao ||
                  "A Mara está em manutenção rápida pela diretoria. Consulte a Biblioteca Oficial."}
              </div>
            )}

            {mensagens.length === 0 ? (
              <section className="hero-welcome" aria-labelledby="mara-hero-title">
                <div className="hero-header" data-enter="1">
                  <div className="hero-badge-row">
                    <img
                      src={resolverUrlApi("/api/emblems/d1")}
                      alt="Emblema D1 Desbravadores"
                      width={34}
                      height={34}
                      className="hero-d1-mark"
                    />
                    <span className="eyebrow-mono">
                      Maranata · Instrutora Oficial fundamentada na DSA
                    </span>
                  </div>

                  <h1 id="mara-hero-title" className="hero-h1">
                    Orientações fiéis aos manuais da DSA. Prontas para o clube e o acampamento.
                  </h1>

                  <p className="hero-lead">
                    Consulte regras exatas do RUD, requisitos dos Cartões de Classes e do Sistema
                    de Unidades, ou gere simulados interativos e provas em PDF com folha do
                    instrutor separada.
                  </p>
                </div>

                <div
                  className="suggestions-grid"
                  data-enter="2"
                  aria-label="Sugestões rápidas de estudo"
                >
                  {sugestoes.map((sug) => (
                    <button
                      key={sug.id}
                      type="button"
                      disabled={!online || chatEmManutencao}
                      onClick={() => {
                        setCategoriaAtiva(sug.categoria);
                        setModo(sug.modo);
                        dispararEnvio({
                          texto: sug.pergunta,
                          modoForcado: sug.modo,
                          categoriaForcada: sug.categoria,
                        });
                      }}
                      className="suggestion-card"
                    >
                      <span className="suggestion-meta">
                        {sug.modo === "simulado" ? (
                          <IconQuiz size={13} />
                        ) : (
                          <IconChat size={13} />
                        )}
                        <span>
                          {sug.modo === "simulado" ? "Simulado Interativo" : "Consulta Oficial"} ·{" "}
                          {sug.categoria}
                        </span>
                      </span>
                      <span className="suggestion-title">{sug.titulo}</span>
                    </button>
                  ))}
                </div>
              </section>
            ) : (
              <div className="chat-thread" aria-live="polite">
                {mensagens.map((msg) => {
                  if (msg.role === "user") {
                    return (
                      <div key={msg.id} className="msg-user-row">
                        <div className="msg-user-bubble">{msg.content}</div>
                      </div>
                    );
                  }

                  const temQuizInterativo = Boolean(msg.quiz && msg.quiz.questoes?.length > 0);

                  return (
                    <article key={msg.id} className="msg-assistant-card">
                      <div className="msg-assistant-head">
                        <div className="msg-author">
                          <img
                            src={resolverUrlApi("/api/emblems/d1")}
                            alt=""
                            width={24}
                            height={24}
                            className="msg-author-avatar"
                          />
                          <span>Mara · Instrutora DSA</span>
                        </div>
                      </div>

                      {msg.etapaStatus && (
                        <div className="status-streaming" role="status">
                          <span className="pulse-dot" />
                          <span>{msg.etapaStatus}</span>
                        </div>
                      )}

                      {temQuizInterativo && msg.quiz ? (
                        <QuizCard
                          quiz={msg.quiz}
                          perguntaTema={msg.pergunta || msg.quiz.titulo}
                          markdownFallback={msg.content}
                          trechos={msg.trechos || []}
                          categoria={categoriaAtiva}
                          onBaixarPdf={baixarPdfResposta}
                        />
                      ) : (
                        msg.content && <MarkdownContent content={msg.content} />
                      )}

                      {!msg.streaming && msg.trechos && msg.trechos.length > 0 && (
                        <details className="sources-disclosure">
                          <summary>
                            Fontes consultadas nos manuais ({msg.trechos.length} trechos oficiais)
                          </summary>
                          <div className="sources-list">
                            {msg.trechos.map((t, idx) => (
                              <div key={`${t.chunk_id}_${idx}`} className="source-chip">
                                <span className="source-chip-title">{t.manual_titulo}</span>
                                <span className="source-chip-meta">
                                  Página {t.pagina} · {t.categoria}
                                </span>
                              </div>
                            ))}
                          </div>
                        </details>
                      )}

                      {!msg.streaming && msg.content && (
                        <div className="msg-actions-bar">
                          <div className="msg-actions-group">
                            <button
                              type="button"
                              aria-label="Avaliar resposta como útil"
                              disabled={Boolean(msg.feedbackEnviado)}
                              onClick={async () => {
                                await enviarFeedback({
                                  pergunta: msg.pergunta || "",
                                  resposta: msg.content,
                                  positivo: true,
                                });
                                setMensagens((prev) =>
                                  prev.map((m) =>
                                    m.id === msg.id ? { ...m, feedbackEnviado: "up" } : m,
                                  ),
                                );
                              }}
                              className="icon-btn"
                              style={{
                                color:
                                  msg.feedbackEnviado === "up" ? "var(--p-ok)" : undefined,
                              }}
                            >
                              <IconThumbUp size={15} />
                            </button>

                            <button
                              type="button"
                              aria-label="Sinalizar resposta para revisão"
                              disabled={Boolean(msg.feedbackEnviado)}
                              onClick={async () => {
                                await enviarFeedback({
                                  pergunta: msg.pergunta || "",
                                  resposta: msg.content,
                                  positivo: false,
                                });
                                setMensagens((prev) =>
                                  prev.map((m) =>
                                    m.id === msg.id ? { ...m, feedbackEnviado: "down" } : m,
                                  ),
                                );
                              }}
                              className="icon-btn"
                              style={{
                                color:
                                  msg.feedbackEnviado === "down" ? "var(--p-danger)" : undefined,
                              }}
                            >
                              <IconThumbDown size={15} />
                            </button>
                          </div>

                          {!temQuizInterativo && online && (
                            <button
                              type="button"
                              onClick={() =>
                                baixarPdfResposta({
                                  pergunta: msg.pergunta || "Estudo DSA",
                                  resposta_md: msg.content,
                                  trechos: msg.trechos || [],
                                  categoria: categoriaAtiva,
                                  modo_quiz: false,
                                })
                              }
                              className="btn-base"
                            >
                              <IconDownload size={14} />
                              <span>Baixar Estudo (PDF)</span>
                            </button>
                          )}
                        </div>
                      )}
                    </article>
                  );
                })}
                <div ref={fimThreadRef} />
              </div>
            )}

            <Composer
              valor={textoEntrada}
              onChange={setTextoEntrada}
              onSubmit={() => dispararEnvio()}
              carregando={carregandoResposta}
              desabilitado={!online || chatEmManutencao}
              modo={modo}
              onChangeModo={setModo}
              qtdQuestoes={qtdQuestoes}
              onChangeQtdQuestoes={setQtdQuestoes}
              nivelQuiz={nivelQuiz}
              onChangeNivelQuiz={setNivelQuiz}
              categoriaAtiva={categoriaAtiva}
              onChangeCategoria={setCategoriaAtiva}
              categorias={categorias}
              inputRef={inputRef}
            />
          </main>
        )}
      </div>
    </div>
  );
}
