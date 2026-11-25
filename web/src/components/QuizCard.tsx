"use client";

import React, { useState } from "react";
import { IconDownload } from "./Icons";
import type { QuizEstruturado, TrechoRecuperado } from "@/lib/types";

interface QuizCardProps {
  quiz: QuizEstruturado;
  perguntaTema: string;
  markdownFallback: string;
  trechos: TrechoRecuperado[];
  categoria: string;
  onBaixarPdf: (params: {
    pergunta: string;
    resposta_md: string;
    trechos: TrechoRecuperado[];
    categoria: string;
    modo_quiz: boolean;
  }) => Promise<void>;
}

const LETRAS = ["A", "B", "C", "D", "E"];

const ROTULO_NIVEL: Record<string, string> = {
  aspirante: "Nível Aspirante",
  regular: "Classes Regulares",
  lideranca: "Liderança / Diretoria",
};

export function QuizCard({
  quiz,
  perguntaTema,
  markdownFallback,
  trechos,
  categoria,
  onBaixarPdf,
}: QuizCardProps) {
  const [respostas, setRespostas] = useState<Record<number, number>>({});
  const [baixandoPdf, setBaixandoPdf] = useState(false);

  const totalQuestoes = quiz.questoes.length;
  const respondidas = Object.keys(respostas).length;
  const acertos = quiz.questoes.reduce((acc, q, idx) => {
    return respostas[idx] === q.indice_correto ? acc + 1 : acc;
  }, 0);

  function selecionarAlternativa(questaoIdx: number, altIdx: number) {
    if (respostas[questaoIdx] !== undefined) return;
    setRespostas((prev) => ({ ...prev, [questaoIdx]: altIdx }));
  }

  function reiniciarSimulado() {
    setRespostas({});
  }

  async function handleExportarProva() {
    if (baixandoPdf) return;
    setBaixandoPdf(true);
    try {
      await onBaixarPdf({
        pergunta: perguntaTema || quiz.titulo,
        resposta_md: markdownFallback,
        trechos,
        categoria,
        modo_quiz: true,
      });
    } finally {
      setBaixandoPdf(false);
    }
  }

  return (
    <section className="quiz-card" aria-label={quiz.titulo || "Simulado Interativo"}>
      <header className="quiz-card-header">
        <div>
          <span className="eyebrow-mono">
            Simulado Interativo · {ROTULO_NIVEL[quiz.nivel] || quiz.nivel}
          </span>
          <h3 style={{ marginTop: 4, fontSize: "1.08rem" }}>{quiz.titulo}</h3>
        </div>
        <div className="quiz-score-pill" role="status" aria-live="polite">
          Acertos: {acertos} / {totalQuestoes}
          {respondidas === totalQuestoes && totalQuestoes > 0
            ? ` (${Math.round((acertos / totalQuestoes) * 100)}%)`
            : ""}
        </div>
      </header>

      <div className="quiz-questions-list">
        {quiz.questoes.map((questao, qIdx) => {
          const escolhida = respostas[qIdx];
          const jaRespondeu = escolhida !== undefined;

          return (
            <div key={qIdx} className="quiz-question-block">
              <div className="quiz-enunciado">
                <span style={{ fontFamily: "var(--font-mono)", color: "var(--p-action)", marginRight: 6 }}>
                  {String(qIdx + 1).padStart(2, "0")}.
                </span>
                {questao.enunciado}
              </div>

              <div className="quiz-options-grid" role="group" aria-label={`Questão ${qIdx + 1}`}>
                {questao.alternativas.map((altTexto, aIdx) => {
                  const letra = LETRAS[aIdx] || String(aIdx + 1);
                  const textoSemPrefixo = altTexto.replace(/^[A-Da-d][\)\.\-]\s*/, "");
                  const ehCorreta = aIdx === questao.indice_correto;
                  const foiClicada = escolhida === aIdx;

                  let estadoClasse = "";
                  if (jaRespondeu) {
                    if (ehCorreta) estadoClasse = "is-correct";
                    else if (foiClicada) estadoClasse = "is-wrong";
                  }

                  return (
                    <button
                      key={aIdx}
                      type="button"
                      disabled={jaRespondeu}
                      onClick={() => selecionarAlternativa(qIdx, aIdx)}
                      className={`quiz-option-btn ${estadoClasse}`}
                    >
                      <span className="quiz-option-letter">{letra}</span>
                      <span>{textoSemPrefixo}</span>
                    </button>
                  );
                })}
              </div>

              {jaRespondeu && (
                <div className="quiz-explanation">
                  <strong style={{ color: escolhida === questao.indice_correto ? "var(--p-ok)" : "var(--p-danger)" }}>
                    {escolhida === questao.indice_correto ? "Resposta correta. " : "Atenção ao regulamento. "}
                  </strong>
                  {questao.explicacao}
                  {questao.fonte && (
                    <div
                      style={{
                        marginTop: 6,
                        fontFamily: "var(--font-mono)",
                        fontSize: "0.73rem",
                        color: "var(--p-muted)",
                      }}
                    >
                      Referência oficial: {questao.fonte}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <footer className="quiz-card-footer">
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          {respondidas > 0 && (
            <button type="button" onClick={reiniciarSimulado} className="btn-base">
              Refazer no celular
            </button>
          )}
        </div>

        <button
          type="button"
          onClick={handleExportarProva}
          aria-disabled={baixandoPdf ? "true" : undefined}
          className="btn-base btn-primary"
        >
          <IconDownload size={15} />
          <span>{baixandoPdf ? "Gerando prova..." : "Baixar Prova + Gabarito (PDF)"}</span>
        </button>
      </footer>
    </section>
  );
}
