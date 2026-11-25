"use client";

import React, { useEffect, useRef, useState } from "react";
import { IconChat, IconChevronDown, IconQuiz, IconSend } from "./Icons";
import type { CategoriaItem } from "@/lib/types";

interface ComposerProps {
  valor: string;
  onChange: (novo: string) => void;
  onSubmit: () => void;
  carregando: boolean;
  desabilitado?: boolean;
  modo: "consulta" | "simulado";
  onChangeModo: (modo: "consulta" | "simulado") => void;
  qtdQuestoes: number;
  onChangeQtdQuestoes: (n: number) => void;
  nivelQuiz: "aspirante" | "regular" | "lideranca";
  onChangeNivelQuiz: (nivel: "aspirante" | "regular" | "lideranca") => void;
  categoriaAtiva: string;
  onChangeCategoria: (cat: string) => void;
  categorias: CategoriaItem[];
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
}

export function Composer({
  valor,
  onChange,
  onSubmit,
  carregando,
  desabilitado = false,
  modo,
  onChangeModo,
  qtdQuestoes,
  onChangeQtdQuestoes,
  nivelQuiz,
  onChangeNivelQuiz,
  categoriaAtiva,
  onChangeCategoria,
  categorias,
  inputRef,
}: ComposerProps) {
  const [popoverAberto, setPopoverAberto] = useState(false);
  const popoverContainerRef = useRef<HTMLDivElement | null>(null);
  const formRef = useRef<HTMLFormElement | null>(null);

  // Auto-ajuste de altura do textarea conforme digita
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    const proximo = Math.min(el.scrollHeight, 180);
    el.style.height = `${proximo}px`;
    el.style.overflowY = el.scrollHeight > 180 ? "auto" : "hidden";
  }, [valor, inputRef]);

  // Fecha popover ao clicar fora ou pressionar Escape
  useEffect(() => {
    if (!popoverAberto) return;

    function handlePointerDown(ev: MouseEvent) {
      if (
        popoverContainerRef.current &&
        !popoverContainerRef.current.contains(ev.target as Node)
      ) {
        setPopoverAberto(false);
      }
    }

    function handleKeyDown(ev: KeyboardEvent) {
      if (ev.key === "Escape") {
        setPopoverAberto(false);
        requestAnimationFrame(() => inputRef.current?.focus());
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [popoverAberto, inputRef]);

  function focarCampoEntrada() {
    requestAnimationFrame(() => {
      const el = inputRef.current;
      if (el) {
        el.focus();
        const fim = el.value.length;
        el.setSelectionRange(fim, fim);
      }
    });
  }

  function escolherModo(novoModo: "consulta" | "simulado", fechar = true) {
    onChangeModo(novoModo);
    if (fechar) {
      setPopoverAberto(false);
      focarCampoEntrada();
    }
  }

  // IME-safe Enter-to-submit (modern-web-guidance: ime-safe-enter-submit)
  function handleTextareaKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (event.nativeEvent.isComposing || event.keyCode === 229) {
        return;
      }
      if (!carregando && !desabilitado && valor.trim().length > 0) {
        formRef.current?.requestSubmit();
      }
    }
  }

  function handleFormSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    if (carregando || desabilitado || !valor.trim()) return;
    setPopoverAberto(false);
    onSubmit();
  }

  const rotuloCategoria =
    categorias.find((c) => c.id === categoriaAtiva)?.rotulo || categoriaAtiva;

  return (
    <div className="composer-dock">
      <form ref={formRef} onSubmit={handleFormSubmit} className="composer-capsule">
        {categoriaAtiva !== "TODAS" && (
          <div className="composer-scope-row">
            <span className="scope-chip">
              <span>Escopo: {rotuloCategoria}</span>
              <button
                type="button"
                aria-label="Limpar filtro de manual e pesquisar em todos"
                onClick={() => {
                  onChangeCategoria("TODAS");
                  focarCampoEntrada();
                }}
              >
                ×
              </button>
            </span>
          </div>
        )}

        <label htmlFor="mara-chat-input" className="sr-only">
          {modo === "simulado"
            ? "Tema do simulado oficial para os Desbravadores"
            : "Pergunta para a instrutora Mara"}
        </label>
        <textarea
          ref={inputRef}
          id="mara-chat-input"
          rows={1}
          value={valor}
          disabled={desabilitado}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleTextareaKeyDown}
          placeholder={
            desabilitado
              ? "Modo offline ativo — consulte os guias salvos na Biblioteca Oficial."
              : modo === "simulado"
                ? "Digite o tema do simulado (ex.: Insígnias no bolso do RUD, Classe de Amigo, Ideais)..."
                : "Pergunte à Mara sobre o RUD, Classes, Especialidades ou Administração do Clube..."
          }
          className="composer-textarea"
        />

        <div className="composer-toolbar">
          <div className="composer-left-tools">
            <label htmlFor="mara-scope-select" className="sr-only">
              Filtrar categoria de manual
            </label>
            <select
              id="mara-scope-select"
              value={categoriaAtiva}
              onChange={(e) => {
                onChangeCategoria(e.target.value);
                focarCampoEntrada();
              }}
              className="composer-scope-select"
              style={{
                minBlockSize: 34,
                padding: "0 10px",
                borderRadius: "var(--r-pill)",
                border: "1px solid var(--hairline)",
                background: "var(--p-surface)",
                color: "var(--p-muted)",
                fontSize: "0.78rem",
                fontWeight: 500,
                maxInlineSize: "190px",
              }}
            >
              {categorias.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.rotulo}
                </option>
              ))}
            </select>
          </div>

          {/* Seletor de Modo Inline estilo Gemini ao lado do botão de enviar */}
          <div ref={popoverContainerRef} className="composer-right-tools" style={{ position: "relative" }}>
            <button
              type="button"
              aria-haspopup="dialog"
              aria-expanded={popoverAberto}
              onClick={() => setPopoverAberto((prev) => !prev)}
              className={`mode-trigger-pill ${modo === "simulado" ? "is-quiz" : ""}`}
            >
              <span className="mode-icon-circle">
                {modo === "simulado" ? <IconQuiz size={13} /> : <IconChat size={13} />}
              </span>
              <span>
                {modo === "simulado" ? `Simulado · ${qtdQuestoes}q` : "Consulta"}
              </span>
              <IconChevronDown size={13} />
            </button>

            {popoverAberto && (
              <div
                role="dialog"
                aria-label="Modo de atuação da Mara"
                className="mode-popover"
              >
                <div className="eyebrow-mono" style={{ padding: "2px 6px 8px" }}>
                  Modo da Instrutora
                </div>

                <button
                  type="button"
                  onClick={() => escolherModo("consulta", true)}
                  className={`mode-option-card ${modo === "consulta" ? "is-selected" : ""}`}
                >
                  <span className="mode-icon-circle" style={{ marginTop: 2 }}>
                    <IconChat size={13} />
                  </span>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: "0.87rem", color: "var(--p-ink)" }}>
                      Consulta Oficial
                    </div>
                    <div style={{ fontSize: "0.77rem", color: "var(--p-muted)", lineHeight: 1.35 }}>
                      Respostas diretas com citação de manual e página da DSA.
                    </div>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => escolherModo("simulado", false)}
                  className={`mode-option-card ${modo === "simulado" ? "is-selected" : ""}`}
                  style={{ marginTop: 4 }}
                >
                  <span className="mode-icon-circle" style={{ marginTop: 2 }}>
                    <IconQuiz size={13} />
                  </span>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: "0.87rem", color: "var(--p-ink)" }}>
                      Simulado Interativo
                    </div>
                    <div style={{ fontSize: "0.77rem", color: "var(--p-muted)", lineHeight: 1.35 }}>
                      Questões clicáveis na tela + prova em PDF com folha do instrutor.
                    </div>
                  </div>
                </button>

                {modo === "simulado" && (
                  <div className="quiz-suboptions">
                    <div className="eyebrow-mono">Quantidade de questões</div>
                    <div className="segmented-row">
                      {[3, 5, 8].map((n) => (
                        <button
                          key={n}
                          type="button"
                          onClick={() => {
                            onChangeQtdQuestoes(n);
                            setPopoverAberto(false);
                            focarCampoEntrada();
                          }}
                          className={`segmented-btn ${qtdQuestoes === n ? "is-active" : ""}`}
                        >
                          {n} questões
                        </button>
                      ))}
                    </div>

                    <div className="eyebrow-mono" style={{ marginTop: 4 }}>
                      Nível da unidade
                    </div>
                    <div className="segmented-row">
                      {(
                        [
                          { id: "aspirante", label: "Aspirante" },
                          { id: "regular", label: "Classes" },
                          { id: "lideranca", label: "Liderança" },
                        ] as const
                      ).map((nv) => (
                        <button
                          key={nv.id}
                          type="button"
                          onClick={() => {
                            onChangeNivelQuiz(nv.id);
                            setPopoverAberto(false);
                            focarCampoEntrada();
                          }}
                          className={`segmented-btn ${nivelQuiz === nv.id ? "is-active" : ""}`}
                        >
                          {nv.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            <button
              type="submit"
              disabled={carregando || desabilitado || !valor.trim()}
              aria-label={modo === "simulado" ? "Gerar simulado" : "Enviar pergunta"}
              className="send-circle-btn"
            >
              <IconSend size={17} />
            </button>
          </div>
        </div>
      </form>

      <div className="composer-footnote">
        Fundamentada exclusivamente nos manuais oficiais da Divisão Sul-Americana (DSA).
      </div>
    </div>
  );
}
