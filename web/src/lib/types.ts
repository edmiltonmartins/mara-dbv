// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Edmilton Cabral Martins Junior <junior.edmilton@gmail.com>

export interface CategoriaItem {
  id: string;
  rotulo: string;
}

export interface SugestaoInicial {
  id: string;
  titulo: string;
  categoria: string;
  modo: "consulta" | "simulado";
  pergunta: string;
}

export interface HealthMetadata {
  status: string;
  versao: string;
  device_id: string;
  nome_clube: string;
  chat_ativo: boolean;
  mensagem_manutencao: string;
  exibir_detalhes_tecnicos: boolean;
  api_configurada: boolean;
  total_manuais: number;
  total_chunks: number;
  total_guias_biblioteca: number;
  categorias: CategoriaItem[];
  sugestoes_iniciais: SugestaoInicial[];
}

export interface TrechoRecuperado {
  chunk_id: number;
  manual_titulo: string;
  arquivo: string;
  categoria: string;
  pagina: number;
  texto: string;
  similaridade: number;
  score_rrf: number;
}

export interface QuestaoQuiz {
  enunciado: string;
  alternativas: string[];
  indice_correto: number;
  explicacao: string;
  fonte: string;
}

export interface QuizEstruturado {
  titulo: string;
  nivel: "aspirante" | "regular" | "lideranca" | string;
  questoes: QuestaoQuiz[];
}

export interface MensagemChat {
  id: string;
  role: "user" | "assistant";
  content: string;
  pergunta?: string;
  trechos?: TrechoRecuperado[];
  quiz?: QuizEstruturado | null;
  streaming?: boolean;
  etapaStatus?: string;
  feedbackEnviado?: "up" | "down" | null;
}

export interface ConversaResumo {
  id: string;
  titulo: string;
  modo: string;
  categoria: string;
  atualizado_em: string;
}

export interface ConversaDetalhe {
  resumo: ConversaResumo;
  mensagens: Array<{
    role: "user" | "assistant";
    content: string;
    pergunta: string;
    trechos: TrechoRecuperado[];
    quiz?: QuizEstruturado | null;
  }>;
}

export interface GuiaBiblioteca {
  id: string;
  titulo: string;
  subtitulo: string;
  categoria: string;
  categoria_rotulo: string;
  badge: string;
  emblema_url: string;
  resumo_markdown: string;
  pergunta_consulta: string;
  tema_simulado: string;
  pdf_url: string;
}

export interface ManualIndexado {
  id: number;
  titulo: string;
  arquivo: string;
  categoria: string;
  categoria_rotulo?: string;
  paginas: number;
  total_chunks: number;
}

export interface BibliotecaPayload {
  guias: GuiaBiblioteca[];
  manuais: ManualIndexado[];
}

export interface AdminDashboardPayload {
  backend: string;
  metricas: {
    manuais: number;
    trechos: number;
    avaliacoes: number;
    taxa_aprovacao: string;
  };
  config: {
    nome_clube: string;
    modelo_chat: string;
    modelos_disponiveis: string[];
    top_k: number;
    database_url: string;
    exibir_detalhes_tecnicos: boolean;
    chat_ativo: boolean;
    mensagem_manutencao: string;
    api_key_configurada: boolean;
    categorias_validas: CategoriaItem[];
  };
  manuais: ManualIndexado[];
  feedbacks: Array<{
    id: number;
    pergunta: string;
    resposta: string;
    positivo: boolean;
    criado_em: string;
  }>;
}
