"""Exportação de consultas, simulados (quizzes), conversas e guias da Biblioteca em PDF.

Gera documentos prontos para impressão e uso em reuniões do Clube de Desbravadores,
Cantinho da Unidade, classes regulares/avançadas e provas de especialidades.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Sequence

from fpdf import FPDF

from .config import RAIZ
from .db import TrechoRecuperado
from .ingestao import ROTULOS_CATEGORIAS

MAPA_CARACTERES_PDF = {
    "—": "-",
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
    "✓": "[OK]",
    "✔": "[OK]",
    "✅": "[OK]",
    "⚠": "[!]",
    "❌": "[X]",
    "✕": "x",
}


def sanitizar_texto_pdf(texto: str) -> str:
    """Converte caracteres especiais/emojis para equivalentes compatíveis com Latin-1 (ISO-8859-1),
    preservando 100% da acentuação da língua portuguesa."""
    if not texto:
        return ""
    limpo = texto
    for orig, dest in MAPA_CARACTERES_PDF.items():
        limpo = limpo.replace(orig, dest)
    # Remove tags HTML residuais simples exceto quebras
    limpo = re.sub(r"<br\s*/?>", "\n", limpo, flags=re.IGNORECASE)
    limpo = re.sub(r"</?(?:summary|details|div|span|p|strong|em|code|pre)[^>]*>", "", limpo, flags=re.IGNORECASE)
    # Evita que '--' ou '__' ative sublinhado/itálico acidental no modo markdown do fpdf2
    limpo = re.sub(r"-{2,}", "-", limpo)
    limpo = re.sub(r"_{2,}", "_", limpo)
    return limpo.encode("latin-1", errors="ignore").decode("latin-1").strip()


def separar_corpo_e_gabarito(texto_md: str) -> tuple[str, str]:
    """Separa o conteúdo principal de blocos `<details>...</details>` (usados para gabarito no Modo Quiz)."""
    padrao = re.compile(r"<details[^>]*>(.*?)</details>", flags=re.IGNORECASE | re.DOTALL)
    matches = padrao.findall(texto_md or "")
    if not matches:
        return texto_md, ""

    corpo = padrao.sub("", texto_md).strip()
    gabaritos: list[str] = []
    for m in matches:
        # Remove a linha de <summary>...</summary> se existir
        sem_summary = re.sub(r"<summary[^>]*>.*?</summary>", "", m, flags=re.IGNORECASE | re.DOTALL).strip()
        if sem_summary:
            gabaritos.append(sem_summary)
    return corpo, "\n\n".join(gabaritos)


class MaraPDF(FPDF):
    """Documento PDF padronizado com cabeçalho e rodapé oficiais da Mara — IA dos Desbravadores."""

    def __init__(
        self,
        nome_clube: str = "Clube de Desbravadores (DSA)",
        subtitulo_doc: str = "Material de Consulta Oficial",
    ) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.nome_clube = sanitizar_texto_pdf(nome_clube) or "Clube de Desbravadores (DSA)"
        self.subtitulo_doc = sanitizar_texto_pdf(subtitulo_doc)
        self.logo_d1_path = RAIZ / "assets" / "logos" / "emblema_d1_triangulo.png"
        self.set_margins(left=14, top=16, right=14)
        self.set_auto_page_break(auto=True, margin=18)
        self.alias_nb_pages()

    def header(self) -> None:
        # Faixa superior institucional nas cores dos Desbravadores (Vermelho + Amarelo Ouro)
        self.set_fill_color(185, 28, 28)
        self.rect(0, 0, 210, 3.2, style="F")
        self.set_fill_color(217, 119, 6)
        self.rect(0, 3.2, 210, 1.2, style="F")

        y_top = 8.0
        x_texto = 14.0
        if self.logo_d1_path.exists():
            try:
                self.image(str(self.logo_d1_path), x=14, y=y_top, w=11)
                x_texto = 28.0
            except Exception:
                x_texto = 14.0

        self.set_xy(x_texto, y_top)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(15, 23, 42)
        self.cell(0, 5, "MARA - IA DOS DESBRAVADORES (DSA)", new_x="LMARGIN", new_y="NEXT")

        self.set_x(x_texto)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(100, 116, 139)
        info_direita = f"{self.nome_clube}  |  {self.subtitulo_doc}"
        self.cell(0, 4.5, info_direita, new_x="LMARGIN", new_y="NEXT")

        self.set_draw_color(203, 213, 225)
        self.set_line_width(0.3)
        self.line(14, 21.5, 196, 21.5)
        self.set_y(25.0)

    def footer(self) -> None:
        self.set_y(-13)
        self.set_draw_color(226, 232, 240)
        self.set_line_width(0.2)
        self.line(14, self.get_y(), 196, self.get_y())
        self.ln(1.5)
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(100, 116, 139)
        data_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        rodape_esq = sanitizar_texto_pdf(
            f"Gerado em {data_str} por Mara (mara.infinitosoft.com) - Manuais Oficiais da DSA"
        )
        self.cell(140, 4, rodape_esq, align="L")
        self.cell(0, 4, sanitizar_texto_pdf(f"Página {self.page_no()}/{{nb}}"), align="R")


def _renderizar_cabecalho_prova(pdf: MaraPDF, categoria_rotulo: str) -> None:
    """Desenha o cabeçalho de identificação do Desbravador para folhas de Simulado / Avaliação."""
    pdf.set_fill_color(254, 252, 232)
    pdf.set_draw_color(217, 119, 6)
    pdf.set_line_width(0.35)
    y0 = pdf.get_y()
    pdf.rect(14, y0, 182, 20, style="DF")

    pdf.set_xy(17, y0 + 2.5)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(146, 64, 14)
    pdf.cell(
        0,
        4.5,
        sanitizar_texto_pdf(f"FOLHA DE AVALIAÇÃO / SIMULADO DO CLUBE  -  ESCOPO: {categoria_rotulo.upper()}"),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_x(17)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(
        0,
        6,
        sanitizar_texto_pdf("Desbravador(a): ___________________________________________   Unidade: ________________________"),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_x(17)
    pdf.cell(
        0,
        5.5,
        sanitizar_texto_pdf("Classe / Especialidade: ____________________________________   Data: ____/____/______   Nota: ______"),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_y(y0 + 23.5)


def _renderizar_markdown_no_pdf(pdf: MaraPDF, texto_md: str) -> None:
    """Converte blocos Markdown (títulos, listas, tabelas e parágrafos com negrito) para chamadas FPDF."""
    linhas = (texto_md or "").splitlines()
    em_tabela = False

    for linha_bruta in linhas:
        linha_strip = linha_bruta.strip()

        if not linha_strip:
            em_tabela = False
            pdf.ln(2.2)
            continue

        # Ignora linhas separadoras de tabela markdown (ex: | :--- | :--- |)
        if re.match(r"^\|?[\s:\-\|]+\|?$", linha_strip) and "-" in linha_strip:
            continue

        # Linha de tabela Markdown
        if linha_strip.startswith("|") and linha_strip.endswith("|"):
            colunas = [sanitizar_texto_pdf(c.strip().replace("**", "")) for c in linha_strip.strip("|").split("|")]
            colunas = [c for c in colunas if c != ""]
            if colunas:
                largura_total = 182.0
                larg_col = largura_total / len(colunas)
                pdf.set_x(pdf.l_margin)
                if not em_tabela:
                    pdf.set_fill_color(241, 245, 249)
                    pdf.set_font("Helvetica", "B", 8.5)
                    pdf.set_text_color(15, 23, 42)
                    em_tabela = True
                    preencher = True
                else:
                    pdf.set_font("Helvetica", "", 8.5)
                    pdf.set_text_color(30, 41, 59)
                    preencher = False

                altura_linha = 6.0
                for col_txt in colunas:
                    txt_curto = col_txt[:42] + "..." if len(col_txt) > 45 else col_txt
                    pdf.cell(larg_col, altura_linha, txt_curto, border=1, fill=preencher)
                pdf.ln(altura_linha)
            continue

        em_tabela = False

        # Títulos (#, ##, ###, ####)
        m_heading = re.match(r"^(#{1,4})\s+(.+)$", linha_strip)
        if m_heading:
            nivel = len(m_heading.group(1))
            titulo_txt = sanitizar_texto_pdf(m_heading.group(2).replace("**", ""))
            pdf.ln(1.8)
            pdf.set_x(pdf.l_margin)
            if nivel == 1:
                pdf.set_font("Helvetica", "B", 13)
                pdf.set_text_color(15, 23, 42)
            elif nivel == 2:
                pdf.set_font("Helvetica", "B", 11.5)
                pdf.set_text_color(153, 27, 27)
            else:
                pdf.set_font("Helvetica", "B", 10.2)
                pdf.set_text_color(30, 41, 59)
            pdf.multi_cell(0, 5.8, titulo_txt)
            pdf.ln(1.0)
            continue

        # Listas com marcadores (- ou *)
        m_lista = re.match(r"^[-*+]\s+(.+)$", linha_strip)
        if m_lista:
            item_txt = sanitizar_texto_pdf(m_lista.group(1))
            pdf.set_x(pdf.l_margin + 3)
            pdf.set_font("Helvetica", "", 9.6)
            pdf.set_text_color(30, 41, 59)
            pdf.multi_cell(0, 5.2, f"-  {item_txt}", markdown=True)
            pdf.ln(0.6)
            continue

        # Listas numeradas (1. , 2. ) ou alternativas (A) , B) )
        m_num = re.match(r"^(\d+[\.\)]|[A-Da-d][\.\)])\s+(.+)$", linha_strip)
        if m_num:
            prefixo = sanitizar_texto_pdf(m_num.group(1))
            item_txt = sanitizar_texto_pdf(m_num.group(2))
            pdf.set_x(pdf.l_margin + 2)
            pdf.set_font("Helvetica", "", 9.6)
            pdf.set_text_color(30, 41, 59)
            pdf.multi_cell(0, 5.2, f"**{prefixo}** {item_txt}", markdown=True)
            pdf.ln(0.8)
            continue

        # Parágrafo comum
        paragrafo = sanitizar_texto_pdf(linha_strip)
        if paragrafo:
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "", 9.8)
            pdf.set_text_color(30, 41, 59)
            pdf.multi_cell(0, 5.3, paragrafo, markdown=True)
            pdf.ln(0.8)


def _renderizar_fontes_no_pdf(pdf: MaraPDF, trechos: Sequence[TrechoRecuperado]) -> None:
    """Desenha um quadro com as fontes oficiais e páginas consultadas para a resposta."""
    if not trechos:
        return

    vistos: set[tuple[str, int]] = set()
    fontes_unicas: list[TrechoRecuperado] = []
    for t in trechos:
        chave = (t.manual_titulo, t.pagina)
        if chave not in vistos:
            vistos.add(chave)
            fontes_unicas.append(t)

    pdf.ln(3)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 8.8)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(
        0,
        5,
        sanitizar_texto_pdf("FONTES OFICIAIS CONSULTADAS (MANUAIS DA DSA):"),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "", 8.3)
    pdf.set_text_color(100, 116, 139)
    for f in fontes_unicas:
        cat_label = ROTULOS_CATEGORIAS.get(f.categoria, f.categoria)
        linha_fonte = sanitizar_texto_pdf(f"- {f.manual_titulo} ({cat_label}) - pág. {f.pagina}")
        pdf.set_x(pdf.l_margin + 2)
        pdf.multi_cell(0, 4.4, linha_fonte)


def gerar_pdf_resposta(
    pergunta: str,
    resposta_md: str,
    trechos: Sequence[TrechoRecuperado] | None = None,
    nome_clube: str = "Clube de Desbravadores (DSA)",
    categoria: str = "TODAS",
    modo_quiz: bool = False,
) -> bytes:
    """Gera um arquivo PDF em memória (`bytes`) para uma resposta ou simulado individual da Mara."""
    corpo_md, gabarito_md = separar_corpo_e_gabarito(resposta_md)
    eh_simulado = modo_quiz or bool(gabarito_md)
    subtitulo = "Folha de Simulado / Quiz Oficial" if eh_simulado else "Estudo e Consulta Oficial"

    pdf = MaraPDF(nome_clube=nome_clube, subtitulo_doc=subtitulo)
    pdf.add_page()

    cat_rotulo = ROTULOS_CATEGORIAS.get(categoria, categoria)
    if eh_simulado:
        _renderizar_cabecalho_prova(pdf, cat_rotulo)

    # Box da Pergunta / Tema solicitado
    if pergunta:
        pdf.set_x(pdf.l_margin)
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(203, 213, 225)
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(15, 23, 42)
        rotulo_p = "Tema do Simulado:" if eh_simulado else "Pergunta Consultada:"
        pdf.multi_cell(
            0,
            6.2,
            sanitizar_texto_pdf(f"{rotulo_p} {pergunta}"),
            border=1,
            fill=True,
        )
        pdf.ln(3)

    # Corpo principal da resposta ou das questões
    _renderizar_markdown_no_pdf(pdf, corpo_md)

    # Se houver gabarito comentado (<details>), adiciona seção destacada para o instrutor/conselheiro
    if gabarito_md:
        pdf.ln(4)
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(146, 64, 14)
        pdf.cell(
            0,
            5,
            sanitizar_texto_pdf("- - - - - - - - - - GABARITO COMENTADO (USO DO INSTRUTOR / CONSELHEIRO) - - - - - - - - - -"),
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.ln(1.5)
        _renderizar_markdown_no_pdf(pdf, gabarito_md)

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
    """Exporta todo o histórico de uma conversa (todas as perguntas e respostas) em um único PDF."""
    subtitulo = "Simulado Completo" if modo_quiz else "Histórico de Consulta e Estudo"
    pdf = MaraPDF(nome_clube=nome_clube, subtitulo_doc=subtitulo)
    pdf.add_page()

    cat_rotulo = ROTULOS_CATEGORIAS.get(categoria, categoria)
    if modo_quiz:
        _renderizar_cabecalho_prova(pdf, cat_rotulo)

    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 12.5)
    pdf.set_text_color(15, 23, 42)
    pdf.multi_cell(0, 6.5, sanitizar_texto_pdf(titulo or "Conversa com a Mara"))
    pdf.ln(2)

    pergunta_atual = ""
    num_interacao = 0
    for msg in mensagens:
        role = msg.get("role", "")
        conteudo = str(msg.get("content", ""))
        if role == "user":
            pergunta_atual = conteudo
            num_interacao += 1
            pdf.ln(2)
            pdf.set_x(pdf.l_margin)
            pdf.set_fill_color(241, 245, 249)
            pdf.set_draw_color(203, 213, 225)
            pdf.set_font("Helvetica", "B", 9.5)
            pdf.set_text_color(15, 23, 42)
            pdf.multi_cell(
                0,
                6.0,
                sanitizar_texto_pdf(f"#{num_interacao} - Desbravador / Líder: {pergunta_atual}"),
                border=1,
                fill=True,
            )
            pdf.ln(2)
        elif role == "assistant":
            corpo_md, gabarito_md = separar_corpo_e_gabarito(conteudo)
            _renderizar_markdown_no_pdf(pdf, corpo_md)
            if gabarito_md:
                pdf.ln(2)
                pdf.set_x(pdf.l_margin)
                pdf.set_font("Helvetica", "B", 8.5)
                pdf.set_text_color(146, 64, 14)
                pdf.cell(
                    0,
                    5,
                    sanitizar_texto_pdf("- - - - - - GABARITO COMENTADO - - - - - -"),
                    align="C",
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
                _renderizar_markdown_no_pdf(pdf, gabarito_md)

            trechos_msg = msg.get("trechos") or []
            if trechos_msg:
                _renderizar_fontes_no_pdf(pdf, trechos_msg)

            pdf.ln(3)
            pdf.set_draw_color(226, 232, 240)
            pdf.line(14, pdf.get_y(), 196, pdf.get_y())
            pdf.ln(3)

    return bytes(pdf.output())


def gerar_pdf_guia_biblioteca(
    titulo: str,
    subtitulo: str,
    badge: str,
    resumo_md: str,
    nome_clube: str = "Clube de Desbravadores (DSA)",
) -> bytes:
    """Gera uma apostila/guia rápido em PDF a partir de um card da Biblioteca de Conhecimento."""
    pdf = MaraPDF(nome_clube=nome_clube, subtitulo_doc=f"Guia Rápido da Biblioteca - {badge}")
    pdf.add_page()

    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(15, 23, 42)
    pdf.multi_cell(0, 6.5, sanitizar_texto_pdf(titulo))

    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "I", 9.5)
    pdf.set_text_color(100, 116, 139)
    pdf.multi_cell(0, 5.2, sanitizar_texto_pdf(subtitulo))
    pdf.ln(3)

    _renderizar_markdown_no_pdf(pdf, resumo_md)
    return bytes(pdf.output())
