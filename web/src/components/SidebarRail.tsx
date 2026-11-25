"use client";

import React, { useEffect, useState } from "react";
import {
  IconBook,
  IconChat,
  IconInstall,
  IconPlus,
  IconQuiz,
  IconShield,
  IconSidebar,
  IconTrash,
} from "./Icons";
import { resolverUrlApi } from "@/lib/api";
import type { ConversaResumo } from "@/lib/types";

export type AbaAtiva = "chat" | "biblioteca" | "diretoria";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

interface SidebarRailProps {
  abaAtiva: AbaAtiva;
  onSelecionarAba: (aba: AbaAtiva) => void;
  recolhida: boolean;
  onToggleRecolhida: () => void;
  mobileAberta: boolean;
  onFecharMobile: () => void;
  conversas: ConversaResumo[];
  conversaAtivaId: string | null;
  onNovaConversa: () => void;
  onAbrirConversa: (id: string) => void;
  onExcluirConversa: (id: string) => void;
}

export function SidebarRail({
  abaAtiva,
  onSelecionarAba,
  recolhida,
  onToggleRecolhida,
  mobileAberta,
  onFecharMobile,
  conversas,
  conversaAtivaId,
  onNovaConversa,
  onAbrirConversa,
  onExcluirConversa,
}: SidebarRailProps) {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [suportaWebInstall, setSuportaWebInstall] = useState(false);
  const [instalando, setInstalando] = useState(false);

  // Instalação progressiva PWA (modern-web-guidance: install-web-app)
  useEffect(() => {
    if (typeof window === "undefined") return;
    const nav = navigator as Navigator & { install?: () => Promise<void> };
    if (typeof nav.install === "function") {
      setSuportaWebInstall(true);
    }

    function handleBeforeInstall(ev: Event) {
      ev.preventDefault();
      setDeferredPrompt(ev as BeforeInstallPromptEvent);
    }

    window.addEventListener("beforeinstallprompt", handleBeforeInstall);
    return () => window.removeEventListener("beforeinstallprompt", handleBeforeInstall);
  }, []);

  // Fecha gaveta mobile com Escape
  useEffect(() => {
    if (!mobileAberta) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onFecharMobile();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileAberta, onFecharMobile]);

  async function handleInstalarApp() {
    if (instalando) return;
    setInstalando(true);
    try {
      const nav = navigator as Navigator & { install?: () => Promise<void> };
      if (suportaWebInstall && typeof nav.install === "function") {
        await nav.install();
        setSuportaWebInstall(false);
      } else if (deferredPrompt) {
        const promptEvent = deferredPrompt;
        setDeferredPrompt(null);
        await promptEvent.prompt();
        await promptEvent.userChoice;
      }
    } catch {
      // Cancelamento do usuário é esperado
    } finally {
      setInstalando(false);
    }
  }

  const mostrarBotaoInstalar = suportaWebInstall || Boolean(deferredPrompt);

  return (
    <>
      <div
        className={`mobile-backdrop ${mobileAberta ? "is-open" : ""}`}
        onClick={onFecharMobile}
        aria-hidden="true"
      />

      <aside
        aria-label="Navegação principal e histórico"
        className={`sidebar-rail ${recolhida ? "is-collapsed" : ""} ${
          mobileAberta ? "is-mobile-open" : ""
        }`}
      >
        <div className="rail-top">
          <button
            type="button"
            onClick={() => {
              onSelecionarAba("chat");
              onFecharMobile();
            }}
            className="rail-brand rail-hide-collapsed"
            style={{ border: 0, background: "transparent", padding: 0, cursor: "pointer" }}
          >
            <img
              src={resolverUrlApi("/api/emblems/d1")}
              alt=""
              width={28}
              height={28}
              style={{ objectFit: "contain" }}
            />
            <div style={{ textAlign: "left" }}>
              <span className="rail-brand-title">Mara</span>
              <span className="rail-brand-sub">Instrutora DSA</span>
            </div>
          </button>

          <button
            type="button"
            onClick={() => {
              if (mobileAberta) {
                onFecharMobile();
              } else {
                onToggleRecolhida();
              }
            }}
            aria-label={
              mobileAberta
                ? "Fechar menu lateral"
                : recolhida
                  ? "Expandir barra lateral"
                  : "Recolher barra lateral"
            }
            className="icon-btn"
          >
            <IconSidebar size={18} />
          </button>
        </div>

        <nav className="rail-nav" aria-label="Seções do aplicativo">
          <button
            type="button"
            onClick={() => {
              onNovaConversa();
              onFecharMobile();
            }}
            title="Nova consulta"
            className="rail-nav-btn is-new-chat"
          >
            <IconPlus size={17} />
            <span className="rail-hide-collapsed">Nova consulta</span>
          </button>

          <button
            type="button"
            onClick={() => {
              onSelecionarAba("chat");
              onFecharMobile();
            }}
            title="Chat com a Mara"
            className={`rail-nav-btn ${abaAtiva === "chat" ? "is-active" : ""}`}
          >
            <IconChat size={17} />
            <span className="rail-hide-collapsed">Instrutora Mara</span>
          </button>

          <button
            type="button"
            onClick={() => {
              onSelecionarAba("biblioteca");
              onFecharMobile();
            }}
            title="Biblioteca Oficial (Offline)"
            className={`rail-nav-btn ${abaAtiva === "biblioteca" ? "is-active" : ""}`}
          >
            <IconBook size={17} />
            <span className="rail-hide-collapsed">Biblioteca Oficial</span>
          </button>

          <button
            type="button"
            onClick={() => {
              onSelecionarAba("diretoria");
              onFecharMobile();
            }}
            title="Painel da Diretoria"
            className={`rail-nav-btn ${abaAtiva === "diretoria" ? "is-active" : ""}`}
          >
            <IconShield size={17} />
            <span className="rail-hide-collapsed">Diretoria</span>
          </button>

          {mostrarBotaoInstalar && (
            <button
              type="button"
              onClick={handleInstalarApp}
              aria-disabled={instalando ? "true" : undefined}
              title="Instalar aplicativo no celular ou computador"
              className="rail-nav-btn"
              style={{ color: "var(--p-action)" }}
            >
              <IconInstall size={17} />
              <span className="rail-hide-collapsed">
                {instalando ? "Instalando..." : "Instalar App"}
              </span>
            </button>
          )}
        </nav>

        <div className="rail-history rail-hide-collapsed">
          <div className="rail-section-label">Estudos recentes</div>
          {conversas.length === 0 ? (
            <p
              style={{
                margin: "4px 10px",
                fontSize: "0.79rem",
                color: "var(--p-muted)",
                lineHeight: 1.45,
              }}
            >
              Suas consultas e simulados ficam salvos neste dispositivo.
            </p>
          ) : (
            conversas.map((conv) => {
              const ehAtual = abaAtiva === "chat" && conversaAtivaId === conv.id;
              return (
                <div key={conv.id} className={`history-row ${ehAtual ? "is-current" : ""}`}>
                  <button
                    type="button"
                    onClick={() => {
                      onAbrirConversa(conv.id);
                      onFecharMobile();
                    }}
                    className="history-select-btn"
                  >
                    {conv.modo === "simulado" ? (
                      <IconQuiz size={14} />
                    ) : (
                      <IconChat size={14} />
                    )}
                    <span className="history-title-text">{conv.titulo}</span>
                  </button>
                  <button
                    type="button"
                    aria-label={`Excluir estudo ${conv.titulo}`}
                    onClick={() => onExcluirConversa(conv.id)}
                    className="history-delete-btn"
                  >
                    <IconTrash size={14} />
                  </button>
                </div>
              );
            })
          )}
        </div>

        <div className="rail-footer rail-hide-collapsed">
          <a
            href="https://infinitosoft.com"
            target="_blank"
            rel="noopener noreferrer"
            className="infinito-signature"
          >
            <img
              src={resolverUrlApi("/api/emblems/infinito")}
              alt=""
              width={20}
              height={20}
              style={{ objectFit: "contain" }}
            />
            <span>Infinito Soft · v2.0</span>
          </a>
        </div>
      </aside>
    </>
  );
}
