"""Extrai os requisitos oficiais integrais (item por item, incluindo gemas bíblicas)
das 8 páginas oficiais de Classes Regulares, Avançadas, Agrupadas e de Liderança da DSA,
baixa eventuais PDFs vinculados e remove duplicatas em data/manuais/."""
from __future__ import annotations

import html as _html
import re
from pathlib import Path
import httpx

RAIZ = Path(__file__).resolve().parents[1]
PASTA_MANUAIS = RAIZ / "data" / "manuais"

PAGINAS_CARTOES = [
    ("cartao_classe_01_amigo_e_amigo_da_natureza", "Cartão Oficial: Classe de Amigo e Amigo da Natureza (10 anos - DSA)", "https://www.adventistas.org/pt/desbravadores/classes/amigo-e-amigo-da-natureza/"),
    ("cartao_classe_02_companheiro_e_excursionismo", "Cartão Oficial: Classe de Companheiro e Companheiro de Excursionismo (11 anos - DSA)", "https://www.adventistas.org/pt/desbravadores/classes/companheiro-e-companheiro-de-excursionismo/"),
    ("cartao_classe_03_pesquisador_campo_e_bosque", "Cartão Oficial: Classe de Pesquisador e Pesquisador de Campo e Bosque (12 anos - DSA)", "https://www.adventistas.org/pt/desbravadores/classes/pesquisador-e-pesquisador-de-campo-e-bosque/"),
    ("cartao_classe_04_pioneiro_novas_fronteiras", "Cartão Oficial: Classe de Pioneiro e Pioneiro de Novas Fronteiras (13 anos - DSA)", "https://www.adventistas.org/pt/desbravadores/classes/pioneiro-e-pioneiro-de-novas-fronteiras/"),
    ("cartao_classe_05_excursionista_na_mata", "Cartão Oficial: Classe de Excursionista e Excursionista na Mata (14 anos - DSA)", "https://www.adventistas.org/pt/desbravadores/classes/excursionista-e-excursionista-na-mata/"),
    ("cartao_classe_06_guia_e_exploracao", "Cartão Oficial: Classe de Guia e Guia de Exploração (15 anos - DSA)", "https://www.adventistas.org/pt/desbravadores/classes/guia-e-guia-de-exploracao/"),
    ("cartao_classes_agrupadas_dsa", "Cartão Oficial: Classes Agrupadas (11 a 15 anos - DSA)", "https://www.adventistas.org/pt/desbravadores/classes/classes-agrupadas-requisitos/"),
    ("cartao_classes_lideranca_lider_lm_lma_dsa", "Cartões Oficiais de Liderança: Líder, Líder Master e Líder Master Avançado (DSA)", "https://www.adventistas.org/pt/desbravadores/classes/classes-de-lideranca-requisitos/"),
]

CANDIDATOS_RUD_PDF = [
    "http://deptos.adventistas.org.s3.amazonaws.com/desbravadores/ManualUniformesMDA.pdf",
    "http://deptos.adventistas.org.s3.amazonaws.com/desbravadores/RegulamentoUniformesMDA.pdf",
    "http://deptos.adventistas.org.s3.amazonaws.com/desbravadores/RUD_MDA.pdf",
    "https://deptos.adventistas.org/desbravadores/Regulamento_de_Uniformes_MDA.pdf",
    "https://files.adventistas.org/desbravadores/pt/2020/05/Regulamento-de-Uniformes-MDA-2020.pdf",
]


