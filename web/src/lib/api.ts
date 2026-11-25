import {
  lerCacheBiblioteca,
  lerCacheConversaDetalhe,
  lerCacheHealth,
  lerCacheListaConversas,
  obterOuCriarDeviceId,
  removerCacheConversaDetalhe,
  salvarCacheBiblioteca,
  salvarCacheConversaDetalhe,
  salvarCacheHealth,
  salvarCacheListaConversas,
} from "./offlineStore";
import type {
  AdminDashboardPayload,
  BibliotecaPayload,
  ConversaDetalhe,
  ConversaResumo,
  HealthMetadata,
  QuizEstruturado,
  TrechoRecuperado,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "";

export function resolverUrlApi(caminho: string): string {
  if (caminho.startsWith("http://") || caminho.startsWith("https://")) {
    return caminho;
  }
  return `${API_BASE}${caminho}`;
}

function cabecalhosPadrao(extra?: Record<string, string>): Record<string, string> {
  return {
    "X-Device-Id": obterOuCriarDeviceId(),
    ...(extra || {}),
  };
}

async function extrairErroHttp(resp: Response): Promise<string> {
  try {
    const dados = await resp.json();
    if (typeof dados?.detail === "string") return dados.detail;
  } catch {
    // ignora
  }
  return `Falha na comunicação (${resp.status}).`;
}

export async function buscarHealth(): Promise<HealthMetadata> {
  try {
    const resp = await fetch(resolverUrlApi("/api/health"), {
      credentials: "include",
      headers: cabecalhosPadrao(),
    });
    if (!resp.ok) throw new Error(await extrairErroHttp(resp));
    const dados = (await resp.json()) as HealthMetadata;
    salvarCacheHealth(dados);
    return dados;
  } catch (err) {
    const cache = lerCacheHealth();
    if (cache) return cache;
    throw err;
  }
}

export async function buscarBiblioteca(): Promise<{
  dados: BibliotecaPayload;
  offlineFallback: boolean;
}> {
  try {
    const resp = await fetch(resolverUrlApi("/api/library"), {
      credentials: "include",
      headers: cabecalhosPadrao(),
    });
    if (!resp.ok) throw new Error(await extrairErroHttp(resp));
    const dados = (await resp.json()) as BibliotecaPayload;
    salvarCacheBiblioteca(dados);
    return { dados, offlineFallback: false };
  } catch (err) {
    const cache = lerCacheBiblioteca();
    if (cache) {
      return { dados: cache, offlineFallback: true };
    }
    throw err;
  }
}

export async function listarConversas(): Promise<ConversaResumo[]> {
  try {
    const resp = await fetch(resolverUrlApi("/api/conversations"), {
      credentials: "include",
      headers: cabecalhosPadrao(),
    });
    if (!resp.ok) throw new Error(await extrairErroHttp(resp));
    const lista = (await resp.json()) as ConversaResumo[];
    salvarCacheListaConversas(lista);
    return lista;
  } catch {
    return lerCacheListaConversas();
  }
}

export async function carregarConversa(conversaId: string): Promise<ConversaDetalhe> {
  try {
    const resp = await fetch(resolverUrlApi(`/api/conversations/${encodeURIComponent(conversaId)}`), {
      credentials: "include",
      headers: cabecalhosPadrao(),
    });
    if (!resp.ok) throw new Error(await extrairErroHttp(resp));
    const det = (await resp.json()) as ConversaDetalhe;
    salvarCacheConversaDetalhe(conversaId, det);
    return det;
  } catch (err) {
    const cache = lerCacheConversaDetalhe(conversaId);
    if (cache) return cache;
    throw err;
  }
}

export async function excluirConversa(conversaId: string): Promise<void> {
  removerCacheConversaDetalhe(conversaId);
  await fetch(resolverUrlApi(`/api/conversations/${encodeURIComponent(conversaId)}`), {
    method: "DELETE",
    credentials: "include",
    headers: cabecalhosPadrao(),
  });
}

export interface StreamCallbacks {
  onStatus?: (etapa: string) => void;
  onToken?: (delta: string) => void;
  onReset?: () => void;
  onSources?: (trechos: TrechoRecuperado[]) => void;
  onDone?: (payload: {
    conversa_id: string;
    titulo: string;
    content: string;
    trechos: TrechoRecuperado[];
    exibir_fontes: boolean;
  }) => void;
  onError?: (detalhe: string) => void;
}

export async function enviarPerguntaStream(
  params: {
    pergunta: string;
    conversa_id?: string | null;
    categoria: string;
    modo_quiz: boolean;
  },
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch(resolverUrlApi("/api/chat/stream"), {
    method: "POST",
    credentials: "include",
    headers: cabecalhosPadrao({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      pergunta: params.pergunta,
      conversa_id: params.conversa_id || null,
      categoria: params.categoria,
      modo_quiz: params.modo_quiz,
    }),
    signal,
  });

  if (!resp.ok || !resp.body) {
    throw new Error(await extrairErroHttp(resp));
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let separadorIdx = buffer.indexOf("\n\n");
    while (separadorIdx !== -1) {
      const bloco = buffer.slice(0, separadorIdx);
      buffer = buffer.slice(separadorIdx + 2);

      let evento = "message";
      const linhasData: string[] = [];
      for (const linha of bloco.split(/\r?\n/)) {
        if (linha.startsWith("event:")) {
          evento = linha.slice(6).trim();
        } else if (linha.startsWith("data:")) {
          linhasData.push(linha.slice(5).trim());
        }
      }

      if (linhasData.length > 0) {
        try {
          const parsed = JSON.parse(linhasData.join("\n"));
          if (evento === "status" && parsed.etapa) {
            callbacks.onStatus?.(parsed.etapa);
          } else if (evento === "reset") {
            callbacks.onReset?.();
          } else if (evento === "token" && typeof parsed.delta === "string") {
            callbacks.onToken?.(parsed.delta);
          } else if (evento === "sources" && Array.isArray(parsed.trechos)) {
            callbacks.onSources?.(parsed.trechos);
          } else if (evento === "done") {
            callbacks.onDone?.(parsed);
          } else if (evento === "error") {
            callbacks.onError?.(parsed.detail || "Erro ao processar resposta.");
          }
        } catch {
          // ignora fragmento malformado
        }
      }
      separadorIdx = buffer.indexOf("\n\n");
    }
  }
}

export async function gerarSimuladoInterativo(params: {
  tema: string;
  conversa_id?: string | null;
  categoria: string;
  quantidade: number;
  nivel: "aspirante" | "regular" | "lideranca";
}): Promise<{
  conversa_id: string;
  titulo_conversa: string;
  quiz: QuizEstruturado;
  markdown: string;
  trechos: TrechoRecuperado[];
}> {
  const resp = await fetch(resolverUrlApi("/api/quiz/generate"), {
    method: "POST",
    credentials: "include",
    headers: cabecalhosPadrao({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      tema: params.tema,
      conversa_id: params.conversa_id || null,
      categoria: params.categoria,
      quantidade: params.quantidade,
      nivel: params.nivel,
    }),
  });
  if (!resp.ok) throw new Error(await extrairErroHttp(resp));
  return resp.json();
}

export async function baixarPdfResposta(params: {
  pergunta: string;
  resposta_md: string;
  trechos: TrechoRecuperado[];
  categoria: string;
  modo_quiz: boolean;
}): Promise<void> {
  const resp = await fetch(resolverUrlApi("/api/pdf/resposta"), {
    method: "POST",
    credentials: "include",
    headers: cabecalhosPadrao({ "Content-Type": "application/json" }),
    body: JSON.stringify(params),
  });
  if (!resp.ok) throw new Error(await extrairErroHttp(resp));
  const blob = await resp.blob();
  dispararDownloadBlob(blob, params.modo_quiz ? "simulado_mara.pdf" : "estudo_mara.pdf");
}

export async function baixarPdfConversa(conversaId: string): Promise<void> {
  const resp = await fetch(resolverUrlApi(`/api/pdf/conversa/${encodeURIComponent(conversaId)}`), {
    credentials: "include",
    headers: cabecalhosPadrao(),
  });
  if (!resp.ok) throw new Error(await extrairErroHttp(resp));
  const blob = await resp.blob();
  dispararDownloadBlob(blob, `caderno_${conversaId}.pdf`);
}

function dispararDownloadBlob(blob: Blob, nomeArquivo: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nomeArquivo;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export async function enviarFeedback(params: {
  pergunta: string;
  resposta: string;
  positivo: boolean;
}): Promise<void> {
  await fetch(resolverUrlApi("/api/feedback"), {
    method: "POST",
    credentials: "include",
    headers: cabecalhosPadrao({ "Content-Type": "application/json" }),
    body: JSON.stringify(params),
  });
}

// ==================== ADMINISTRAÇÃO ====================

export async function verificarSessaoAdmin(): Promise<boolean> {
  const resp = await fetch(resolverUrlApi("/api/admin/session"), {
    credentials: "include",
    headers: cabecalhosPadrao(),
  });
  if (!resp.ok) return false;
  const dados = await resp.json();
  return Boolean(dados?.autenticado);
}

export async function loginAdmin(senha: string): Promise<void> {
  const resp = await fetch(resolverUrlApi("/api/admin/login"), {
    method: "POST",
    credentials: "include",
    headers: cabecalhosPadrao({ "Content-Type": "application/json" }),
    body: JSON.stringify({ senha }),
  });
  if (!resp.ok) throw new Error(await extrairErroHttp(resp));
}

export async function logoutAdmin(): Promise<void> {
  await fetch(resolverUrlApi("/api/admin/logout"), {
    method: "POST",
    credentials: "include",
    headers: cabecalhosPadrao(),
  });
}

export async function buscarDashboardAdmin(): Promise<AdminDashboardPayload> {
  const resp = await fetch(resolverUrlApi("/api/admin/dashboard"), {
    credentials: "include",
    headers: cabecalhosPadrao(),
  });
  if (!resp.ok) throw new Error(await extrairErroHttp(resp));
  return resp.json();
}

export async function salvarConfigAdmin(payload: Record<string, unknown>): Promise<void> {
  const resp = await fetch(resolverUrlApi("/api/admin/config"), {
    method: "PUT",
    credentials: "include",
    headers: cabecalhosPadrao({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  if (!resp.ok) throw new Error(await extrairErroHttp(resp));
}

export async function alterarSenhaAdmin(nova_senha: string): Promise<void> {
  const resp = await fetch(resolverUrlApi("/api/admin/password"), {
    method: "PUT",
    credentials: "include",
    headers: cabecalhosPadrao({ "Content-Type": "application/json" }),
    body: JSON.stringify({ nova_senha }),
  });
  if (!resp.ok) throw new Error(await extrairErroHttp(resp));
}

export async function uploadManuaisAdmin(params: {
  categoria: string;
  forcar: boolean;
  arquivos: File[];
}): Promise<Array<{ arquivo: string; paginas: number; chunks: number; ignorado_por_cache: boolean }>> {
  const fd = new FormData();
  fd.append("categoria", params.categoria);
  fd.append("forcar", String(params.forcar));
  for (const arq of params.arquivos) {
    fd.append("arquivos", arq);
  }
  const resp = await fetch(resolverUrlApi("/api/admin/manuals/upload"), {
    method: "POST",
    credentials: "include",
    headers: cabecalhosPadrao(),
    body: fd,
  });
  if (!resp.ok) throw new Error(await extrairErroHttp(resp));
  const dados = await resp.json();
  return dados.resultados || [];
}

export async function removerManualAdmin(id: number): Promise<void> {
  const resp = await fetch(resolverUrlApi(`/api/admin/manuals/${id}`), {
    method: "DELETE",
    credentials: "include",
    headers: cabecalhosPadrao(),
  });
  if (!resp.ok) throw new Error(await extrairErroHttp(resp));
}

export async function removerFeedbackAdmin(id: number): Promise<void> {
  const resp = await fetch(resolverUrlApi(`/api/admin/feedback/${id}`), {
    method: "DELETE",
    credentials: "include",
    headers: cabecalhosPadrao(),
  });
  if (!resp.ok) throw new Error(await extrairErroHttp(resp));
}
