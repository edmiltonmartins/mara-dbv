# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Edmilton Cabral Martins Junior <junior.edmilton@gmail.com>

"""Exportação editorial de consultas, simulados (provas), conversas e guias da Biblioteca em PDF.

Segue princípios de design editorial limpo (92% neutro, hierarquia tipográfica clara,
fios hairline de 0.22mm, tabelas multilinhas proporcionais sem truncamento, círculos de
marcação em alternativas de múltipla escolha e folha de gabarito separada para o instrutor).
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Sequence

from fpdf import FPDF, FontFace

from .config import RAIZ
from .db import TrechoRecuperado
from .ingestao import ROTULOS_CATEGORIAS

# Paleta Editorial (Alinhada ao Design System Infinito Soft + Identidade Oficial DSA)
COR_MARINHO_INFINITO = (1, 4, 64)       # #010440 — Títulos e autoridade
COR_TINTA_CORPO = (30, 41, 59)          # #1E293B — Texto corrido de alta legibilidade
COR_TINTA_MUTED = (100, 116, 139)       # #64748B — Metadados, legendas e cabeçalhos
COR_ACENTO_ACAO = (13, 106, 138)        # #0D6A8A — Acento técnico Infinito/Mara
COR_VERMELHO_DSA = (185, 28, 28)        # #B91C1C — Faixa institucional Desbravadores
COR_OURO_DSA = (217, 119, 6)            # #D97706 — Filete ouro Desbravadores
COR_SUPERFICIE = (246, 248, 251)        # #F6F8FB — Superfície suave (1 passo do branco)
COR_SUPERFICIE_TABELA = (238, 242, 246) # #EEF2F6 — Cabeçalho de tabela
COR_SUPERFICIE_PROVA = (252, 250, 242)  # #FCFAF2 — Cabeçalho sutil de avaliação
COR_HAIRLINE = (216, 224, 234)          # #D8E0EA — Fio editorial sutil

MAPA_CARACTERES_PDF = {
    "—": " - ",
    "–": "-",
    "―": "-",
    "“": '"',
    "”": '"',
    "„": '"',
    "‘": "'",
    "’": "'",
    "‚": "'",
    "•": "-",
    "▪": "-",
    "▸": ">",
    "▹": ">",
    "►": ">",
    "→": "->",
    "←": "<-",
    "↔": "<->",
    "…": "...",
    "≥": ">=",
    "≤": "<=",
    "≠": "!=",
    "×": "x",
    "·": "|",
    "✓": "[OK]",
    "✔": "[OK]",
    "✅": "[OK]",
    "⚠": "[Atenção]",
    "❌": "[X]",
    "✕": "x",
}


def sanitizar_texto_pdf(texto: str, preservar_markdown_basico: bool = True) -> str:
    """Converte caracteres especiais/emojis para equivalentes compatíveis com Latin-1 (ISO-8859-1),
    preservando 100% da acentuação da língua portuguesa e limpando ruídos."""
    if not texto:
        return ""
    limpo = texto
    for orig, dest in MAPA_CARACTERES_PDF.items():
        limpo = limpo.replace(orig, dest)
    limpo = re.sub(r"<br\s*/?>", "\n", limpo, flags=re.IGNORECASE)
    limpo = re.sub(
        r"</?(?:summary|details|div|span|p|strong|em|code|pre)[^>]*>",
        "",
        limpo,
        flags=re.IGNORECASE,
    )
    # Evita que '--' ou '__' ative sublinhado acidental no modo markdown do fpdf2
    limpo = re.sub(r"-{2,}", "-", limpo)
    limpo = re.sub(r"_{2,}", "_", limpo)
    if not preservar_markdown_basico:
        limpo = limpo.replace("**", "").replace("__", "").replace("`", "")
    else:
        limpo = limpo.replace("`", "")
    resultado = limpo.encode("latin-1", errors="ignore").decode("latin-1")
    return re.sub(r"[ \t]{2,}", " ", resultado).strip()


def separar_corpo_e_gabarito(texto_md: str) -> tuple[str, str]:
    """Separa o enunciado das questões do bloco de Gabarito Comentado.

    Detecta tanto tags `<details>...</details>` quanto seções Markdown iniciadas por
    `Gabarito Comentado`, `Gabarito da Mara` ou `Gabarito Oficial`, garantindo que a
    folha do desbravador nunca exiba as respostas na mesma página da prova.
    """
    if not texto_md:
        return "", ""

    # 1. Caso haja bloco explícito <details>...</details>
    padrao_details = re.compile(r"<details[^>]*>(.*?)</details>", flags=re.IGNORECASE | re.DOTALL)
    matches = padrao_details.findall(texto_md)
    if matches:
        corpo = padrao_details.sub("", texto_md).strip()
        gabaritos: list[str] = []
        for m in matches:
            sem_summary = re.sub(
                r"<summary[^>]*>.*?</summary>", "", m, flags=re.IGNORECASE | re.DOTALL
            ).strip()
            if sem_summary:
                gabaritos.append(sem_summary)
        return corpo, "\n\n".join(gabaritos)

    # 2. Caso o modelo tenha gerado cabeçalho ou destaque Markdown de Gabarito
    padrao_heading_gab = re.compile(
        r"(?:^|\n)(?:#{1,4}\s*|\*\*\s*)(?:🎯\s*|✅\s*)?"
        r"(Gabarito(?:\s+Comentado)?(?:\s+da\s+Mara|\s+Oficial)?)\s*(?:\*\*)?:?\s*\n",
        flags=re.IGNORECASE,
    )
    m_gab = padrao_heading_gab.search(texto_md)
    if m_gab:
        idx = m_gab.start()
        corpo = texto_md[:idx].strip()
        gabarito = texto_md[m_gab.end() :].strip()
        if corpo and gabarito:
            return corpo, gabarito

    return texto_md, ""


def _resolver_caminho_logo_d1() -> Path | None:
    candidatos = [
        RAIZ / "assets" / "logos" / "emblema_d1_triangulo.png",
        RAIZ / "assets" / "emblema_d1.svg",
        RAIZ / "assets" / "imagens" / "Logos" / "D1" / "Imagem 005.jpg",
    ]
    for c in candidatos:
        if c.exists():
            return c
    return None


def _resolver_caminho_logo_infinito() -> Path | None:
    candidatos = [
        RAIZ / "assets" / "logos" / "infinito-logo-transparente.png",
        RAIZ / "assets" / "logos" / "infinito-logo-vetorial-dark.svg",
    ]
    for c in candidatos:
        if c.exists():
            return c
    return None


class MaraPDF(FPDF):
    """Documento PDF editorial A4 com margens equilibradas (15mm) e cabeçalho/rodapé oficiais."""

    def __init__(
        self,
        nome_clube: str = "Clube de Desbravadores (DSA)",
        subtitulo_doc: str = "Material de Consulta Oficial",
        tag_direita: str = "MANUAIS DSA",
    ) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.nome_clube = sanitizar_texto_pdf(nome_clube, False) or "Clube de Desbravadores (DSA)"
        self.subtitulo_doc = sanitizar_texto_pdf(subtitulo_doc, False)
        self.tag_direita = sanitizar_texto_pdf(tag_direita, False).upper()
        self.logo_d1_path = _resolver_caminho_logo_d1()
        self.logo_infinito_path = _resolver_caminho_logo_infinito()
        self.set_margins(left=15, top=16, right=15)
        self.set_auto_page_break(auto=True, margin=18)
        self.alias_nb_pages()

    def header(self) -> None:
        # Coroa superior institucional discreta (Vermelho DSA + Filete Ouro + Filete Marinho)
        self.set_fill_color(*COR_VERMELHO_DSA)
        self.rect(0, 0, 210, 2.2, style="F")
        self.set_fill_color(*COR_OURO_DSA)
        self.rect(0, 2.2, 210, 0.8, style="F")

        y_top = 7.2
        x_texto = 15.0
        if self.logo_d1_path is not None:
            try:
                self.image(str(self.logo_d1_path), x=15.0, y=y_top - 0.4, h=11.0)
                x_texto = 28.5
            except Exception:
                x_texto = 15.0

        # Tag editorial alinhada à margem direita (equal edges: x=195mm)
        if self.tag_direita:
            self.set_xy(140, y_top + 0.4)
            self.set_font("Helvetica", "B", 7.2)
            self.set_text_color(*COR_ACENTO_ACAO)
            self.cell(55, 4.2, self.tag_direita, align="R")

        # Título institucional à esquerda
        self.set_xy(x_texto, y_top)
        self.set_font("Helvetica", "B", 10.2)
        self.set_text_color(*COR_MARINHO_INFINITO)
        self.cell(115, 4.8, "MARA  |  IA DOS DESBRAVADORES", new_x="LMARGIN", new_y="NEXT")

        self.set_x(x_texto)
        self.set_font("Helvetica", "", 8.2)
        self.set_text_color(*COR_TINTA_MUTED)
        sub_linha = f"{self.nome_clube}  -  {self.subtitulo_doc}"
        self.cell(150, 4.4, sub_linha[:95], new_x="LMARGIN", new_y="NEXT")

        # Hairline divisório (15mm a 195mm = 180mm úteis)
        self.set_draw_color(*COR_HAIRLINE)
        self.set_line_width(0.22)
        self.line(15, 20.8, 195, 20.8)
        self.set_y(24.5)

    def footer(self) -> None:
        self.set_y(-13.5)
        self.set_draw_color(*COR_HAIRLINE)
        self.set_line_width(0.2)
        self.line(15, self.get_y(), 195, self.get_y())
        self.ln(1.8)

        x_rodape = 15.0
        y_atual = self.get_y()
        if self.logo_infinito_path is not None:
            try:
                self.image(str(self.logo_infinito_path), x=15.0, y=y_atual - 0.3, h=4.2)
                x_rodape = 22.5
            except Exception:
                x_rodape = 15.0

        self.set_xy(x_rodape, y_atual)
        self.set_font("Helvetica", "", 7.3)
        self.set_text_color(*COR_TINTA_MUTED)
        data_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        rodape_esq = sanitizar_texto_pdf(
            f"Infinito Soft  |  mara.infinitosoft.com  |  Baseado nos Manuais Oficiais DSA  ({data_str})",
            False,
        )
        self.cell(135, 4, rodape_esq, align="L")
        self.set_font("Helvetica", "B", 7.3)
        self.cell(0, 4, sanitizar_texto_pdf(f"Página {self.page_no()} de {{nb}}", False), align="R")


def _garantir_espaco_vertical(pdf: MaraPDF, altura_minima_mm: float = 24.0) -> None:
    """Evita títulos ou cabeçalhos órfãos no fim da página."""
    limite_util = pdf.h - pdf.b_margin
    if pdf.get_y() + altura_minima_mm > limite_util:
        pdf.add_page()


def _renderizar_cabecalho_prova(pdf: MaraPDF, categoria_rotulo: str) -> None:
    """Desenha ficha limpa de identificação do Desbravador com linhas confortáveis para escrita."""
    _garantir_espaco_vertical(pdf, 30.0)
    y0 = pdf.get_y()

    pdf.set_fill_color(*COR_SUPERFICIE_PROVA)
    pdf.set_draw_color(*COR_HAIRLINE)
    pdf.set_line_width(0.25)
    pdf.rect(15, y0, 180, 24.5, style="DF")

    # Filete lateral ouro de identificação
    pdf.set_fill_color(*COR_OURO_DSA)
    pdf.rect(15, y0, 1.3, 24.5, style="F")

    pdf.set_xy(19, y0 + 2.4)
    pdf.set_font("Helvetica", "B", 8.0)
    pdf.set_text_color(146, 64, 14)
    pdf.cell(
        0,
        4.2,
        sanitizar_texto_pdf(
            f"FOLHA DE AVALIAÇÃO DO DESBRAVADOR  |  ESCOPO: {categoria_rotulo.upper()}", False
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    # Linhas vetoriais finas para preenchimento à caneta/lápis (sem underscores serrilhados)
    pdf.set_font("Helvetica", "", 8.6)
    pdf.set_text_color(*COR_TINTA_CORPO)
    pdf.set_draw_color(180, 190, 204)
    pdf.set_line_width(0.25)

    # Linha 1: Nome e Unidade
    y_l1 = y0 + 9.0
    pdf.set_xy(19, y_l1)
    pdf.cell(12, 5.5, "Nome:")
    pdf.line(31.5, y_l1 + 4.6, 128.0, y_l1 + 4.6)
    pdf.set_xy(132.0, y_l1)
    pdf.cell(15, 5.5, "Unidade:")
    pdf.line(147.5, y_l1 + 4.6, 191.0, y_l1 + 4.6)

    # Linha 2: Classe/Especialidade, Data e Nota
    y_l2 = y0 + 16.2
    pdf.set_xy(19, y_l2)
    pdf.cell(35, 5.5, "Classe / Especialidade:")
    pdf.line(54.5, y_l2 + 4.6, 118.0, y_l2 + 4.6)
    pdf.set_xy(122.0, y_l2)
    pdf.cell(10, 5.5, "Data:")
    pdf.line(132.5, y_l2 + 4.6, 160.0, y_l2 + 4.6)
    pdf.set_xy(164.0, y_l2)
    pdf.cell(10, 5.5, "Nota:")
    pdf.line(174.0, y_l2 + 4.6, 191.0, y_l2 + 4.6)

    pdf.set_y(y0 + 28.5)


def _renderizar_box_destaque(
    pdf: MaraPDF,
    rotulo: str,
    conteudo: str,
    cor_barra: tuple[int, int, int] = COR_ACENTO_ACAO,
) -> None:
    """Renderiza callout editorial limpo com barra lateral de 1.2mm (sem caixa pesada de 4 lados)."""
    texto_limpo = sanitizar_texto_pdf(conteudo, False)
    if not texto_limpo:
        return

    _garantir_espaco_vertical(pdf, 18.0)
    x0 = pdf.l_margin
    largura = 180.0

    # Calcula altura estimada com folga segura
    pdf.set_font("Helvetica", "", 9.6)
    linhas_est = max(1, len(pdf.multi_cell(largura - 8, 5.2, texto_limpo, dry_run=True, output="LINES")))
    altura_box = 7.5 + (linhas_est * 5.2) + 2.8

    _garantir_espaco_vertical(pdf, altura_box + 2)
    y0 = pdf.get_y()

    pdf.set_fill_color(*COR_SUPERFICIE)
    pdf.rect(x0, y0, largura, altura_box, style="F")
    pdf.set_fill_color(*cor_barra)
    pdf.rect(x0, y0, 1.2, altura_box, style="F")

    pdf.set_xy(x0 + 4.2, y0 + 2.2)
    pdf.set_font("Helvetica", "B", 7.8)
    pdf.set_text_color(*cor_barra)
    pdf.cell(largura - 6, 4.2, sanitizar_texto_pdf(rotulo.upper(), False), new_x="LMARGIN", new_y="NEXT")

    pdf.set_xy(x0 + 4.2, y0 + 6.8)
    pdf.set_font("Helvetica", "B", 9.6)
    pdf.set_text_color(*COR_MARINHO_INFINITO)
    pdf.multi_cell(largura - 6.5, 5.2, texto_limpo)

    pdf.set_y(y0 + altura_box + 3.5)


def _calcular_larguras_colunas(linhas_tabela: list[list[str]], largura_total: float = 180.0) -> list[float]:
    """Calcula larguras proporcionais inteligentes para as colunas da tabela sem esmagar textos longos."""
    n_cols = max(len(r) for r in linhas_tabela)
    if n_cols <= 1:
        return [largura_total]

    pesos: list[float] = []
    for c_idx in range(n_cols):
        max_len = max((len(r[c_idx]) for r in linhas_tabela if c_idx < len(r)), default=10)
        # Raiz suavizada evita que uma coluna longa esmague completamente colunas curtas
        pesos.append(max(12.0, min(85.0, float(max_len) ** 0.72)))

    soma = sum(pesos) or 1.0
    larguras = [(p / soma) * largura_total for p in pesos]
    return larguras


def _renderizar_tabela_markdown(pdf: MaraPDF, linhas_brutas_tabela: list[str]) -> None:
    """Renderiza tabela Markdown completa com quebra automática de múltiplas linhas via fpdf2."""
    linhas_limpas: list[list[str]] = []
    for lb in linhas_brutas_tabela:
        s = lb.strip()
        if re.match(r"^\|?[\s:\-\|]+\|?$", s) and "-" in s:
            continue
        partes = [sanitizar_texto_pdf(c.strip(), False) for c in s.strip("|").split("|")]
        if any(partes):
            linhas_limpas.append(partes)

    if not linhas_limpas:
        return

    n_cols = max(len(r) for r in linhas_limpas)
    linhas_norm = [r + [""] * (n_cols - len(r)) for r in linhas_limpas]
    larguras = _calcular_larguras_colunas(linhas_norm, largura_total=180.0)

    _garantir_espaco_vertical(pdf, 18.0)
    pdf.ln(1.2)
    pdf.set_font("Helvetica", "", 8.8)
    pdf.set_text_color(*COR_TINTA_CORPO)
    pdf.set_draw_color(*COR_HAIRLINE)
    pdf.set_line_width(0.22)

    estilo_cabecalho = FontFace(
        emphasis="BOLD",
        color=COR_MARINHO_INFINITO,
        fill_color=COR_SUPERFICIE_TABELA,
        size_pt=8.6,
    )

    with pdf.table(
        col_widths=tuple(larguras),
        borders_layout="HORIZONTAL_LINES",
        cell_fill_color=COR_SUPERFICIE,
        cell_fill_mode="ROWS",
        headings_style=estilo_cabecalho,
        line_height=5.0,
        padding=(2.2, 2.6, 2.2, 2.6),
        text_align="LEFT",
        width=180,
    ) as tabela:
        for r_idx, cols in enumerate(linhas_norm):
            row = tabela.row()
            for txt_celula in cols:
                row.cell(txt_celula)
                if r_idx == 0:
                    pass

    pdf.ln(2.8)


def _renderizar_markdown_no_pdf(
    pdf: MaraPDF,
    texto_md: str,
    modo_simulado: bool = False,
) -> None:
    """Converte Markdown estruturado (títulos, tabelas multilinhas, citações, listas e alternativas) em PDF."""
    linhas = (texto_md or "").splitlines()
    idx = 0
    total = len(linhas)

    while idx < total:
        linha_strip = linhas[idx].strip()

        # Linhas em branco
        if not linha_strip:
            pdf.ln(1.8)
            idx += 1
            continue

        # Agrupamento de Tabelas Markdown completas
        if linha_strip.startswith("|") and "|" in linha_strip[1:]:
            bloco_tabela: list[str] = []
            while idx < total and linhas[idx].strip().startswith("|"):
                bloco_tabela.append(linhas[idx].strip())
                idx += 1
            _renderizar_tabela_markdown(pdf, bloco_tabela)
            continue

        # Divisor horizontal Markdown (--- ou ***)
        if re.match(r"^(?:-\s*){3,}$|^(?:\*\s*){3,}$|^(?:_\s*){3,}$", linha_strip):
            pdf.ln(1.5)
            pdf.set_draw_color(*COR_HAIRLINE)
            pdf.set_line_width(0.22)
            pdf.line(pdf.l_margin, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(2.5)
            idx += 1
            continue

        # Bloco de citação (> Voto, Lei, Lema, etc.)
        if linha_strip.startswith(">"):
            linhas_quote: list[str] = []
            while idx < total and linhas[idx].strip().startswith(">"):
                q_limpa = re.sub(r"^>+\s*", "", linhas[idx].strip())
                if q_limpa:
                    linhas_quote.append(sanitizar_texto_pdf(q_limpa, False))
                idx += 1
            texto_quote = " ".join(linhas_quote)
            if texto_quote:
                _garantir_espaco_vertical(pdf, 14.0)
                x0 = pdf.l_margin + 2
                larg_q = 176.0
                pdf.set_font("Helvetica", "I", 9.5)
                n_lq = max(
                    1,
                    len(pdf.multi_cell(larg_q - 7, 5.2, texto_quote, dry_run=True, output="LINES")),
                )
                alt_q = (n_lq * 5.2) + 4.4
                _garantir_espaco_vertical(pdf, alt_q + 2)
                yq = pdf.get_y()
                pdf.set_fill_color(*COR_SUPERFICIE)
                pdf.rect(x0, yq, larg_q, alt_q, style="F")
                pdf.set_fill_color(*COR_OURO_DSA)
                pdf.rect(x0, yq, 1.0, alt_q, style="F")
                pdf.set_xy(x0 + 4.0, yq + 2.2)
                pdf.set_text_color(*COR_MARINHO_INFINITO)
                pdf.multi_cell(larg_q - 6, 5.2, texto_quote)
                pdf.set_y(yq + alt_q + 2.2)
            continue

        # Títulos (#, ##, ###, ####) com proteção contra título órfão
        m_heading = re.match(r"^(#{1,4})\s+(.+)$", linha_strip)
        if m_heading:
            nivel = len(m_heading.group(1))
            titulo_txt = sanitizar_texto_pdf(m_heading.group(2), False)
            _garantir_espaco_vertical(pdf, 16.0)
            pdf.ln(2.0 if nivel <= 2 else 1.2)
            pdf.set_x(pdf.l_margin)
            if nivel == 1:
                pdf.set_font("Helvetica", "B", 13.0)
                pdf.set_text_color(*COR_MARINHO_INFINITO)
            elif nivel == 2:
                pdf.set_font("Helvetica", "B", 11.2)
                pdf.set_text_color(*COR_MARINHO_INFINITO)
            else:
                pdf.set_font("Helvetica", "B", 10.0)
                pdf.set_text_color(*COR_ACENTO_ACAO)
            pdf.multi_cell(0, 5.8, titulo_txt)
            pdf.ln(1.0)
            idx += 1
            continue

        # Alternativas de múltipla escolha (A) , B) , C) , D) ou a. , b. )
        m_alt = re.match(r"^([A-Ea-e])[\.\)]\s+(.+)$", linha_strip)
        if m_alt:
            letra = m_alt.group(1).upper()
            item_txt = sanitizar_texto_pdf(m_alt.group(2), True)
            _garantir_espaco_vertical(pdf, 8.0)
            y_alt = pdf.get_y()
            x_base = pdf.l_margin + 3.5

            if modo_simulado:
                # Desenha círculo vetorial limpo para marcação à caneta/lápis
                pdf.set_draw_color(148, 163, 184)
                pdf.set_line_width(0.3)
                pdf.ellipse(x_base, y_alt + 1.0, 3.3, 3.3, style="D")
                pdf.set_xy(x_base + 5.0, y_alt)
            else:
                pdf.set_xy(x_base, y_alt)

            pdf.set_font("Helvetica", "", 9.6)
            pdf.set_text_color(*COR_TINTA_CORPO)
            pdf.multi_cell(0, 5.3, f"**{letra})** {item_txt}", markdown=True)
            pdf.ln(0.7)
            idx += 1
            continue

        # Questões ou itens numerados (1. , 2. , Questão 1:)
        m_num = re.match(r"^(\d+[\.\)])\s+(.+)$", linha_strip)
        if m_num:
            prefixo = sanitizar_texto_pdf(m_num.group(1), False)
            item_txt = sanitizar_texto_pdf(m_num.group(2), True)
            _garantir_espaco_vertical(pdf, 12.0)
            if modo_simulado:
                pdf.ln(1.4)
            pdf.set_x(pdf.l_margin + 1.0)
            pdf.set_font("Helvetica", "", 9.8)
            pdf.set_text_color(*COR_MARINHO_INFINITO if modo_simulado else COR_TINTA_CORPO)
            pdf.multi_cell(0, 5.4, f"**{prefixo}** {item_txt}", markdown=True)
            pdf.ln(1.0)
            idx += 1
            continue

        # Listas com marcadores (- ou * ou +) com suporte a recuo
        recuo_espacos = len(linhas[idx]) - len(linhas[idx].lstrip(" "))
        m_lista = re.match(r"^[-*+]\s+(.+)$", linha_strip)
        if m_lista:
            item_txt = sanitizar_texto_pdf(m_lista.group(1), True)
            offset = 3.0 + min(8.0, (recuo_espacos // 2) * 3.0)
            _garantir_espaco_vertical(pdf, 7.5)
            y_li = pdf.get_y()
            # Marcador geométrico sutil
            pdf.set_fill_color(*COR_ACENTO_ACAO)
            pdf.ellipse(pdf.l_margin + offset, y_li + 2.1, 1.3, 1.3, style="F")
            pdf.set_xy(pdf.l_margin + offset + 3.2, y_li)
            pdf.set_font("Helvetica", "", 9.6)
            pdf.set_text_color(*COR_TINTA_CORPO)
            pdf.multi_cell(0, 5.2, item_txt, markdown=True)
            pdf.ln(0.6)
            idx += 1
            continue

        # Parágrafo comum
        paragrafo = sanitizar_texto_pdf(linha_strip, True)
        if paragrafo:
            _garantir_espaco_vertical(pdf, 8.0)
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "", 9.8)
            pdf.set_text_color(*COR_TINTA_CORPO)
            pdf.multi_cell(0, 5.4, paragrafo, markdown=True)
            pdf.ln(1.0)
        idx += 1


def _renderizar_fontes_no_pdf(pdf: MaraPDF, trechos: Sequence[TrechoRecuperado]) -> None:
    """Desenha bloco editorial de referências bibliográficas oficiais da DSA."""
    if not trechos:
        return

    vistos: set[tuple[str, int]] = set()
    fontes_unicas: list[TrechoRecuperado] = []
    for t in trechos:
        chave = (t.manual_titulo, t.pagina)
        if chave not in vistos:
            vistos.add(chave)
            fontes_unicas.append(t)

    _garantir_espaco_vertical(pdf, 16.0 + len(fontes_unicas) * 4.8)
    pdf.ln(3.0)
    y0 = pdf.get_y()
    pdf.set_draw_color(*COR_HAIRLINE)
    pdf.set_line_width(0.22)
    pdf.line(15, y0, 195, y0)
    pdf.ln(2.5)

    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 8.0)
    pdf.set_text_color(*COR_ACENTO_ACAO)
    pdf.cell(
        0,
        4.6,
        sanitizar_texto_pdf("REFERÊNCIAS OFICIAIS CONSULTADAS (ACERVO DSA)", False),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "", 8.3)
    pdf.set_text_color(*COR_TINTA_MUTED)
    for idx_f, f in enumerate(fontes_unicas, start=1):
        cat_label = ROTULOS_CATEGORIAS.get(f.categoria, f.categoria)
        linha_fonte = sanitizar_texto_pdf(
            f"[{idx_f}] {f.manual_titulo}  ({cat_label})  -  Página {f.pagina}", False
        )
        pdf.set_x(pdf.l_margin + 1.5)
        pdf.multi_cell(0, 4.5, linha_fonte)


def gerar_pdf_resposta(
    pergunta: str,
    resposta_md: str,
    trechos: Sequence[TrechoRecuperado] | None = None,
    nome_clube: str = "Clube de Desbravadores (DSA)",
    categoria: str = "TODAS",
    modo_quiz: bool = False,
) -> bytes:
    """Gera PDF editorial em memória (`bytes`) para consulta oficial ou folha de simulado.

    No modo simulado (`modo_quiz=True`), quando há gabarito comentado, separa-o automaticamente
    em uma nova página exclusiva para o Instrutor/Conselheiro, permitindo imprimir apenas a
    primeira folha para os desbravadores responderem sem ver o gabarito.
    """
    corpo_md, gabarito_md = separar_corpo_e_gabarito(resposta_md)
    eh_simulado = modo_quiz or bool(gabarito_md)
    cat_rotulo = ROTULOS_CATEGORIAS.get(categoria, categoria)
    subtitulo = "Folha de Avaliação e Simulado" if eh_simulado else "Ficha de Estudo e Consulta Oficial"
    tag_dir = "SIMULADO OFICIAL" if eh_simulado else f"ESCOPO: {categoria}"

    pdf = MaraPDF(nome_clube=nome_clube, subtitulo_doc=subtitulo, tag_direita=tag_dir)
    pdf.add_page()

    if eh_simulado:
        _renderizar_cabecalho_prova(pdf, cat_rotulo)

    if pergunta:
        rotulo_p = "Tema da Avaliação / Simulado" if eh_simulado else f"Consulta Oficial ({cat_rotulo})"
        _renderizar_box_destaque(
            pdf,
            rotulo=rotulo_p,
            conteudo=pergunta,
            cor_barra=COR_OURO_DSA if eh_simulado else COR_ACENTO_ACAO,
        )

    # Corpo principal da resposta ou caderno de questões
    _renderizar_markdown_no_pdf(pdf, corpo_md, modo_simulado=eh_simulado)

    # Em simulados, o Gabarito Comentado inicia em página exclusiva para o Instrutor/Conselheiro
    if gabarito_md:
        pdf.tag_direita = "USO DO INSTRUTOR"
        pdf.add_page()
        _renderizar_box_destaque(
            pdf,
            rotulo="Folha do Instrutor / Conselheiro",
            conteudo="Gabarito Comentado e Fundamentação nos Manuais Oficiais da DSA",
            cor_barra=COR_VERMELHO_DSA,
        )
        _renderizar_markdown_no_pdf(pdf, gabarito_md, modo_simulado=False)

    if trechos:
        _renderizar_fontes_no_pdf(pdf, trechos)

    return bytes(pdf.output())


def gerar_pdf_conversa(
    titulo: str,
    mensagens: Sequence[dict],
    nome_clube: str = "Clube de Desbravadores (DSA)",
    categoria: str = "TODAS",
    modo_quiz: bool = False,
) -> bytes:
    """Exporta todo o histórico de uma conversa em caderno de estudo editorial em PDF."""
    cat_rotulo = ROTULOS_CATEGORIAS.get(categoria, categoria)
    subtitulo = "Caderno de Simulados" if modo_quiz else "Caderno de Estudo e Consulta"
    tag_dir = "SIMULADO COMPLETO" if modo_quiz else "CADERNO DE ESTUDO"

    pdf = MaraPDF(nome_clube=nome_clube, subtitulo_doc=subtitulo, tag_direita=tag_dir)
    pdf.add_page()

    if modo_quiz:
        _renderizar_cabecalho_prova(pdf, cat_rotulo)

    # Título principal do caderno
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 13.5)
    pdf.set_text_color(*COR_MARINHO_INFINITO)
    pdf.multi_cell(0, 6.5, sanitizar_texto_pdf(titulo or "Caderno de Estudo com a Mara", False))
    pdf.ln(2.0)

    gabaritos_acumulados: list[tuple[int, str]] = []
    num_interacao = 0

    for msg in mensagens:
        role = msg.get("role", "")
        conteudo = str(msg.get("content", ""))
        if role == "user":
            num_interacao += 1
            _renderizar_box_destaque(
                pdf,
                rotulo=f" Tópico #{num_interacao}" if modo_quiz else f"Pergunta #{num_interacao}",
                conteudo=conteudo,
                cor_barra=COR_OURO_DSA if modo_quiz else COR_ACENTO_ACAO,
            )
        elif role == "assistant":
            corpo_md, gabarito_md = separar_corpo_e_gabarito(conteudo)
            _renderizar_markdown_no_pdf(pdf, corpo_md, modo_simulado=modo_quiz or bool(gabarito_md))

            if gabarito_md:
                gabaritos_acumulados.append((num_interacao, gabarito_md))

            trechos_msg = msg.get("trechos") or []
            if trechos_msg and not gabarito_md:
                _renderizar_fontes_no_pdf(pdf, trechos_msg)

            pdf.ln(2.5)
            pdf.set_draw_color(*COR_HAIRLINE)
            pdf.set_line_width(0.22)
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(3.5)

    # Se houve simulados na conversa, agrupa todos os gabaritos comentados na folha final do instrutor
    if gabaritos_acumulados:
        pdf.tag_direita = "USO DO INSTRUTOR"
        pdf.add_page()
        _renderizar_box_destaque(
            pdf,
            rotulo="Folha do Instrutor / Conselheiro",
            conteudo="Gabarito Comentado Oficial das Avaliações deste Caderno",
            cor_barra=COR_VERMELHO_DSA,
        )
        for idx_q, gab_txt in gabaritos_acumulados:
            if len(gabaritos_acumulados) > 1:
                pdf.set_font("Helvetica", "B", 10.5)
                pdf.set_text_color(*COR_MARINHO_INFINITO)
                pdf.cell(
                    0,
                    6.0,
                    sanitizar_texto_pdf(f"Gabarito da Avaliação #{idx_q}", False),
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
            _renderizar_markdown_no_pdf(pdf, gab_txt, modo_simulado=False)
            pdf.ln(2.0)

    return bytes(pdf.output())


def gerar_pdf_guia_biblioteca(
    titulo: str,
    subtitulo: str,
    badge: str,
    resumo_md: str,
    nome_clube: str = "Clube de Desbravadores (DSA)",
    logo_relativo: str | None = None,
) -> bytes:
    """Gera apostila/guia rápido editorial em PDF a partir de um item da Biblioteca."""
    pdf = MaraPDF(
        nome_clube=nome_clube,
        subtitulo_doc="Guia Rápido Oficial da Biblioteca",
        tag_direita=badge or "BIBLIOTECA DSA",
    )
    pdf.add_page()

    # Cabeçalho editorial da apostila (exibe insígnia apenas quando distinta do D1 já presente no topo)
    y0 = pdf.get_y()
    larg_titulo = 180.0
    if logo_relativo and not logo_relativo.upper().startswith("D1/"):
        caminho_insignia = RAIZ / "assets" / "imagens" / "Logos" / logo_relativo
        if caminho_insignia.exists():
            try:
                import io as _io
                from PIL import Image as _Image, ImageDraw as _ImageDraw

                img_ins = _Image.open(caminho_insignia).convert("RGBA")
                w_i, h_i = img_ins.size
                for sx, sy in [(0, 0), (w_i - 1, 0), (0, h_i - 1), (w_i - 1, h_i - 1)]:
                    r_c, g_c, b_c, a_c = img_ins.getpixel((sx, sy))
                    if a_c > 0 and r_c > 235 and g_c > 235 and b_c > 235:
                        _ImageDraw.floodfill(img_ins, (sx, sy), (255, 255, 255, 0), thresh=28)
                bbox = img_ins.getbbox()
                if bbox:
                    img_ins = img_ins.crop(bbox)
                buf_ins = _io.BytesIO()
                img_ins.save(buf_ins, format="PNG")
                buf_ins.seek(0)
                pdf.image(buf_ins, x=180.0, y=y0, h=14.0)
                larg_titulo = 160.0
            except Exception:
                larg_titulo = 180.0

    pdf.set_xy(15, y0)
    pdf.set_font("Helvetica", "B", 8.0)
    pdf.set_text_color(*COR_ACENTO_ACAO)
    pdf.cell(
        larg_titulo,
        4.5,
        sanitizar_texto_pdf(f"GUIA DE REFERÊNCIA RÁPIDA  |  {badge.upper()}", False),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_x(15)
    pdf.set_font("Helvetica", "B", 14.0)
    pdf.set_text_color(*COR_MARINHO_INFINITO)
    pdf.multi_cell(larg_titulo, 6.6, sanitizar_texto_pdf(titulo, False))

    pdf.set_x(15)
    pdf.set_font("Helvetica", "", 9.6)
    pdf.set_text_color(*COR_TINTA_MUTED)
    pdf.multi_cell(larg_titulo, 5.2, sanitizar_texto_pdf(subtitulo, False))

    pdf.ln(3.0)
    pdf.set_draw_color(*COR_HAIRLINE)
    pdf.set_line_width(0.25)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(4.0)

    _renderizar_markdown_no_pdf(pdf, resumo_md, modo_simulado=False)
    return bytes(pdf.output())
