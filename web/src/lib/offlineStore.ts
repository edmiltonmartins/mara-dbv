import type { BibliotecaPayload, ConversaDetalhe, ConversaResumo, HealthMetadata } from "./types";

const KEY_DEVICE_ID = "mara_v2_device_id";
const KEY_HEALTH_CACHE = "mara_v2_health_cache";
const KEY_LIBRARY_CACHE = "mara_v2_library_cache";
const KEY_CONVERSATIONS_LIST = "mara_v2_convs_cache";
const PREFIX_CONVERSATION = "mara_v2_conv_detail_";

export function obterOuCriarDeviceId(): string {
  if (typeof window === "undefined") return "server";
  try {
    const existente = window.localStorage.getItem(KEY_DEVICE_ID);
    if (existente && existente.length >= 8) {
      return existente;
    }
    const novo =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID().replace(/-/g, "").slice(0, 24)
        : `dev${Math.random().toString(36).slice(2, 14)}${Date.now().toString(36)}`;
    window.localStorage.setItem(KEY_DEVICE_ID, novo);
    return novo;
  } catch {
    return "anon_local_device";
  }
}

export function salvarCacheHealth(dados: HealthMetadata): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY_HEALTH_CACHE, JSON.stringify(dados));
  } catch {
    // Ignora cota excedida
  }
}

export function lerCacheHealth(): HealthMetadata | null {
  if (typeof window === "undefined") return null;
  try {
    const bruto = window.localStorage.getItem(KEY_HEALTH_CACHE);
    return bruto ? (JSON.parse(bruto) as HealthMetadata) : null;
  } catch {
    return null;
  }
}

export function salvarCacheBiblioteca(dados: BibliotecaPayload): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY_LIBRARY_CACHE, JSON.stringify(dados));
  } catch {
    // Ignora cota excedida
  }
}

export function lerCacheBiblioteca(): BibliotecaPayload | null {
  if (typeof window === "undefined") return null;
  try {
    const bruto = window.localStorage.getItem(KEY_LIBRARY_CACHE);
    return bruto ? (JSON.parse(bruto) as BibliotecaPayload) : null;
  } catch {
    return null;
  }
}

export function salvarCacheListaConversas(lista: ConversaResumo[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY_CONVERSATIONS_LIST, JSON.stringify(lista.slice(0, 30)));
  } catch {
    // Ignora
  }
}

export function lerCacheListaConversas(): ConversaResumo[] {
  if (typeof window === "undefined") return [];
  try {
    const bruto = window.localStorage.getItem(KEY_CONVERSATIONS_LIST);
    return bruto ? (JSON.parse(bruto) as ConversaResumo[]) : [];
  } catch {
    return [];
  }
}

export function salvarCacheConversaDetalhe(id: string, detalhe: ConversaDetalhe): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(`${PREFIX_CONVERSATION}${id}`, JSON.stringify(detalhe));
  } catch {
    // Ignora
  }
}

export function lerCacheConversaDetalhe(id: string): ConversaDetalhe | null {
  if (typeof window === "undefined") return null;
  try {
    const bruto = window.localStorage.getItem(`${PREFIX_CONVERSATION}${id}`);
    return bruto ? (JSON.parse(bruto) as ConversaDetalhe) : null;
  } catch {
    return null;
  }
}

export function removerCacheConversaDetalhe(id: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(`${PREFIX_CONVERSATION}${id}`);
  } catch {
    // Ignora
  }
}
