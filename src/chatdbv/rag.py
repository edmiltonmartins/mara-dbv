"""Orquestrador RAG do Chat DBV compatível tanto com Gemini Developer API (AIza...)
quanto com Google Cloud Vertex AI Express Mode (chaves AQ...)."""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from google import genai
from google.genai import types

from .config import Config, criar_cliente_genai
from .db import RepositorioRAG, TrechoRecuperado
from .embeddings import Embedder

INSTRUCAO_SISTEMA_DBV = """Você é a **Mara** (nome inspirado na saudação *Maranata*), a instrutora e assistente de Inteligência Artificial oficial de apoio ao Clube de Desbravadores na Divisão Sul-Americana (DSA / Brasil).
Seu objetivo é responder dúvidas de desbravadores, conselheiros, instrutores e diretores com base ESTRITA nos manuais e documentos oficiais fornecidos no bloco CONTEXTO DOS MANUAIS.

Regras Obrigatórias:
1. Identidade, Saudação e Tom: Você é uma figura feminina (instrutora/líder especialista). Seja cortês, didática, encorajadora e use linguagem própria do universo dos Desbravadores (como "Maranata!" quando apropriado).
2. Fidelidade Absoluta às Fontes (Zero Alucinação):
   - Responda APENAS com informações sustentadas pelo CONTEXTO DOS MANUAIS abaixo.
   - Se a resposta não estiver nos trechos recuperados, diga claramente: "Não encontrei essa regra ou informação específica nos manuais indexados até o momento." Não invente medidas, cores, idades ou requisitos.
3. Citação Obrigatória:
   - Ao afirmar qualquer regra, requisito, medida ou fato histórico, cite a fonte entre colchetes no formato: `[Nome do Manual, pág. X]`.
4. Organização Visual:
   - Use listas com marcadores, tabelas ou passos numerados para facilitar a leitura rápida por líderes e desbravadores.
"""

INSTRUCAO_SISTEMA_SIMPLES_DBV = """Você é a **Mara** (nome inspirado na saudação *Maranata*), a instrutora e amiga de Inteligência Artificial do Clube de Desbravadores na Divisão Sul-Americana (DSA / Brasil).
Seu objetivo é responder dúvidas de desbravadores (especialmente crianças e adolescentes de 10 a 15 anos) e líderes com base ESTRITA nos manuais oficiais fornecidos no bloco CONTEXTO DOS MANUAIS.

Regras Obrigatórias:
1. Identidade e Linguagem Acessível: Você é uma instrutora feminina acolhedora, animada e muito didática. Use frases claras, diretas e fáceis de entender por crianças e juvenis, iniciando com "Maranata!" quando apropriado.
2. Fidelidade Absoluta às Fontes (Zero Alucinação):
   - Responda APENAS com informações sustentadas pelo CONTEXTO DOS MANUAIS abaixo.
   - Se a resposta não estiver nos trechos recuperados, diga de forma gentil que ainda não tem essa informação nos manuais cadastrados.
3. Visual Limpo (Sem Colchetes Técnicos):
   - NÃO coloque citações técnicas entre colchetes como `[Manual, pág. X]` no meio do texto para não poluir a leitura das crianças.
   - Use tópicos curtos, destaques em negrito e explicações diretas.
"""

INSTRUCAO_QUIZ_DBV = """Você é a **Mara**, Instrutora de Investidura do Clube de Desbravadores (Divisão Sul-Americana).
Com base EXCLUSIVAMENTE nos trechos de manuais fornecidos no bloco CONTEXTO DOS MANUAIS:
1. Elabore um simulado / quiz de estudo com 3 perguntas objetivas ou práticas sobre o tema solicitado.
2. Após as perguntas, apresente um bloco "**Gabarito Comentado da Mara**" explicando a resposta correta e citando `[Nome do Manual, pág. X]`.
"""

INSTRUCAO_QUIZ_SIMPLES_DBV = """Você é a **Mara**, Instrutora de Investidura do Clube de Desbravadores (Divisão Sul-Americana).
Com base EXCLUSIVAMENTE nos trechos de manuais fornecidos no bloco CONTEXTO DOS MANUAIS:
1. Elabore um simulado divertido e educativo com 3 perguntas fáceis de entender sobre o tema solicitado.
2. Após as perguntas, apresente um bloco "**Gabarito da Mara**" explicando de forma simples a resposta correta (sem citações técnicas entre colchetes).
"""

# Ordem de modelos atuais tentados em sequência caso algum não esteja habilitado na chave
MODELOS_CANDIDATOS = (
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
)


@dataclass(frozen=True)
class RespostaRAG:
    texto: str
    trechos: list[TrechoRecuperado]
    interaction_id: str | None = None


