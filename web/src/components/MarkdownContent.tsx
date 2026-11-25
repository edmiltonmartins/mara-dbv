"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownContentProps {
  content: string;
}

/**
 * Normaliza blocos HTML legados (<details>/<summary>) vindos de conversas antigas
 * para Markdown limpo, preservando tabelas GFM com wrapper acessível.
 */
function normalizarMarkdownLegado(texto: string): string {
  if (!texto) return "";
  return texto
    .replace(/<details[^>]*>\s*<summary[^>]*>(.*?)<\/summary>/gi, "\n\n### $1\n\n")
    .replace(/<\/details>/gi, "\n")
    .replace(/<br\s*\/?>/gi, "\n");
}

export function MarkdownContent({ content }: MarkdownContentProps) {
  const limpo = normalizarMarkdownLegado(content);

  return (
    <div className="mara-prose">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          table: ({ children }) => (
            <div
              tabIndex={0}
              role="region"
              aria-label="Tabela oficial do manual DSA"
              className="table-wrapper"
            >
              <table>{children}</table>
            </div>
          ),
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {limpo}
      </ReactMarkdown>
    </div>
  );
}
