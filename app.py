r"""Interface Web do Chat DBV (Streamlit) — Layout Minimalista estilo Gemini
com Histórico no Navegador (sem login), Seletor de Modo integrado ao Chat,
Página de Biblioteca estruturada por Categorias e Painel Administrativo.

Execução:
    .\.venv\Scripts\streamlit.exe run app.py
"""
from __future__ import annotations

import base64
import html
import io
import sys
import uuid
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

from chatdbv.biblioteca import CATALOGO_BIBLIOTECA, ItemBiblioteca
from chatdbv.config import (
    MODELOS_DISPONIVEIS,
    Config,
    limpar_chave,
    salvar_configuracoes_no_env,
    verificar_senha_admin,
)
from chatdbv.db import TrechoRecuperado, criar_repositorio
from chatdbv.embeddings import Embedder
from chatdbv.ingestao import (
    CATEGORIAS_VALIDAS,
    ROTULOS_CATEGORIAS,
    ingerir_arquivo,
    ingerir_pasta,
)
from chatdbv.rag import MotorRAG

PASTA_LOGOS = RAIZ / "assets" / "imagens" / "Logos"
CAMINHO_SVG_D1 = RAIZ / "assets" / "emblema_d1.svg"


def render_html(bloco_html: str) -> None:
    """Remove indentação de 4+ espaços para evitar que o Streamlit trate HTML como código."""
    compacto = "\n".join(linha.strip() for linha in bloco_html.splitlines() if linha.strip())
    st.markdown(compacto, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def carregar_logo_data_uri(
    caminho_relativo: str,
    remover_fundo_branco_externo: bool = False,
    altura_max: int = 160,
) -> str:
    caminho = PASTA_LOGOS / caminho_relativo
    if not caminho.exists():
        if CAMINHO_SVG_D1.exists():
            b64 = base64.b64encode(CAMINHO_SVG_D1.read_bytes()).decode("ascii")
            return f"data:image/svg+xml;base64,{b64}"
        return ""

    if caminho.suffix.lower() == ".png" and not remover_fundo_branco_externo:
        b64 = base64.b64encode(caminho.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{b64}"

    img = Image.open(caminho).convert("RGBA")
    if remover_fundo_branco_externo:
        w, h = img.size
        for sx, sy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (0, h // 2)]:
            try:
                r, g, b, a = img.getpixel((sx, sy))
                if a > 0 and r > 235 and g > 235 and b > 235:
                    ImageDraw.floodfill(img, (sx, sy), (255, 255, 255, 0), thresh=28)
            except Exception:
                pass
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)

    if img.height > altura_max:
        proporcao = altura_max / float(img.height)
        nova_largura = max(1, int(img.width * proporcao))
        img = img.resize((nova_largura, altura_max), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


URI_D1 = carregar_logo_data_uri("D1/Imagem 005.jpg", remover_fundo_branco_externo=True, altura_max=140)
URI_LIDER = carregar_logo_data_uri("L1/globo-lider-desbravador.jpg", remover_fundo_branco_externo=True, altura_max=140)

CAMINHO_AVATAR_D1 = PASTA_LOGOS / "D1" / "Imagem 005.jpg"
AVATAR_DBV = str(CAMINHO_AVATAR_D1) if CAMINHO_AVATAR_D1.exists() else (str(CAMINHO_SVG_D1) if CAMINHO_SVG_D1.exists() else "🔺")
CAMINHO_AVATAR_USER = PASTA_LOGOS / "Classes" / "b6_guia.png"
AVATAR_USER = str(CAMINHO_AVATAR_USER) if CAMINHO_AVATAR_USER.exists() else "🧣"

st.set_page_config(
    page_title="Mara — IA dos Desbravadores",
    page_icon=AVATAR_DBV,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ==================== CSS MINIMALISTA ESTILO GEMINI ====================
render_html(
    """
    <style>
    :root {
        --dbv-azul: #0047AB;
        --dbv-petroleo: #005C8A;
        --dbv-ouro: #FFD600;
        --dbv-vermelho: #FF1300;
    }

    /* Fundo clean claro estilo Gemini */
    .stApp {
        background-color: #F8FAFC;
        cursor: default;
        caret-color: transparent;
    }

    /* Formato geral amplo para evitar quebras de linha indesejadas */
    div.stMainBlockContainer {
        max-width: 1140px !important;
        padding-top: 1.5rem !important;
        padding-bottom: 6.5rem !important;
    }

    /* Oculta o ícone de âncora/link ("anexo") e o rodapé/badge "Made with Streamlit" */
    [data-testid="stHeaderActionElements"],
    .stMarkdown h1 a, .stMarkdown h2 a, .stMarkdown h3 a,
    .stMarkdown h4 a, .stMarkdown h5 a, .stMarkdown h6 a,
    footer,
    [data-testid="stFooter"],
    [data-testid="stDecoration"],
    .stDeployButton,
    [class*="viewerBadge"],
    [id*="MainMenu"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        pointer-events: none !important;
    }

    /* Sem barra vertical de texto em elementos não-editáveis */
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
    .stApp p, .stApp span, .stApp label, .stApp div,
    div[data-testid="stMetric"], div[data-testid="stCaptionContainer"] {
        cursor: default;
        caret-color: transparent;
    }
    .gemini-welcome, .dbv-topbar, .lib-card-header, section[data-testid="stSidebar"],
    button, [role="tab"], summary {
        user-select: none !important;
        -webkit-user-select: none !important;
    }
    div[data-baseweb="select"],
    div[data-baseweb="select"] *,
    div[data-baseweb="select"] input {
        cursor: pointer !important;
        caret-color: transparent !important;
        user-select: none !important;
    }
    button, button *, [role="button"], [role="button"] *,
    [role="tab"], [role="tab"] *, [role="radio"], [role="radio"] *,
    label[data-baseweb="radio"], label[data-baseweb="radio"] *,
    summary, summary * {
        cursor: pointer !important;
        caret-color: transparent !important;
    }
    input[type="text"]:not([readonly]),
    input[type="password"]:not([readonly]),
    input[type="search"]:not([readonly]),
    input[type="number"]:not([readonly]),
    textarea,
    div[data-testid="stChatInput"] textarea {
        cursor: text !important;
        caret-color: #0047AB !important;
        user-select: text !important;
        -webkit-user-select: text !important;
    }

    /* Barra superior discreta quando já há conversa */
    .dbv-topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.4rem 0 0.85rem 0;
        margin-bottom: 1rem;
        border-bottom: 1px solid #E2E8F0;
    }
    .dbv-topbar-left {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .dbv-topbar-left img {
        width: 28px;
        height: auto;
    }
    .dbv-topbar-title {
        font-weight: 800;
        font-size: 1.05rem;
        color: #0F172A;
    }
    .dbv-topbar-badge {
        font-size: 0.76rem;
        font-weight: 600;
        color: #005C8A;
        background: #E0F2FE;
        padding: 3px 11px;
        border-radius: 999px;
    }

    /* Tela Inicial Minimalista Estilo Gemini (centralizada verticalmente) */
    .gemini-welcome {
        text-align: center;
        padding: 11vh 1rem 1.2rem 1rem;
    }
    .gemini-welcome img {
        width: 64px;
        height: auto;
        margin-bottom: 0.9rem;
        filter: drop-shadow(0 4px 10px rgba(0, 71, 171, 0.18));
    }
    .gemini-greeting {
        font-size: 2.2rem;
        font-weight: 800;
        line-height: 1.25;
        margin: 0 0 0.45rem 0;
        background: linear-gradient(90deg, #0047AB 0%, #005C8A 55%, #D90416 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .gemini-sub {
        font-size: 1.04rem;
        color: #64748B;
        margin: 0 auto;
        max-width: 100%;
        font-weight: 400;
    }

    /* Chips de sugestão limpos estilo Gemini */
    div.stMainBlockContainer .stButton > button {
        background: #FFFFFF !important;
        color: #1E293B !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 14px !important;
        font-weight: 500 !important;
        font-size: 0.89rem !important;
        padding: 0.65rem 1.05rem !important;
        min-height: 3.3rem !important;
        text-align: left !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04) !important;
        transition: all 0.16s ease !important;
    }
    div.stMainBlockContainer .stButton > button:hover {
        background: #F1F5F9 !important;
        border-color: #0047AB !important;
        color: #0047AB !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 10px rgba(0, 71, 171, 0.08) !important;
    }

    /* Barra inferior do Chat (stBottom) estilo seletor de modelo/modo do Gemini */
    div[data-testid="stBottom"] > div {
        background: linear-gradient(180deg, rgba(248,250,252,0) 0%, #F8FAFC 28%, #F8FAFC 100%) !important;
        padding-bottom: 1.8rem !important;
    }

    /* Barra Lateral Sutil */
    section[data-testid="stSidebar"] {
        background-color: #F1F5F9 !important;
        border-right: 1px solid #E2E8F0 !important;
    }
    section[data-testid="stSidebar"] .stButton > button {
        background: #FFFFFF !important;
        color: #0F172A !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 0.84rem !important;
        height: 2.4rem !important;
        min-height: 2.4rem !important;
        padding: 0 0.75rem !important;
        display: flex !important;
        align-items: center !important;
        justify-content: flex-start !important;
        overflow: hidden !important;
    }
    section[data-testid="stSidebar"] .stButton > button p {
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        margin: 0 !important;
        font-size: 0.84rem !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        border-color: #0047AB !important;
        color: #0047AB !important;
        background: #F8FAFC !important;
    }
    /* Botão de excluir conversa (segunda coluna da lista de recentes) */
    section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] > div:nth-child(2) .stButton > button {
        justify-content: center !important;
        padding: 0 !important;
        color: #64748B !important;
        border-color: transparent !important;
        background: transparent !important;
        box-shadow: none !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] > div:nth-child(2) .stButton > button:hover {
        color: #DC2626 !important;
        background: #FEE2E2 !important;
        border-color: #FCA5A5 !important;
    }
    .sidebar-section-label {
        font-size: 0.73rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #64748B;
        margin: 0.9rem 0 0.35rem 0.2rem;
    }

    /* Cards da página Biblioteca */
    .lib-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-top: 3px solid #0047AB;
        border-radius: 14px;
        padding: 1.05rem 1.15rem 0.75rem 1.15rem;
        margin-bottom: 0.5rem;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.03);
    }
    .lib-card-header {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        margin-bottom: 0.45rem;
    }
    .lib-card-header img {
        width: 42px;
        height: 42px;
        object-fit: contain;
        flex-shrink: 0;
    }
    .lib-card-title {
        font-weight: 800;
        font-size: 1rem;
        color: #0F172A;
        line-height: 1.25;
        margin-bottom: 0.2rem;
    }
    .lib-card-sub {
        font-size: 0.84rem;
        color: #475569;
        line-height: 1.38;
    }
    .lib-badge {
        display: inline-block;
        font-size: 0.7rem;
        font-weight: 700;
        color: #0047AB;
        background: #EFF6FF;
        border: 1px solid #BFDBFE;
        padding: 1px 8px;
        border-radius: 999px;
        margin-bottom: 0.3rem;
    }

    /* Mensagens do Chat limpas sem caixas pesadas */
    div[data-testid="stChatMessage"] {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0.75rem 0.25rem !important;
        margin-bottom: 0.4rem !important;
    }

    /* Indicador animado de busca e elaboração da resposta (estilo Gemini) */
    @keyframes dbvSpin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    @keyframes dbvPulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.65; }
    }
    .dbv-thinking-box {
        display: flex;
        align-items: center;
        gap: 14px;
        background: #FFFFFF;
        border: 1px solid #DBEAFE;
        border-left: 4px solid #0047AB;
        border-radius: 12px;
        padding: 0.85rem 1.1rem;
        margin: 0.25rem 0 0.6rem 0;
        box-shadow: 0 2px 8px rgba(0, 71, 171, 0.06);
        animation: dbvPulse 1.8s ease-in-out infinite;
    }
    .dbv-spinner {
        width: 22px;
        height: 22px;
        border: 3px solid #DBEAFE;
        border-top: 3px solid #0047AB;
        border-right: 3px solid #FFD600;
        border-radius: 50%;
        flex-shrink: 0;
        animation: dbvSpin 0.85s linear infinite;
    }
    .dbv-thinking-title {
        font-weight: 700;
        font-size: 0.92rem;
        color: #0F172A;
        line-height: 1.25;
    }
    .dbv-thinking-sub {
        font-size: 0.8rem;
        color: #64748B;
        margin-top: 2px;
    }

    /* Card de Fonte Consultada enxuto */
    .dbv-source-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-left: 3px solid #0047AB;
        border-radius: 8px;
        padding: 0.65rem 0.9rem;
        margin-bottom: 0.5rem;
    }
    .dbv-source-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 0.3rem;
    }
    .dbv-source-title { font-weight: 700; color: #0F172A; font-size: 0.88rem; }
    .dbv-page-badge {
        background-color: #FEF9C3;
        color: #854D0E;
        font-weight: 700;
        padding: 1px 8px;
        border-radius: 999px;
        font-size: 0.74rem;
    }
    .dbv-cat-badge {
        background-color: #E0F2FE;
        color: #0369A1;
        font-weight: 600;
        padding: 1px 8px;
        border-radius: 999px;
        font-size: 0.74rem;
    }
    .dbv-source-text {
        color: #475569;
        font-size: 0.84rem;
        line-height: 1.45;
        white-space: pre-wrap;
    }

    /* Painel Admin Clean */
    .dbv-admin-statusbar {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #0047AB;
        border-radius: 12px;
        padding: 0.85rem 1.15rem;
        margin-bottom: 1rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.75rem;
    }
    .badge-status-ok {
        background: #DCFCE7;
        color: #166534;
        padding: 3px 10px;
        border-radius: 999px;
        font-weight: 700;
        font-size: 0.78rem;
    }
    .badge-status-off {
        background: #FEE2E2;
        color: #991B1B;
        padding: 3px 10px;
        border-radius: 999px;
        font-weight: 700;
        font-size: 0.78rem;
    }
    </style>
    """
)


# ==================== IDENTIFICAÇÃO ANÔNIMA DO NAVEGADOR (SEM LOGIN) ====================
def obter_device_id_navegador() -> str:
    """Obtém ou cria um ID único persistente no cookie do navegador sem exigir login."""
    cookies = getattr(st.context, "cookies", {}) or {}
    cookie_id = cookies.get("dbv_device_id")

    if cookie_id and len(str(cookie_id)) >= 8:
        st.session_state.device_id = str(cookie_id)
        return str(cookie_id)

    if "device_id" not in st.session_state or not st.session_state.device_id:
        st.session_state.device_id = f"dbv_{uuid.uuid4().hex[:12]}"

    dev_id = st.session_state.device_id
    # Grava cookie para persistir por 1 ano neste navegador e remove qualquer badge "Made with Streamlit"
    components.html(
        f"""
        <script>
        try {{
            document.cookie = "dbv_device_id={dev_id}; path=/; max-age=31536000; SameSite=Lax";
            localStorage.setItem("dbv_device_id", "{dev_id}");
            const ocultarBadges = () => {{
                const doc = window.parent.document;
                doc.querySelectorAll('footer, [data-testid="stFooter"], [class*="viewerBadge"]').forEach(el => {{
                    el.style.display = 'none';
                }});
            }};
            ocultarBadges();
            setTimeout(ocultarBadges, 500);
            setTimeout(ocultarBadges, 1500);
        }} catch (e) {{}}
        </script>
        """,
        height=0,
        width=0,
    )
    return dev_id


def gerar_titulo_conversa(primeira_pergunta: str) -> str:
    limpo = " ".join(primeira_pergunta.strip().split())
    if len(limpo) <= 44:
        return limpo
    return limpo[:41].rstrip() + "..."


# ==================== ESTADO INICIAL DE SESSÃO ====================
if "conversa_id" not in st.session_state:
    st.session_state.conversa_id = None
if "mensagens" not in st.session_state:
    st.session_state.mensagens = []
if "last_interaction_id" not in st.session_state:
    st.session_state.last_interaction_id = None
if "pagina_atual" not in st.session_state:
    st.session_state.pagina_atual = "chat"
if "modo_chat" not in st.session_state:
    st.session_state.modo_chat = "💬 Consulta"
if "categoria_ativa" not in st.session_state:
    st.session_state.categoria_ativa = "TODAS"
if "admin_autenticado" not in st.session_state:
    st.session_state.admin_autenticado = False

device_id_atual = obter_device_id_navegador()

SUGESTOES_INICIAIS = [
    (
        "👕 Posição dos emblemas no bolso",
        "Qual a posição correta dos emblemas e tiras nos bolsos do uniforme de gala segundo o RUD?",
    ),
    (
        "🔵 Requisitos da Classe de Amigo",
        "Quais são os principais requisitos da Classe de Amigo (10 anos) e Amigo da Natureza?",
    ),
    (
        "⛺ Sistema de Unidades no Clube",
        "Quantos desbravadores formam uma unidade e qual o papel do conselheiro e do capitão?",
    ),
    (
        "🎯 Simulado rápido sobre os Ideais",
        "Gere um simulado com 3 questões sobre o Voto, a Lei, o Alvo e o Lema dos Desbravadores.",
    ),
]


def renderizar_fontes(trechos: list[TrechoRecuperado], exibir_detalhes: bool = False) -> None:
    if not exibir_detalhes or not trechos:
        return
    qtd = len(trechos)
    rotulo_qtd = "1 trecho relevante" if qtd == 1 else f"{qtd} trechos relevantes"
    with st.expander(f"📚 Fontes consultadas ({rotulo_qtd})", expanded=False):
        for i, t in enumerate(trechos, 1):
            titulo_esc = html.escape(t.manual_titulo)
            cat_esc = html.escape(t.categoria)
            pct_sim = max(1, min(99, int(round(t.similaridade * 100))))
            trecho_curto = t.texto[:420] + ("..." if len(t.texto) > 420 else "")
            texto_esc = html.escape(trecho_curto)
            render_html(
                f"""
                <div class="dbv-source-card">
                    <div class="dbv-source-header">
                        <span class="dbv-source-title">[{i}] {titulo_esc}</span>
                        <div>
                            <span class="dbv-cat-badge">{cat_esc}</span>
                            <span class="dbv-page-badge">Pág. {t.pagina} · {pct_sim}%</span>
                        </div>
                    </div>
                    <div class="dbv-source-text">{texto_esc}</div>
                </div>
                """
            )


def iniciar_nova_conversa(ir_para_chat: bool = True) -> None:
    st.session_state.conversa_id = None
    st.session_state.mensagens = []
    st.session_state.last_interaction_id = None
    if ir_para_chat:
        st.session_state.pagina_atual = "chat"


# ==================== INICIALIZAÇÃO DE CONFIGURAÇÃO E REPOSITÓRIO ====================
cfg_env = Config.carregar()
cfg = cfg_env

repo = criar_repositorio(cfg)
try:
    if not st.session_state.get("esquema_pronto"):
        repo.inicializar_esquema()
        st.session_state.esquema_pronto = True
    manuais_cadastrados = repo.listar_manuais()
except Exception:
    manuais_cadastrados = []

motor = MotorRAG(cfg=cfg, repo=repo) if cfg.gemini_api_key else None

if not manuais_cadastrados and (RAIZ / "data" / "manuais").exists():
    try:
        emb_boot = Embedder(cfg)
        ingerir_pasta(RAIZ / "data" / "manuais", repo, emb_boot)
        manuais_cadastrados = repo.listar_manuais()
    except Exception:
        pass

try:
    conversas_salvas = repo.listar_conversas_dispositivo(device_id_atual, limite=25)
except Exception:
    conversas_salvas = []

# ==================== GAVETA LATERAL (ESTILO GEMINI: NOVA CONVERSA + BIBLIOTECA + RECENTES) ====================
with st.sidebar:
    render_html(
        f"""
        <div style="display:flex;align-items:center;gap:10px;padding:0.2rem 0 0.7rem 0;">
            <img src="{URI_D1}" alt="D1" style="width:32px;height:auto;">
            <div>
                <div style="font-weight:800;font-size:1.05rem;color:#0F172A;line-height:1.1;">Mara</div>
                <div style="font-size:0.75rem;color:#64748B;">IA dos Desbravadores · {html.escape(cfg_env.nome_clube)}</div>
            </div>
        </div>
        """
    )

    if st.button("➕ Nova conversa", use_container_width=True):
        iniciar_nova_conversa(ir_para_chat=True)
        st.rerun()

    rotulo_btn_bib = (
        "📚 Biblioteca (Ativa)"
        if st.session_state.pagina_atual == "biblioteca"
        else f"📚 Biblioteca ({len(CATALOGO_BIBLIOTECA)} guias)"
    )
    if st.button(rotulo_btn_bib, use_container_width=True):
        st.session_state.pagina_atual = "biblioteca"
        st.rerun()

    # Histórico de conversas recentes salvas neste navegador (sem login)
    render_html('<div class="sidebar-section-label">Recentes neste navegador</div>')
    if not conversas_salvas:
        st.caption("Suas conversas aparecerão salvas aqui automaticamente.")
    else:
        for conv in conversas_salvas:
            icone_conv = "🎯" if conv.modo == "simulado" else "💬"
            destaque = "▸ " if conv.id == st.session_state.conversa_id else ""
            c_abrir, c_del = st.columns([4.6, 1], gap="small", vertical_alignment="center")
            if c_abrir.button(
                f"{destaque}{icone_conv} {conv.titulo}",
                key=f"open_{conv.id}",
                use_container_width=True,
            ):
                carregada = repo.carregar_conversa(conv.id, device_id_atual)
                if carregada:
                    resumo, msgs = carregada
                    st.session_state.conversa_id = resumo.id
                    st.session_state.mensagens = msgs
                    st.session_state.last_interaction_id = resumo.last_interaction_id
                    st.session_state.modo_chat = (
                        "🎯 Simulado / Quiz" if resumo.modo == "simulado" else "💬 Consulta"
                    )
                    st.session_state.categoria_ativa = resumo.categoria
                    st.session_state.pagina_atual = "chat"
                    st.rerun()
            if c_del.button("✕", key=f"del_conv_{conv.id}", use_container_width=True):
                repo.remover_conversa(conv.id, device_id_atual)
                if st.session_state.conversa_id == conv.id:
                    iniciar_nova_conversa(ir_para_chat=False)
                st.rerun()

    st.divider()
    if st.session_state.pagina_atual != "admin":
        if st.button("🔐 Painel da Diretoria", use_container_width=True):
            st.session_state.pagina_atual = "admin"
            st.rerun()
    else:
        if st.button("💬 Voltar para a Mara", use_container_width=True):
            st.session_state.pagina_atual = "chat"
            st.rerun()


# ==============================================================================
# VISÃO 1: PAINEL ADMINISTRATIVO (DIRETORIA)
# ==============================================================================
if st.session_state.pagina_atual == "admin":
    col_t, col_b = st.columns([4, 1])
    with col_t:
        st.markdown("### 🔐 Painel da Diretoria")
    with col_b:
        if st.button("← Voltar para a Mara", use_container_width=True):
            st.session_state.pagina_atual = "chat"
            st.rerun()

    if not st.session_state.admin_autenticado:
        col_esq, col_centro, col_dir = st.columns([1, 1.5, 1])
        with col_centro:
            render_html(
                f"""
                <div style="text-align:center;padding:1rem 0;">
                    <img src="{URI_LIDER}" style="width:68px;height:auto;margin-bottom:0.5rem;">
                    <div style="font-weight:800;font-size:1.2rem;color:#0F172A;">Acesso Restrito à Diretoria</div>
                    <div style="font-size:0.86rem;color:#64748B;">Digite a senha administrativa (padrão inicial: <code>admin123</code>)</div>
                </div>
                """
            )
            with st.form("form_login_admin"):
                senha_digitada = st.text_input("Senha", type="password", placeholder="••••••••")
                entrar = st.form_submit_button("Entrar no Painel", use_container_width=True)
                if entrar:
                    if verificar_senha_admin(senha_digitada, cfg_env.admin_password):
                        st.session_state.admin_autenticado = True
                        st.rerun()
                    else:
                        st.error("Senha incorreta.")
        st.stop()

    total_chunks_geral = sum(m.total_chunks for m in manuais_cadastrados)
    feedbacks = repo.listar_feedbacks(limite=100)
    positivos = sum(1 for f in feedbacks if f.positivo)
    taxa_aprovacao = f"{int((positivos / len(feedbacks)) * 100)}%" if feedbacks else "—"

    status_badge = (
        '<span class="badge-status-ok">● Chat Ativo</span>'
        if cfg_env.chat_ativo
        else '<span class="badge-status-off">● Em Manutenção</span>'
    )
    api_badge = (
        '<span class="badge-status-ok">🔑 Gemini Conectado</span>'
        if cfg_env.gemini_api_key
        else '<span class="badge-status-off">⚠️ Chave Pendente</span>'
    )
    layout_badge = (
        '<span class="badge-status-ok">📊 Layout Completo (Fontes + Estatísticas)</span>'
        if cfg_env.exibir_detalhes_tecnicos
        else '<span class="badge-status-ok">🧒 Layout Simples (Apenas Resposta)</span>'
    )

    render_html(
        f"""
        <div class="dbv-admin-statusbar">
            <div>
                <strong style="color:#0F172A;font-size:1rem;">🏕️ {html.escape(cfg_env.nome_clube)}</strong>
                <span style="color:#64748B;font-size:0.84rem;margin-left:8px;">({html.escape(repo.nome_backend)})</span>
            </div>
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                {layout_badge}
                {status_badge}
                {api_badge}
            </div>
        </div>
        """
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("📚 Manuais", len(manuais_cadastrados))
    k2.metric("🧩 Trechos (768d)", total_chunks_geral)
    k3.metric("💬 Avaliações", len(feedbacks))
    k4.metric("⭐ Aprovação", taxa_aprovacao)

    aba_ia, aba_manuais, aba_fb, aba_seg = st.tabs(
        [
            "🤖 IA & Sistema",
            "📚 Manuais & Upload",
            "📊 Avaliações",
            "🔑 Segurança",
        ]
    )

    with aba_ia:
        with st.form("form_config_ia"):
            c_col1, c_col2 = st.columns(2)
            with c_col1:
                novo_nome_clube = st.text_input("Nome do Clube / Campo", value=cfg_env.nome_clube)
                nova_api_key = st.text_input(
                    "Chave da API Google Gemini (GEMINI_API_KEY)",
                    value=cfg_env.gemini_api_key,
                    type="password",
                )
                opcoes_modelos = list(MODELOS_DISPONIVEIS)
                idx_modelo = (
                    opcoes_modelos.index(cfg_env.modelo_chat)
                    if cfg_env.modelo_chat in opcoes_modelos
                    else 0
                )
                novo_modelo = st.selectbox(
                    "Modelo Gemini",
                    options=opcoes_modelos,
                    index=idx_modelo,
                )
            with c_col2:
                novo_top_k = st.slider(
                    "Trechos recuperados por resposta (TOP_K)",
                    min_value=2,
                    max_value=12,
                    value=int(cfg_env.top_k),
                )
                novo_db_url = st.text_input(
                    "URL PostgreSQL + pgvector (vazio = SQLite local)",
                    value=cfg_env.database_url,
                )
                novo_modo_completo = st.toggle(
                    "📊 Modo Completo: exibir fontes consultadas, trechos e estatísticas",
                    value=cfg_env.exibir_detalhes_tecnicos,
                    help="Desligado (padrão): exibe apenas a resposta limpa e simplificada da Mara, ideal para crianças e desbravadores. Ligado: exibe contagem de trechos, % de relevância e as fontes consultadas.",
                )
                novo_chat_ativo = st.toggle("Chat aberto para consultas", value=cfg_env.chat_ativo)
                nova_msg_manut = st.text_input(
                    "Aviso quando em manutenção",
                    value=cfg_env.mensagem_manutencao,
                )

            if st.form_submit_button("💾 Salvar Configurações", use_container_width=True):
                salvar_configuracoes_no_env(
                    {
                        "NOME_CLUBE": novo_nome_clube.strip() or "Clube de Desbravadores — DSA",
                        "GEMINI_API_KEY": limpar_chave(nova_api_key),
                        "MODELO_CHAT": novo_modelo,
                        "TOP_K": str(novo_top_k),
                        "DATABASE_URL": novo_db_url.strip(),
                        "EXIBIR_DETALHES_TECNICOS": "true" if novo_modo_completo else "false",
                        "CHAT_ATIVO": "true" if novo_chat_ativo else "false",
                        "MENSAGEM_MANUTENCAO": nova_msg_manut.strip(),
                    }
                )
                st.success("✅ Configurações salvas no arquivo `.env`!")
                st.rerun()

    with aba_manuais:
        col_up1, col_up2 = st.columns([2, 1])
        with col_up1:
            arquivos_up = st.file_uploader(
                "Enviar manuais (.pdf, .md, .txt)",
                type=["pdf", "md", "txt"],
                accept_multiple_files=True,
            )
        with col_up2:
            cat_up = st.selectbox(
                "Categoria do manual",
                options=list(CATEGORIAS_VALIDAS),
                format_func=lambda c: f"{c} — {ROTULOS_CATEGORIAS.get(c, c)}",
            )
            forcar_up = st.checkbox("Reindexar se já existir", value=True)
            if st.button("📥 Salvar e Indexar", use_container_width=True, disabled=not arquivos_up):
                pasta_manuais = RAIZ / "data" / "manuais"
                pasta_manuais.mkdir(parents=True, exist_ok=True)
                emb_up = Embedder(cfg)
                with st.spinner("Processando e indexando..."):
                    for arq in arquivos_up:
                        destino = pasta_manuais / arq.name
                        destino.write_bytes(arq.getvalue())
                        ingerir_arquivo(
                            caminho=destino,
                            repo=repo,
                            embedder=emb_up,
                            categoria=cat_up,
                            forcar=forcar_up,
                        )
                st.success("✅ Manuais indexados!")
                st.rerun()

        st.divider()
        for m in manuais_cadastrados:
            c1, c2, c3, c4 = st.columns([3.5, 1.5, 1.5, 1])
            c1.markdown(f"**{m.titulo}**  \n`{m.arquivo}`")
            c2.markdown(f"`{m.categoria}`")
            c3.markdown(f"📄 {m.paginas} págs · 🧩 {m.total_chunks} trechos")
            if c4.button("🗑️ Excluir", key=f"del_m_{m.id}", use_container_width=True):
                repo.remover_manual(m.id)
                st.rerun()

    with aba_fb:
        if not feedbacks:
            st.info("Nenhuma avaliação registrada ainda.")
        else:
            for fb in feedbacks:
                icone = "👍" if fb.positivo else "👎"
                with st.expander(f"{icone} {fb.pergunta[:80]} ({fb.criado_em})"):
                    st.markdown(f"**Pergunta:** {fb.pergunta}")
                    st.markdown(f"**Resposta:**\n\n{fb.resposta}")
                    if st.button("🗑️ Remover", key=f"del_fb_{fb.id}"):
                        repo.remover_feedback(fb.id)
                        st.rerun()

    with aba_seg:
        c_s1, c_s2 = st.columns(2)
        with c_s1:
            with st.form("form_trocar_senha"):
                nova_senha_1 = st.text_input("Nova senha", type="password")
                nova_senha_2 = st.text_input("Confirmar nova senha", type="password")
                if st.form_submit_button("🔒 Atualizar Senha", use_container_width=True):
                    if len(nova_senha_1.strip()) < 4:
                        st.error("Use ao menos 4 caracteres.")
                    elif nova_senha_1 != nova_senha_2:
                        st.error("A confirmação não confere.")
                    else:
                        salvar_configuracoes_no_env({"ADMIN_PASSWORD": nova_senha_1.strip()})
                        st.success("Senha atualizada!")
        with c_s2:
            if st.button("🚪 Encerrar Sessão da Diretoria", use_container_width=True):
                st.session_state.admin_autenticado = False
                st.session_state.pagina_atual = "chat"
                st.rerun()

    st.stop()


# ==============================================================================
# VISÃO 2: PÁGINA "BIBLIOTECA" (CONTEÚDOS PRÉ-FEITOS E CATEGORIAS ESTILO GEMINI)
# ==============================================================================
if st.session_state.pagina_atual == "biblioteca":
    col_h1, col_h2 = st.columns([4.5, 1.2])
    with col_h1:
        render_html(
            f"""
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:0.3rem;">
                <img src="{URI_D1}" alt="D1" style="width:40px;height:auto;">
                <div>
                    <div style="font-weight:800;font-size:1.55rem;color:#0F172A;line-height:1.15;">Biblioteca do Clube</div>
                    <div style="font-size:0.92rem;color:#64748B;">Conteúdos pré-estruturados, resumos oficiais da DSA e manuais divididos por categoria.</div>
                </div>
            </div>
            """
        )
    with col_h2:
        if st.button("💬 Conversar com a Mara", use_container_width=True):
            st.session_state.pagina_atual = "chat"
            st.rerun()

    st.write("")

    opcoes_abas_cat = [
        "TODAS",
        "UNIFORMES",
        "CLASSES",
        "ADMINISTRATIVO",
        "HISTORIA_IDEAIS",
        "ESPECIALIDADES",
    ]
    nomes_abas_cat = {
        "TODAS": "✨ Todos os Conteúdos",
        "UNIFORMES": "📘 Uniformes (RUD)",
        "CLASSES": "🏕️ Classes & Liderança",
        "ADMINISTRATIVO": "📗 Manual Administrativo & Ordem Unida",
        "HISTORIA_IDEAIS": "🔺 História, Ideais e Emblemas",
        "ESPECIALIDADES": "🏅 Especialidades",
    }

    cat_selecionada_bib = st.pills(
        "Filtrar por categoria:",
        options=opcoes_abas_cat,
        default="TODAS",
        format_func=lambda c: nomes_abas_cat.get(c, c),
        label_visibility="collapsed",
    ) or "TODAS"

    # Botão rápido caso o usuário queira abrir o chat filtrado apenas nessa categoria
    if cat_selecionada_bib != "TODAS":
        c_foco1, c_foco2 = st.columns([3.5, 1.5])
        c_foco1.caption(
            f"Exibindo guias e manuais da categoria **{ROTULOS_CATEGORIAS.get(cat_selecionada_bib, cat_selecionada_bib)}**."
        )
        if c_foco2.button(
            f"🔍 Conversar só sobre {cat_selecionada_bib}",
            use_container_width=True,
        ):
            iniciar_nova_conversa(ir_para_chat=True)
            st.session_state.categoria_ativa = cat_selecionada_bib
            st.session_state.modo_chat = "💬 Consulta"
            st.rerun()

    itens_filtrados: list[ItemBiblioteca] = [
        item
        for item in CATALOGO_BIBLIOTECA
        if cat_selecionada_bib == "TODAS" or item.categoria == cat_selecionada_bib
    ]

    # Grid 2 colunas com os cards pré-feitos da Biblioteca
    col_b1, col_b2 = st.columns(2)
    for idx, item in enumerate(itens_filtrados):
        col_alvo = col_b1 if idx % 2 == 0 else col_b2
        uri_logo_item = carregar_logo_data_uri(
            item.logo_relativo,
            remover_fundo_branco_externo=True,
            altura_max=96,
        )
        with col_alvo:
            render_html(
                f"""
                <div class="lib-card">
                    <div class="lib-card-header">
                        <img src="{uri_logo_item}" alt="Logo">
                        <div>
                            <span class="lib-badge">{html.escape(item.badge)}</span>
                            <div class="lib-card-title">{html.escape(item.titulo)}</div>
                            <div class="lib-card-sub">{html.escape(item.subtitulo)}</div>
                        </div>
                    </div>
                </div>
                """
            )
            with st.expander("📖 Ver resumo estruturado pronto", expanded=False):
                st.markdown(item.resumo_markdown)

            b_chat, b_quiz = st.columns(2)
            if b_chat.button(
                "💬 Perguntar à Mara",
                key=f"lib_chat_{item.id}",
                use_container_width=True,
            ):
                iniciar_nova_conversa(ir_para_chat=True)
                st.session_state.categoria_ativa = item.categoria
                st.session_state.modo_chat = "💬 Consulta"
                st.session_state.mensagens.append({"role": "user", "content": item.pergunta_consulta})
                st.rerun()

            if b_quiz.button(
                "🎯 Gerar Simulado",
                key=f"lib_quiz_{item.id}",
                use_container_width=True,
            ):
                iniciar_nova_conversa(ir_para_chat=True)
                st.session_state.categoria_ativa = item.categoria
                st.session_state.modo_chat = "🎯 Simulado / Quiz"
                st.session_state.mensagens.append({"role": "user", "content": item.tema_simulado})
                st.rerun()

    # Seção inferior da Biblioteca: Manuais Oficiais Indexados no Banco para essa categoria
    st.divider()
    st.markdown("#### 📑 Documentos e Manuais Indexados nesta Categoria")
    manuais_da_cat = [
        m
        for m in manuais_cadastrados
        if cat_selecionada_bib == "TODAS" or m.categoria == cat_selecionada_bib
    ]
    if not manuais_da_cat:
        st.caption("Nenhum manual indexado especificamente nesta categoria ainda.")
    else:
        for m in manuais_da_cat:
            with st.expander(
                f"📘 {m.titulo} — ({ROTULOS_CATEGORIAS.get(m.categoria, m.categoria)} · {m.paginas} págs · {m.total_chunks} trechos)"
            ):
                trechos_m = repo.listar_chunks_manual(m.id, limite=10)
                for tm in trechos_m:
                    st.markdown(f"**Página {tm.pagina} (Trecho #{tm.ordem}):**")
                    st.text(tm.texto)
                    st.divider()

    st.stop()


# ==============================================================================
# VISÃO 3: HOME & CHAT MINIMALISTA ESTILO GEMINI
# ==============================================================================
if not cfg_env.chat_ativo:
    st.warning(f"🚧 {cfg_env.mensagem_manutencao}")
    st.stop()

modo_quiz = st.session_state.modo_chat == "🎯 Simulado / Quiz"
categoria_filtro = st.session_state.categoria_ativa
pergunta_clicada: str | None = None

# Se ainda não há mensagens, mostra a tela inicial E a barra de chat centralizadas (estilo Gemini)
if not st.session_state.mensagens:
    subtitulo_modo = (
        "Modo Simulado ativo: digite um tema ou escolha um tópico abaixo para a Mara montar questões comentadas"
        if modo_quiz
        else f"Sua instrutora e IA de apoio aos manuais do Clube de Desbravadores · {html.escape(cfg_env.nome_clube)}"
    )
    render_html(
        f"""
        <div class="gemini-welcome">
            <img src="{URI_D1}" alt="Emblema D1 Desbravadores">
            <div class="gemini-greeting">Maranata! Eu sou a Mara. Como posso ajudar?</div>
            <p class="gemini-sub">{subtitulo_modo}</p>
        </div>
        """
    )

    # Barra de chat centralizada logo abaixo da saudação (inline por estar dentro de st.container)
    with st.container():
        entrada_chat = st.chat_input(
            "Pergunte à Mara ou digite o tema para simulado...",
            key="chat_input_principal_fixo",
        )
        col_modo, col_escopo = st.columns([2.5, 3.5])
        with col_modo:
            modo_escolhido = st.segmented_control(
                "Modo da IA",
                options=["💬 Consulta", "🎯 Simulado / Quiz"],
                default=st.session_state.modo_chat,
                key="seletor_modo_home_centro",
                label_visibility="collapsed",
            )
            if modo_escolhido and modo_escolhido != st.session_state.modo_chat:
                st.session_state.modo_chat = modo_escolhido
                modo_quiz = modo_escolhido == "🎯 Simulado / Quiz"

        with col_escopo:
            if st.session_state.categoria_ativa != "TODAS":
                if st.button(
                    f"📂 Escopo: {st.session_state.categoria_ativa} ✕ (limpar)",
                    key="btn_limpar_escopo_centro",
                ):
                    st.session_state.categoria_ativa = "TODAS"
                    st.rerun()

    st.write("")
    c1, c2 = st.columns(2)
    for idx, (rotulo_chip, pergunta_completa) in enumerate(SUGESTOES_INICIAIS):
        col_alvo = c1 if idx % 2 == 0 else c2
        if col_alvo.button(rotulo_chip, key=f"chip_{idx}", use_container_width=True):
            if "Simulado" in rotulo_chip:
                st.session_state.modo_chat = "🎯 Simulado / Quiz"
            pergunta_clicada = pergunta_completa

    pergunta_ativa = pergunta_clicada or entrada_chat
    if pergunta_ativa:
        if not motor:
            st.error(
                "Configure a chave da API no **Painel da Diretoria** (menu lateral esquerdo) para iniciar."
            )
        else:
            st.session_state.mensagens.append({"role": "user", "content": pergunta_ativa})
            st.rerun()
    st.stop()

# Quando já há conversa no histórico, mostra a barra superior discreta e o chat ancorado no rodapé
rotulo_escopo = ROTULOS_CATEGORIAS.get(categoria_filtro, categoria_filtro)
badge_modo = "🎯 Modo Simulado" if modo_quiz else "💬 Modo Consulta"
render_html(
    f"""
    <div class="dbv-topbar">
        <div class="dbv-topbar-left">
            <img src="{URI_D1}" alt="D1">
            <span class="dbv-topbar-title">Mara</span>
        </div>
        <div style="display:flex;gap:8px;align-items:center;">
            <span class="dbv-topbar-badge">{badge_modo}</span>
            <span class="dbv-topbar-badge">{html.escape(rotulo_escopo)}</span>
        </div>
    </div>
    """
)

# ==================== HISTÓRICO DA CONVERSA ATIVA ====================
for idx, msg in enumerate(st.session_state.mensagens):
    avatar_icone = AVATAR_USER if msg["role"] == "user" else AVATAR_DBV
    with st.chat_message(msg["role"], avatar=avatar_icone):
        st.markdown(msg["content"])
        if msg.get("trechos"):
            renderizar_fontes(msg["trechos"], exibir_detalhes=cfg_env.exibir_detalhes_tecnicos)
        if msg["role"] == "assistant":
            c_up, c_down, _ = st.columns([1, 1, 10])
            if c_up.button("👍", key=f"up_{idx}", help="Resposta útil"):
                repo.registrar_feedback(msg.get("pergunta", ""), msg["content"], True)
                st.toast("Obrigado pelo feedback! 🔺")
            if c_down.button("👎", key=f"down_{idx}", help="Resposta imprecisa"):
                repo.registrar_feedback(msg.get("pergunta", ""), msg["content"], False)
                st.toast("Feedback registrado para revisão.")

# ==================== COMPOSER INFERIOR (QUANDO JÁ HÁ HISTÓRICO) ====================
with st._bottom:
    col_modo, col_escopo = st.columns([2.5, 3.5])
    with col_modo:
        modo_escolhido = st.segmented_control(
            "Modo da IA",
            options=["💬 Consulta", "🎯 Simulado / Quiz"],
            default=st.session_state.modo_chat,
            key="seletor_modo_bottom",
            label_visibility="collapsed",
        )
        if modo_escolhido and modo_escolhido != st.session_state.modo_chat:
            st.session_state.modo_chat = modo_escolhido
            modo_quiz = modo_escolhido == "🎯 Simulado / Quiz"

    with col_escopo:
        if st.session_state.categoria_ativa != "TODAS":
            if st.button(
                f"📂 Escopo: {st.session_state.categoria_ativa} ✕ (limpar)",
                key="btn_limpar_escopo_bottom",
            ):
                st.session_state.categoria_ativa = "TODAS"
                st.rerun()

entrada_chat = st.chat_input(
    "Pergunte à Mara ou digite o tema para simulado...",
    key="chat_input_conversa_bottom",
)

if entrada_chat:
    if not motor:
        st.error(
            "Configure a chave da API no **Painel da Diretoria** (menu lateral esquerdo) para iniciar."
        )
    else:
        st.session_state.mensagens.append({"role": "user", "content": entrada_chat})
        st.rerun()

# Se a última mensagem na fila for do usuário, gera a resposta com feedback visual em tempo real
if st.session_state.mensagens and st.session_state.mensagens[-1]["role"] == "user":
    ultima_pergunta = st.session_state.mensagens[-1]["content"]
    modo_quiz = st.session_state.modo_chat == "🎯 Simulado / Quiz"
    categoria_filtro = st.session_state.categoria_ativa

    with st.chat_message("assistant", avatar=AVATAR_DBV):
        placeholder_status = st.empty()
        placeholder_resposta = st.empty()

        # Etapa 1: Feedback imediato de busca nos manuais
        sub_busca = (
            "Localizando as páginas e artigos relacionados à sua pergunta"
            if cfg_env.exibir_detalhes_tecnicos
            else "Consultando os materiais do Clube de Desbravadores"
        )
        placeholder_status.markdown(
            '<div class="dbv-thinking-box">'
            '<div class="dbv-spinner"></div>'
            '<div>'
            '<div class="dbv-thinking-title">🔎 A Mara está buscando a sua resposta...</div>'
            f'<div class="dbv-thinking-sub">{sub_busca}</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        trechos = motor.recuperar(ultima_pergunta, categoria=categoria_filtro)

        # Etapa 2: Feedback visível enquanto o modelo Gemini analisa os trechos (thinking)
        acao_txt = "A Mara está montando o simulado" if modo_quiz else "A Mara está escrevendo a resposta"
        if cfg_env.exibir_detalhes_tecnicos:
            qtd_t = len(trechos)
            info_t = (
                " (1 trecho relevante localizado)"
                if qtd_t == 1
                else f" ({qtd_t} trechos relevantes localizados)"
            )
            sub_geracao = "Verificando páginas e preparando as citações oficiais"
        else:
            info_t = ""
            sub_geracao = "Organizando a explicação de um jeito fácil para você"

        placeholder_status.markdown(
            f'<div class="dbv-thinking-box">'
            f'<div class="dbv-spinner"></div>'
            f'<div>'
            f'<div class="dbv-thinking-title">✨ {acao_txt}{info_t}...</div>'
            f'<div class="dbv-thinking-sub">{sub_geracao}</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        texto_acumulado = ""
        try:
            fluxo = motor.responder_stream(
                pergunta=ultima_pergunta,
                trechos=trechos,
                modo_quiz=modo_quiz,
                previous_interaction_id=st.session_state.last_interaction_id,
            )
            for pedaco in fluxo:
                if pedaco:
                    if not texto_acumulado:
                        placeholder_status.empty()
                    texto_acumulado += pedaco
                    placeholder_resposta.markdown(texto_acumulado + " ▌")
        except Exception:
            texto_acumulado = ""

        if not texto_acumulado.strip():
            try:
                resp = motor.responder(
                    pergunta=ultima_pergunta,
                    categoria=categoria_filtro,
                    modo_quiz=modo_quiz,
                    previous_interaction_id=st.session_state.last_interaction_id,
                    trechos_pre_recuperados=trechos,
                )
                resposta_completa = resp.texto
                st.session_state.last_interaction_id = resp.interaction_id
                placeholder_status.empty()
                placeholder_resposta.markdown(resposta_completa)
            except Exception as exc_api:
                placeholder_status.empty()
                resposta_completa = (
                    f"⚠️ Não foi possível concluir a resposta neste momento (`{exc_api}`). "
                    "Tente enviar sua pergunta novamente."
                )
                placeholder_resposta.error(resposta_completa)
        else:
            resposta_completa = texto_acumulado
            if motor.ultimo_interaction_id:
                st.session_state.last_interaction_id = motor.ultimo_interaction_id
            placeholder_status.empty()
            placeholder_resposta.markdown(resposta_completa)

        renderizar_fontes(trechos, exibir_detalhes=cfg_env.exibir_detalhes_tecnicos)

    st.session_state.mensagens.append(
        {
            "role": "assistant",
            "content": str(resposta_completa),
            "trechos": trechos,
            "pergunta": ultima_pergunta,
        }
    )

    # Salva automaticamente a conversa no histórico deste navegador (sem login)
    if not st.session_state.conversa_id:
        st.session_state.conversa_id = f"conv_{uuid.uuid4().hex[:10]}"

    primeira_msg_user = next(
        (m["content"] for m in st.session_state.mensagens if m.get("role") == "user"),
        ultima_pergunta,
    )
    titulo_auto = gerar_titulo_conversa(primeira_msg_user)
    modo_codigo = "simulado" if modo_quiz else "consulta"

    try:
        repo.salvar_conversa(
            conversa_id=st.session_state.conversa_id,
            device_id=device_id_atual,
            titulo=titulo_auto,
            modo=modo_codigo,
            categoria=categoria_filtro,
            mensagens=st.session_state.mensagens,
            last_interaction_id=st.session_state.last_interaction_id,
        )
    except Exception:
        pass