def montar_bloco_contexto(trechos: list[TrechoRecuperado]) -> str:
    if not trechos:
        return "NENHUM TRECHO ENCONTRADO NOS MANUAIS INDEXADOS."
    blocos: list[str] = []
    for i, t in enumerate(trechos, start=1):
        blocos.append(
            f"--- FONTE {i}: [{t.manual_titulo}, pág. {t.pagina}] "
            f"(Categoria: {t.categoria} | Similaridade: {t.similaridade:.2f}) ---\n"
            f"{t.texto}"
        )
    return "\n\n".join(blocos)


def montar_prompt_usuario(
    pergunta: str,
    trechos: list[TrechoRecuperado],
    modo_quiz: bool = False,
    exibir_detalhes_tecnicos: bool = True,
) -> str:
    contexto = montar_bloco_contexto(trechos)
    tarefa = (
        f"Tema solicitado para o Simulado/Quiz de Investidura: {pergunta}"
        if modo_quiz
        else f"Pergunta do Desbravador/Líder: {pergunta}"
    )
    lembrete = (
        "Lembre-se de citar as fontes no formato [Manual, pág. X]."
        if exibir_detalhes_tecnicos
        else "Responda de forma simples, direta e amigável, sem colchetes técnicos de página."
    )
    return (
        f"CONTEXTO DOS MANUAIS OFICIAIS (DSA):\n\n{contexto}\n\n"
        f"========================================\n"
        f"{tarefa}\n\n"
        f"{lembrete}"
    )


def _selecionar_instrucao(modo_quiz: bool, exibir_detalhes_tecnicos: bool) -> str:
    if modo_quiz:
        return INSTRUCAO_QUIZ_DBV if exibir_detalhes_tecnicos else INSTRUCAO_QUIZ_SIMPLES_DBV
    return INSTRUCAO_SISTEMA_DBV if exibir_detalhes_tecnicos else INSTRUCAO_SISTEMA_SIMPLES_DBV


def _lista_modelos(modelo_preferido: str) -> list[str]:
    modelos = [modelo_preferido]
    for m in MODELOS_CANDIDATOS:
        if m not in modelos:
            modelos.append(m)
    return modelos


def _eh_chave_aq(api_key: str) -> bool:
    return (api_key or "").strip().upper().startswith("AQ.")


def _nivel_thinking_rapido(modelo: str) -> str:
    """Define o menor nível de thinking suportado pelo modelo na Interactions API."""
    m = (modelo or "").lower()
    if "flash-lite" in m or "3.6-flash" in m:
        return "minimal"
    return "low"


def _nivel_thinking_enum(modelo: str) -> types.ThinkingLevel:
    """Define o ThinkingLevel compatível com GenerateContentConfig nos modelos Gemini 3."""
    m = (modelo or "").lower()
    if "flash-lite" in m or "3.6-flash" in m:
        return types.ThinkingLevel.MINIMAL
    return types.ThinkingLevel.LOW


