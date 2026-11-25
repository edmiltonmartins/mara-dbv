// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Edmilton Cabral Martins Junior <junior.edmilton@gmail.com>

"use client";

import React, { useCallback, useEffect, useState } from "react";
import { IconTrash } from "./Icons";
import {
  alterarSenhaAdmin,
  buscarDashboardAdmin,
  loginAdmin,
  logoutAdmin,
  removerFeedbackAdmin,
  removerManualAdmin,
  salvarConfigAdmin,
  uploadManuaisAdmin,
  verificarSessaoAdmin,
} from "@/lib/api";
import type { AdminDashboardPayload } from "@/lib/types";

interface AdminViewProps {
  onConfigAtualizada: () => void;
}

type SubAbaAdmin = "config" | "manuais" | "feedbacks" | "seguranca";

export function AdminView({ onConfigAtualizada }: AdminViewProps) {
  const [verificando, setVerificando] = useState(true);
  const [autenticado, setAutenticado] = useState(false);
  const [senhaLogin, setSenhaLogin] = useState("");
  const [erroLogin, setErroLogin] = useState<string | null>(null);
  const [entrando, setEntrando] = useState(false);

  const [dashboard, setDashboard] = useState<AdminDashboardPayload | null>(null);
  const [subAba, setSubAba] = useState<SubAbaAdmin>("config");
  const [avisoSucesso, setAvisoSucesso] = useState<string | null>(null);
  const [avisoErro, setAvisoErro] = useState<string | null>(null);

  // Campos de configuração
  const [nomeClube, setNomeClube] = useState("");
  const [modeloChat, setModeloChat] = useState("");
  const [topK, setTopK] = useState(5);
  const [geminiKey, setGeminiKey] = useState("");
  const [dbUrl, setDbUrl] = useState("");
  const [exibirFontes, setExibirFontes] = useState(true);
  const [chatAtivo, setChatAtivo] = useState(true);
  const [msgManutencao, setMsgManutencao] = useState("");
  const [salvandoCfg, setSalvandoCfg] = useState(false);

  // Upload de manuais
  const [catUpload, setCatUpload] = useState("UNIFORMES");
  const [forcarReindex, setForcarReindex] = useState(true);
  const [arquivosSelecionados, setArquivosSelecionados] = useState<File[]>([]);
  const [enviandoUpload, setEnviandoUpload] = useState(false);

  // Alteração de senha
  const [novaSenha, setNovaSenha] = useState("");
  const [confirmaSenha, setConfirmaSenha] = useState("");
  const [salvandoSenha, setSalvandoSenha] = useState(false);

  const carregarDadosPainel = useCallback(async () => {
    const dados = await buscarDashboardAdmin();
    setDashboard(dados);
    setNomeClube(dados.config.nome_clube);
    setModeloChat(dados.config.modelo_chat);
    setTopK(dados.config.top_k);
    setDbUrl(dados.config.database_url || "");
    setExibirFontes(dados.config.exibir_detalhes_tecnicos);
    setChatAtivo(dados.config.chat_ativo);
    setMsgManutencao(dados.config.mensagem_manutencao);
  }, []);

  useEffect(() => {
    verificarSessaoAdmin()
      .then(async (ok) => {
        setAutenticado(ok);
        if (ok) {
          await carregarDadosPainel();
        }
      })
      .catch(() => setAutenticado(false))
      .finally(() => setVerificando(false));
  }, [carregarDadosPainel]);

  async function handleLogin(ev: React.FormEvent) {
    ev.preventDefault();
    if (!senhaLogin.trim() || entrando) return;
    setEntrando(true);
    setErroLogin(null);
    try {
      await loginAdmin(senhaLogin);
      setSenhaLogin("");
      setAutenticado(true);
      await carregarDadosPainel();
    } catch (e) {
      setErroLogin(e instanceof Error ? e.message : "Senha incorreta.");
    } finally {
      setEntrando(false);
    }
  }

  async function handleLogout() {
    await logoutAdmin();
    setAutenticado(false);
    setDashboard(null);
  }

  async function handleSalvarConfig(ev: React.FormEvent) {
    ev.preventDefault();
    setSalvandoCfg(true);
    setAvisoErro(null);
    setAvisoSucesso(null);
    try {
      await salvarConfigAdmin({
        nome_clube: nomeClube,
        modelo_chat: modeloChat,
        top_k: topK,
        gemini_api_key: geminiKey.trim() || undefined,
        database_url: dbUrl,
        exibir_detalhes_tecnicos: exibirFontes,
        chat_ativo: chatAtivo,
        mensagem_manutencao: msgManutencao,
      });
      setGeminiKey("");
      await carregarDadosPainel();
      onConfigAtualizada();
      setAvisoSucesso("Configurações do clube e da IA salvas com sucesso.");
    } catch (e) {
      setAvisoErro(e instanceof Error ? e.message : "Erro ao salvar configurações.");
    } finally {
      setSalvandoCfg(false);
    }
  }

  async function handleUploadManuais(ev: React.FormEvent) {
    ev.preventDefault();
    if (arquivosSelecionados.length === 0 || enviandoUpload) return;
    setEnviandoUpload(true);
    setAvisoErro(null);
    setAvisoSucesso(null);
    try {
      const res = await uploadManuaisAdmin({
        categoria: catUpload,
        forcar: forcarReindex,
        arquivos: arquivosSelecionados,
      });
      setArquivosSelecionados([]);
      await carregarDadosPainel();
      onConfigAtualizada();
      const totalChunks = res.reduce((acc, r) => acc + r.chunks, 0);
      setAvisoSucesso(`${res.length} arquivo(s) processado(s) (${totalChunks} trechos indexados).`);
    } catch (e) {
      setAvisoErro(e instanceof Error ? e.message : "Erro ao indexar manuais.");
    } finally {
      setEnviandoUpload(false);
    }
  }

  async function handleAlterarSenha(ev: React.FormEvent) {
    ev.preventDefault();
    setAvisoErro(null);
    setAvisoSucesso(null);
    if (novaSenha.trim().length < 4) {
      setAvisoErro("A nova senha deve ter pelo menos 4 caracteres.");
      return;
    }
    if (novaSenha !== confirmaSenha) {
      setAvisoErro("A confirmação não coincide com a nova senha.");
      return;
    }
    setSalvandoSenha(true);
    try {
      await alterarSenhaAdmin(novaSenha);
      setNovaSenha("");
      setConfirmaSenha("");
      setAvisoSucesso("Senha administrativa atualizada.");
    } catch (e) {
      setAvisoErro(e instanceof Error ? e.message : "Erro ao atualizar senha.");
    } finally {
      setSalvandoSenha(false);
    }
  }

  if (verificando) {
    return (
      <div className="page-container">
        <p style={{ color: "var(--p-muted)" }}>Verificando credenciais da diretoria...</p>
      </div>
    );
  }

  if (!autenticado) {
    return (
      <div className="page-container" style={{ maxInlineSize: 480 }}>
        <header className="page-header">
          <span className="eyebrow-mono">Acesso Restrito · Diretoria</span>
          <h1 style={{ fontSize: "1.65rem" }}>Painel Administrativo</h1>
          <p style={{ margin: 0, color: "var(--p-muted)", fontSize: "0.92rem" }}>
            Gerencie o nome do clube, chave Gemini, acervo normativo DSA e avaliações das unidades.
          </p>
        </header>

        <form onSubmit={handleLogin} className="form-panel">
          <div className="field-group">
            <label htmlFor="admin-password" className="field-label">
              Senha da Diretoria
            </label>
            <input
              id="admin-password"
              type="password"
              autoComplete="current-password"
              required
              value={senhaLogin}
              onChange={(e) => setSenhaLogin(e.target.value)}
              placeholder="Digite a senha administrativa"
              className="field-input"
            />
            {erroLogin && (
              <span role="alert" className="field-error">
                {erroLogin}
              </span>
            )}
          </div>

          <button type="submit" disabled={entrando} className="btn-base btn-primary">
            {entrando ? "Autenticando..." : "Entrar no Painel"}
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="page-container">
      <header
        className="page-header"
        style={{
          flexDirection: "row",
          alignItems: "flex-end",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <span className="eyebrow-mono">
            Painel da Diretoria · Motor {dashboard?.backend || "SQLite"}
          </span>
          <h1 style={{ fontSize: "clamp(1.45rem, 2.4vw, 1.95rem)", marginTop: 4 }}>
            Gestão da Instrutora Mara
          </h1>
        </div>
        <button type="button" onClick={handleLogout} className="btn-base">
          Encerrar sessão
        </button>
      </header>

      {dashboard && (
        <section aria-label="Métricas operacionais" className="metrics-strip">
          <div className="metric-box">
            <div className="eyebrow-mono">Manuais Ativos</div>
            <div className="metric-value">{dashboard.metricas.manuais}</div>
          </div>
          <div className="metric-box">
            <div className="eyebrow-mono">Trechos RAG</div>
            <div className="metric-value">{dashboard.metricas.trechos}</div>
          </div>
          <div className="metric-box">
            <div className="eyebrow-mono">Avaliações</div>
            <div className="metric-value">{dashboard.metricas.avaliacoes}</div>
          </div>
          <div className="metric-box">
            <div className="eyebrow-mono">Aprovação</div>
            <div className="metric-value">{dashboard.metricas.taxa_aprovacao}</div>
          </div>
        </section>
      )}

      {avisoSucesso && (
        <div
          role="status"
          style={{
            padding: "12px 16px",
            borderRadius: "var(--r-sm)",
            background: "var(--p-ok-bg)",
            border: "1px solid var(--p-ok)",
            color: "var(--p-ok)",
            fontSize: "0.88rem",
            fontWeight: 500,
          }}
        >
          {avisoSucesso}
        </div>
      )}

      {avisoErro && (
        <div
          role="alert"
          style={{
            padding: "12px 16px",
            borderRadius: "var(--r-sm)",
            background: "var(--p-danger-bg)",
            border: "1px solid var(--p-danger)",
            color: "var(--p-danger)",
            fontSize: "0.88rem",
            fontWeight: 500,
          }}
        >
          {avisoErro}
        </div>
      )}

      <div className="filter-pills-scroller" role="tablist" aria-label="Abas administrativas">
        {(
          [
            { id: "config", label: "Clube & Modelo IA" },
            { id: "manuais", label: "Acervo de Manuais" },
            { id: "feedbacks", label: "Avaliações Recebidas" },
            { id: "seguranca", label: "Senha de Acesso" },
          ] as const
        ).map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={subAba === t.id}
            onClick={() => {
              setSubAba(t.id);
              setAvisoErro(null);
              setAvisoSucesso(null);
            }}
            className={`filter-pill ${subAba === t.id ? "is-active" : ""}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {subAba === "config" && dashboard && (
        <form onSubmit={handleSalvarConfig} className="form-panel">
          <div className="field-group">
            <label htmlFor="cfg-nome-clube" className="field-label">
              Identificação do Clube ou Região
            </label>
            <input
              id="cfg-nome-clube"
              type="text"
              value={nomeClube}
              onChange={(e) => setNomeClube(e.target.value)}
              className="field-input"
            />
            <span className="field-hint">
              Impresso no cabeçalho editorial de todas as provas e cadernos em PDF.
            </span>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: 16,
            }}
          >
            <div className="field-group">
              <label htmlFor="cfg-modelo" className="field-label">
                Modelo Gemini Principal
              </label>
              <select
                id="cfg-modelo"
                value={modeloChat}
                onChange={(e) => setModeloChat(e.target.value)}
                className="field-select"
              >
                {dashboard.config.modelos_disponiveis.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>

            <div className="field-group">
              <label htmlFor="cfg-topk" className="field-label">
                Trechos recuperados por consulta (Top-K: {topK})
              </label>
              <input
                id="cfg-topk"
                type="number"
                min={2}
                max={12}
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="field-input"
              />
            </div>
          </div>

          <div className="field-group">
            <label htmlFor="cfg-api-key" className="field-label">
              Chave da API Google Gemini{" "}
              {dashboard.config.api_key_configurada ? "(Configurada ✓)" : "(Pendente)"}
            </label>
            <input
              id="cfg-api-key"
              type="password"
              autoComplete="off"
              value={geminiKey}
              onChange={(e) => setGeminiKey(e.target.value)}
              placeholder="Deixe em branco para manter a chave atual"
              className="field-input"
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={exibirFontes}
                onChange={(e) => setExibirFontes(e.target.checked)}
              />
              <span style={{ fontSize: "0.9rem" }}>
                Exibir referências técnicas de manual e página ao final das respostas
              </span>
            </label>

            <label style={{ display: "inline-flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={chatAtivo}
                onChange={(e) => setChatAtivo(e.target.checked)}
              />
              <span style={{ fontSize: "0.9rem" }}>
                Manter atendimento público da Mara ativo
              </span>
            </label>
          </div>

          {!chatAtivo && (
            <div className="field-group">
              <label htmlFor="cfg-manutencao" className="field-label">
                Aviso exibido durante pausa de manutenção
              </label>
              <textarea
                id="cfg-manutencao"
                value={msgManutencao}
                onChange={(e) => setMsgManutencao(e.target.value)}
                className="field-textarea"
              />
            </div>
          )}

          <div>
            <button type="submit" disabled={salvandoCfg} className="btn-base btn-primary">
              {salvandoCfg ? "Salvando..." : "Salvar configurações"}
            </button>
          </div>
        </form>
      )}

      {subAba === "manuais" && dashboard && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <form onSubmit={handleUploadManuais} className="form-panel">
            <h2 style={{ fontSize: "1.08rem" }}>Indexar novos manuais ou regulamentos (.pdf / .md)</h2>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                gap: 16,
              }}
            >
              <div className="field-group">
                <label htmlFor="up-cat" className="field-label">
                  Categoria Normativa
                </label>
                <select
                  id="up-cat"
                  value={catUpload}
                  onChange={(e) => setCatUpload(e.target.value)}
                  className="field-select"
                >
                  {dashboard.config.categorias_validas.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.rotulo}
                    </option>
                  ))}
                </select>
              </div>

              <div className="field-group">
                <label htmlFor="up-files" className="field-label">
                  Arquivos oficiais
                </label>
                <input
                  id="up-files"
                  type="file"
                  multiple
                  accept=".pdf,.md,.txt"
                  onChange={(e) => setArquivosSelecionados(Array.from(e.target.files || []))}
                  className="field-input"
                />
              </div>
            </div>

            <label style={{ display: "inline-flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={forcarReindex}
                onChange={(e) => setForcarReindex(e.target.checked)}
              />
              <span style={{ fontSize: "0.88rem" }}>
                Forçar reindexação caso o documento já exista na base
              </span>
            </label>

            <div>
              <button
                type="submit"
                disabled={enviandoUpload || arquivosSelecionados.length === 0}
                className="btn-base btn-primary"
              >
                {enviandoUpload ? "Gerando embeddings e indexando..." : "Enviar e indexar"}
              </button>
            </div>
          </form>

          <div
            tabIndex={0}
            role="region"
            aria-label="Manuais cadastrados"
            className="table-wrapper"
          >
            <table>
              <thead>
                <tr>
                  <th>Título</th>
                  <th>Arquivo</th>
                  <th>Categoria</th>
                  <th>Trechos</th>
                  <th>Ação</th>
                </tr>
              </thead>
              <tbody>
                {dashboard.manuais.map((m) => (
                  <tr key={m.id}>
                    <td style={{ fontWeight: 600, color: "var(--p-ink)" }}>{m.titulo}</td>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}>{m.arquivo}</td>
                    <td>{m.categoria}</td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>{m.total_chunks}</td>
                    <td>
                      <button
                        type="button"
                        aria-label={`Remover manual ${m.titulo}`}
                        onClick={async () => {
                          await removerManualAdmin(m.id);
                          await carregarDadosPainel();
                          onConfigAtualizada();
                        }}
                        className="icon-btn"
                        style={{ color: "var(--p-danger)" }}
                      >
                        <IconTrash size={15} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {subAba === "feedbacks" && dashboard && (
        <div className="form-panel">
          <h2 style={{ fontSize: "1.08rem" }}>
            Avaliações das Unidades ({dashboard.feedbacks.length})
          </h2>
          {dashboard.feedbacks.length === 0 ? (
            <p style={{ color: "var(--p-muted)", margin: 0 }}>
              Nenhuma avaliação registrada até o momento.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {dashboard.feedbacks.map((fb) => (
                <div
                  key={fb.id}
                  style={{
                    padding: 14,
                    borderRadius: "var(--r-sm)",
                    border: "1px solid var(--hairline)",
                    background: "var(--p-surface)",
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 12,
                  }}
                >
                  <div style={{ minInlineSize: 0 }}>
                    <span
                      className="eyebrow-mono"
                      style={{ color: fb.positivo ? "var(--p-ok)" : "var(--p-danger)" }}
                    >
                      {fb.positivo ? "Útil (Positivo)" : "Revisar (Negativo)"} · {fb.criado_em}
                    </span>
                    <div style={{ fontWeight: 600, marginTop: 4 }}>{fb.pergunta}</div>
                    <p
                      style={{
                        margin: "6px 0 0",
                        fontSize: "0.84rem",
                        color: "var(--p-muted)",
                      }}
                    >
                      {fb.resposta.slice(0, 240)}
                      {fb.resposta.length > 240 ? "..." : ""}
                    </p>
                  </div>
                  <button
                    type="button"
                    aria-label="Excluir avaliação"
                    onClick={async () => {
                      await removerFeedbackAdmin(fb.id);
                      await carregarDadosPainel();
                    }}
                    className="icon-btn"
                  >
                    <IconTrash size={15} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {subAba === "seguranca" && (
        <form onSubmit={handleAlterarSenha} className="form-panel" style={{ maxInlineSize: 480 }}>
          <h2 style={{ fontSize: "1.08rem" }}>Atualizar Senha da Diretoria</h2>
          <div className="field-group">
            <label htmlFor="sec-nova" className="field-label">
              Nova senha
            </label>
            <input
              id="sec-nova"
              type="password"
              autoComplete="new-password"
              required
              minLength={4}
              value={novaSenha}
              onChange={(e) => setNovaSenha(e.target.value)}
              className="field-input"
            />
          </div>
          <div className="field-group">
            <label htmlFor="sec-conf" className="field-label">
              Confirmar nova senha
            </label>
            <input
              id="sec-conf"
              type="password"
              autoComplete="new-password"
              required
              minLength={4}
              value={confirmaSenha}
              onChange={(e) => setConfirmaSenha(e.target.value)}
              className="field-input"
            />
          </div>
          <div>
            <button type="submit" disabled={salvandoSenha} className="btn-base btn-primary">
              {salvandoSenha ? "Atualizando..." : "Alterar senha"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
