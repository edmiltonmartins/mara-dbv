"use client";

import React, { useEffect, useState } from "react";
import { IconChat, IconDownload, IconOffline, IconQuiz } from "./Icons";
import { MarkdownContent } from "./MarkdownContent";
import { buscarBiblioteca, resolverUrlApi } from "@/lib/api";
import type { BibliotecaPayload, CategoriaItem, GuiaBiblioteca } from "@/lib/types";

interface LibraryViewProps {
  categorias: CategoriaItem[];
  online: boolean;
  onConsultarGuia: (guia: GuiaBiblioteca) => void;
  onGerarSimuladoGuia: (guia: GuiaBiblioteca) => void;
}

export function LibraryView({
  categorias,
  online,
  onConsultarGuia,
  onGerarSimuladoGuia,
}: LibraryViewProps) {
  const [dados, setDados] = useState<BibliotecaPayload | null>(null);
  const [usandoCacheOffline, setUsandoCacheOffline] = useState(false);
  const [filtroCat, setFiltroCat] = useState<string>("TODAS");
  const [guiaExpandidoId, setGuiaExpandidoId] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let cancelado = false;
    buscarBiblioteca()
      .then(({ dados: payload, offlineFallback }) => {
        if (!cancelado) {
          setDados(payload);
          setUsandoCacheOffline(offlineFallback);
          setErro(null);
        }
      })
      .catch((e) => {
        if (!cancelado) {
          setErro(e instanceof Error ? e.message : "Erro ao carregar biblioteca.");
        }
      });
    return () => {
      cancelado = true;
    };
  }, [online]);

  const guiasFiltrados = (dados?.guias || []).filter(
    (g) => filtroCat === "TODAS" || g.categoria === filtroCat,
  );

  return (
    <div className="page-container">
      <header className="page-header">
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span className="eyebrow-mono">Acervo Oficial · Divisão Sul-Americana</span>
          {(usandoCacheOffline || !online) && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                padding: "2px 9px",
                borderRadius: "var(--r-pill)",
                background: "var(--p-warn-bg)",
                color: "var(--p-warn)",
                fontFamily: "var(--font-mono)",
                fontSize: "0.7rem",
                fontWeight: 600,
              }}
            >
              <IconOffline size={12} />
              <span>Modo Acampamento (Cache Local)</span>
            </span>
          )}
        </div>
        <h1 style={{ fontSize: "clamp(1.5rem, 2.5vw, 2rem)" }}>Biblioteca do Conselheiro</h1>
        <p style={{ margin: 0, color: "var(--p-muted)", maxInlineSize: "64ch" }}>
          Guias rápidos de bolso com resumos estruturados disponíveis mesmo sem sinal no
          acampamento, além de exportação editorial em PDF e simulados em 1 clique.
        </p>
      </header>

      <div
        className="filter-pills-scroller"
        role="tablist"
        aria-label="Filtrar guias por categoria"
      >
        {categorias.map((cat) => (
          <button
            key={cat.id}
            type="button"
            role="tab"
            aria-selected={filtroCat === cat.id}
            onClick={() => setFiltroCat(cat.id)}
            className={`filter-pill ${filtroCat === cat.id ? "is-active" : ""}`}
          >
            {cat.rotulo}
          </button>
        ))}
      </div>

      {erro && (
        <div className="form-panel" style={{ borderColor: "var(--p-danger)", color: "var(--p-danger)" }}>
          {erro}
        </div>
      )}

      <section aria-label="Guias rápidos oficiais" className="library-grid">
        {guiasFiltrados.map((guia) => {
          const expandido = guiaExpandidoId === guia.id;
          return (
            <article key={guia.id} className="library-card">
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div className="library-card-top">
                  <div className="library-emblem-box">
                    <img
                      src={resolverUrlApi(guia.emblema_url)}
                      alt={`Insígnia ${guia.titulo}`}
                      width={44}
                      height={44}
                      loading="lazy"
                    />
                  </div>
                  <div style={{ minInlineSize: 0 }}>
                    <span className="eyebrow-mono" style={{ color: "var(--p-action)" }}>
                      {guia.badge}
                    </span>
                    <h2 style={{ fontSize: "1.06rem", marginTop: 2 }}>{guia.titulo}</h2>
                    <p
                      style={{
                        margin: "4px 0 0",
                        fontSize: "0.86rem",
                        color: "var(--p-muted)",
                        lineHeight: 1.45,
                      }}
                    >
                      {guia.subtitulo}
                    </p>
                  </div>
                </div>

                <div>
                  <button
                    type="button"
                    aria-expanded={expandido}
                    onClick={() => setGuiaExpandidoId(expandido ? null : guia.id)}
                    style={{
                      border: 0,
                      background: "transparent",
                      padding: "4px 0",
                      color: "var(--p-action)",
                      fontSize: "0.83rem",
                      fontWeight: 600,
                    }}
                  >
                    {expandido ? "Ocultar resumo de bolso ↑" : "Ler resumo de bolso (offline) ↓"}
                  </button>

                  {expandido && (
                    <div
                      style={{
                        marginTop: 8,
                        padding: "14px 16px",
                        borderRadius: "var(--r-sm)",
                        background: "var(--p-surface)",
                        border: "1px solid var(--hairline)",
                      }}
                    >
                      <MarkdownContent content={guia.resumo_markdown} />
                    </div>
                  )}
                </div>
              </div>

              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: 8,
                  paddingTop: 12,
                  borderTop: "1px solid var(--hairline)",
                }}
              >
                <button
                  type="button"
                  disabled={!online}
                  onClick={() => onConsultarGuia(guia)}
                  className="btn-base"
                >
                  <IconChat size={14} />
                  <span>Consultar na Mara</span>
                </button>

                <button
                  type="button"
                  disabled={!online}
                  onClick={() => onGerarSimuladoGuia(guia)}
                  className="btn-base"
                >
                  <IconQuiz size={14} />
                  <span>Simulado</span>
                </button>

                {online && (
                  <a
                    href={resolverUrlApi(guia.pdf_url)}
                    download={`guia_mara_${guia.id}.pdf`}
                    className="btn-base btn-primary"
                    style={{ marginInlineStart: "auto" }}
                  >
                    <IconDownload size={14} />
                    <span>Guia PDF</span>
                  </a>
                )}
              </div>
            </article>
          );
        })}
      </section>
    </div>
  );
}