class MotorRAG:
    def __init__(
        self,
        cfg: Config,
        repo: RepositorioRAG,
        embedder: Embedder | None = None,
        client: genai.Client | None = None,
    ) -> None:
        self.cfg = cfg
        self.repo = repo
        self.embedder = embedder or Embedder(cfg)
        self.client = client or criar_cliente_genai(cfg)
        self.ultimo_interaction_id: str | None = None

    def recuperar(
        self,
        pergunta: str,
        categoria: str | None = None,
        top_k: int | None = None,
    ) -> list[TrechoRecuperado]:
        vetor = self.embedder.consulta(pergunta)
        return self.repo.buscar_hibrido(
            vetor_consulta=vetor,
            texto_consulta=pergunta,
            top_k=top_k or self.cfg.top_k,
            categoria=categoria,
        )

    def responder(
        self,
        pergunta: str,
        categoria: str | None = None,
        modo_quiz: bool = False,
        previous_interaction_id: str | None = None,
        trechos_pre_recuperados: list[TrechoRecuperado] | None = None,
    ) -> RespostaRAG:
        trechos = (
            trechos_pre_recuperados
            if trechos_pre_recuperados is not None
            else self.recuperar(pergunta, categoria=categoria)
        )
        prompt = montar_prompt_usuario(
            pergunta,
            trechos,
            modo_quiz=modo_quiz,
            exibir_detalhes_tecnicos=self.cfg.exibir_detalhes_tecnicos,
        )
        instrucao = _selecionar_instrucao(modo_quiz, self.cfg.exibir_detalhes_tecnicos)
        nivel_thinking = _nivel_thinking_rapido(self.cfg.modelo_chat)

        # 1. Em chaves AI Studio padrão (AIza...), usa Interactions API com thinking_level baixo
        if not self.cfg.usa_vertex_express and not _eh_chave_aq(self.cfg.gemini_api_key):
            try:
                kwargs: dict = {
                    "model": self.cfg.modelo_chat,
                    "system_instruction": instrucao,
                    "input": prompt,
                    "generation_config": {"thinking_level": nivel_thinking},
                }
                if previous_interaction_id:
                    kwargs["previous_interaction_id"] = previous_interaction_id
                interaction = self.client.interactions.create(**kwargs)
                inter_id = getattr(interaction, "id", None)
                self.ultimo_interaction_id = inter_id
                return RespostaRAG(
                    texto=interaction.output_text or "",
                    trechos=trechos,
                    interaction_id=inter_id,
                )
            except Exception:
                pass

        # 2. Chaves AQ... e fallback direto via generate_content (compatível com Gemini 3.8 Flash)
        ultimo_erro: Exception | None = None
        for mod in _lista_modelos(self.cfg.modelo_chat):
            configs_tentativa = [
                types.GenerateContentConfig(
                    system_instruction=instrucao,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=_nivel_thinking_enum(mod),
                    ),
                ),
                types.GenerateContentConfig(system_instruction=instrucao),
            ]
            for cfg_gen in configs_tentativa:
                try:
                    resp = self.client.models.generate_content(
                        model=mod,
                        contents=prompt,
                        config=cfg_gen,
                    )
                    if resp and getattr(resp, "text", None):
                        return RespostaRAG(
                            texto=resp.text,
                            trechos=trechos,
                            interaction_id=None,
                        )
                except Exception as exc:
                    ultimo_erro = exc
                    continue
        raise RuntimeError(f"Falha ao gerar resposta na API: {ultimo_erro}")

    def responder_stream(
        self,
        pergunta: str,
        trechos: list[TrechoRecuperado],
        modo_quiz: bool = False,
        previous_interaction_id: str | None = None,
    ) -> Iterator[str]:
        """Gera tokens em tempo real com baixa latência tanto em chaves AIza... quanto AQ..."""
        prompt = montar_prompt_usuario(
            pergunta,
            trechos,
            modo_quiz=modo_quiz,
            exibir_detalhes_tecnicos=self.cfg.exibir_detalhes_tecnicos,
        )
        instrucao = _selecionar_instrucao(modo_quiz, self.cfg.exibir_detalhes_tecnicos)
        nivel_thinking = _nivel_thinking_rapido(self.cfg.modelo_chat)

        if not self.cfg.usa_vertex_express and not _eh_chave_aq(self.cfg.gemini_api_key):
            try:
                kwargs: dict = {
                    "model": self.cfg.modelo_chat,
                    "system_instruction": instrucao,
                    "input": prompt,
                    "generation_config": {"thinking_level": nivel_thinking},
                    "stream": True,
                }
                if previous_interaction_id:
                    kwargs["previous_interaction_id"] = previous_interaction_id

                stream = self.client.interactions.create(**kwargs)
                emitiu_texto = False
                for event in stream:
                    ev_type = getattr(event, "event_type", None)
                    if ev_type in ("interaction.created", "interaction.completed"):
                        inter_obj = getattr(event, "interaction", None)
                        if inter_obj and getattr(inter_obj, "id", None):
                            self.ultimo_interaction_id = inter_obj.id
                    elif ev_type == "step.delta":
                        delta = getattr(event, "delta", None)
                        if delta and getattr(delta, "type", None) == "text":
                            txt = getattr(delta, "text", "")
                            if txt:
                                emitiu_texto = True
                                yield txt
                if emitiu_texto:
                    return
            except Exception:
                pass

        # Chaves AQ... (e fallback geral): vai direto para generate_content_stream sem atraso
        ultimo_erro: Exception | None = None
        for mod in _lista_modelos(self.cfg.modelo_chat):
            configs_tentativa = [
                types.GenerateContentConfig(
                    system_instruction=instrucao,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=_nivel_thinking_enum(mod),
                    ),
                ),
                types.GenerateContentConfig(system_instruction=instrucao),
            ]
            for cfg_gen in configs_tentativa:
                emitiu = False
                try:
                    stream = self.client.models.generate_content_stream(
                        model=mod,
                        contents=prompt,
                        config=cfg_gen,
                    )
                    for chunk in stream:
                        txt = getattr(chunk, "text", None)
                        if txt:
                            emitiu = True
                            yield txt
                    if emitiu:
                        return
                except Exception as exc:
                    ultimo_erro = exc
                    if emitiu:
                        return
                    continue
        if ultimo_erro:
            raise ultimo_erro