def html_para_markdown_paginado(raw_html: str, titulo: str, url: str) -> str:
    m = re.search(r"<article\b[^>]*>(.*?)</article>", raw_html, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        m = re.search(r"<main\b[^>]*>(.*?)</main>", raw_html, flags=re.DOTALL | re.IGNORECASE)
    corpo = m.group(1) if m else raw_html
    corpo = re.sub(r"<(script|style|nav|footer|header|svg|noscript)\b[^>]*>.*?</\1>", "", corpo, flags=re.DOTALL | re.IGNORECASE)
    corpo = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n\n# \1\n\n", corpo, flags=re.DOTALL | re.IGNORECASE)
    corpo = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n\n## \1\n\n", corpo, flags=re.DOTALL | re.IGNORECASE)
    corpo = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n\n### \1\n\n", corpo, flags=re.DOTALL | re.IGNORECASE)
    corpo = re.sub(r"<h4[^>]*>(.*?)</h4>", r"\n\n#### \1\n\n", corpo, flags=re.DOTALL | re.IGNORECASE)
    corpo = re.sub(r"<(strong|b)[^>]*>(.*?)</\1>", r"**\2**", corpo, flags=re.DOTALL | re.IGNORECASE)
    corpo = re.sub(r"<li[^>]*>(.*?)</li>", r"\n- \1", corpo, flags=re.DOTALL | re.IGNORECASE)
    corpo = re.sub(r"<br\s*/?>", "\n", corpo, flags=re.IGNORECASE)
    corpo = re.sub(r"</p>", "\n\n", corpo, flags=re.IGNORECASE)
    corpo = re.sub(r"<[^>]+>", " ", corpo)
    corpo = _html.unescape(corpo)
    corpo = re.sub(r"[ \t]+", " ", corpo)
    corpo = re.sub(r"\n{3,}", "\n\n", corpo).strip()

    # Divide em seções lógicas (~2500 chars por "página" lógica) para citações precisas
    paragrafos = [p.strip() for p in corpo.split("\n\n") if p.strip()]
    paginas: list[str] = []
    atual = f"# {titulo}\nFonte Oficial DSA: {url}"
    num_pag = 1
    for par in paragrafos:
        if len(atual) + len(par) > 2600 and len(atual) > 400:
            paginas.append(f"--- PAGINA {num_pag} ---\n{atual}")
            num_pag += 1
            atual = f"## {titulo} (Seção {num_pag})\n\n{par}"
        else:
            atual = f"{atual}\n\n{par}"
    if atual:
        paginas.append(f"--- PAGINA {num_pag} ---\n{atual}")
    return "\n\n".join(paginas)


def main() -> None:
    with httpx.Client(headers={"User-Agent": "Mozilla/5.0 MaraDBV/2.0"}, follow_redirects=True, timeout=30.0) as client:
        for slug, titulo, url in PAGINAS_CARTOES:
            r = client.get(url)
            if r.status_code != 200:
                print(f"[FALHA {r.status_code}] {slug}")
                continue
            md_pag = html_para_markdown_paginado(r.text, titulo, url)
            dest_md = PASTA_MANUAIS / f"{slug}.md"
            dest_md.write_text(md_pag, encoding="utf-8")
            print(f"[OK CARTÃO] {dest_md.name} ({len(md_pag)} chars)")

            # Verifica se há PDF anexo na própria página da classe
            for m in re.findall(r'https?://[^\s"\'<>]+?\.pdf', r.text, flags=re.IGNORECASE):
                print(f"   PDF vinculado em {slug}: {m}")

        for url_rud in CANDIDATOS_RUD_PDF:
            try:
                rr = client.get(url_rud)
                if rr.status_code == 200 and rr.content.startswith(b"%PDF"):
                    dest_rud = PASTA_MANUAIS / "regulamento_uniformes_mda_dsa.pdf"
                    dest_rud.write_bytes(rr.content)
                    print(f"[OK RUD PDF] {dest_rud.name} ({len(rr.content)//1024} KB)")
                    break
            except Exception:
                pass

    # Deduplicação das OMDs: remove cópias duplicadas dsa_omd_001..019 quando já existe omd_001..019 descritivo,
    # e renomeia dsa_omd_003, 016, 018, 020, 021 e dsa_ne_001..003 para nomes descritivos canônicos!
    renomeacoes = {
        "dsa_omd_003-2013.pdf": "omd_003_2013_orientacao_oficial_dsa.pdf",
        "dsa_omd_016-2018.pdf": "omd_016_2018_orientacao_oficial_dsa.pdf",
        "dsa_omd_018-2022.pdf": "omd_018_2022_orientacao_oficial_dsa.pdf",
        "dsa_omd_020-2024.pdf": "omd_020_2024_nomes_de_clubes_desbravadores.pdf",
        "dsa_omd_021-2024.pdf": "omd_021_2024_atualizacao_livros_classes.pdf",
        "dsa_ne_001-2014.pdf": "rud_nota_explicativa_001_2014_uniforme.pdf",
        "dsa_ne_002-2014.pdf": "rud_nota_explicativa_002_2014_uniforme.pdf",
        "dsa_ne_003-2015.pdf": "rud_nota_explicativa_003_2015_uniforme.pdf",
    }
    for orig, novo in renomeacoes.items():
        p_orig = PASTA_MANUAIS / orig
        p_novo = PASTA_MANUAIS / novo
        if p_orig.exists():
            if p_novo.exists():
                p_orig.unlink()
            else:
                p_orig.rename(p_novo)
            print(f"[CANÔNICO] {orig} -> {novo}")

    for dup in sorted(PASTA_MANUAIS.glob("dsa_omd_*.pdf")):
        dup.unlink()
        print(f"[DEDUP REMOVIDO] {dup.name}")

    # Remove oficial_dsa_lideres.md (era lista institucional de departamentais, não requisitos) e oficial_dsa_classes_requisitos.md (índice)
    for aux in ("oficial_dsa_lideres.md", "oficial_dsa_classes_requisitos.md"):
        p_aux = PASTA_MANUAIS / aux
        if p_aux.exists():
            p_aux.unlink()


if __name__ == "__main__":
    main()
