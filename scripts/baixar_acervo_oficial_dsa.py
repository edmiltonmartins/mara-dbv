"""Coletor oficial de documentos públicos da Divisão Sul-Americana (DSA)
para enriquecimento da base RAG da Mara v2.0.

Baixa apenas documentos normativos e curriculares oficiais (.pdf) de
downloads.adventistas.org / files.adventistas.org / adventistas.org/pt/desbravadores.
"""
from __future__ import annotations

import io
import re
import time
import zipfile
from pathlib import Path
import httpx

RAIZ = Path(__file__).resolve().parents[1]
PASTA_MANUAIS = RAIZ / "data" / "manuais"

ITENS_PORTAL_DOWNLOADS: list[tuple[str, str]] = [
    # Núcleo P0 — Manuais e Diretrizes Vigentes
    (
        "manual_administrativo_clube_desbravadores_dsa",
        "https://downloads.adventistas.org/pt/desbravadores/manuais-e-guias/pdf-manual-administrativo-do-clube-de-desbravadores/",
    ),
    (
        "orientacoes_desbravadores_aventureiros_2026",
        "https://downloads.adventistas.org/pt/aventureiros/manuais-e-guias/orientacoes-para-desbravadores-e-aventureiros-2026/",
    ),
    (
        "map_espaco_da_calma_mda",
        "https://downloads.adventistas.org/pt/aventureiros/manuais-e-guias/map-espaco-da-calma/",
    ),
    (
        "recomendacoes_lider_master_avancado",
        "https://downloads.adventistas.org/pt/desbravadores/manuais-e-guias/recomendacoes-lider-master-avancado/",
    ),
    # P0 — Série Completa de OMDs (Orientações do Ministério de Desbravadores)
    (
        "omd_001_cartao_de_classe",
        "https://downloads.adventistas.org/pt/desbravadores/documentos-oficiais/cartao-classe-orientacao-ministerio-desbravadores/",
    ),
    (
        "omd_002_cartao_de_lideranca",
        "https://downloads.adventistas.org/pt/desbravadores/documentos-oficiais/cartao-lideranca-orientacao-ministerio-desbravadores/",
    ),
    (
        "omd_004_desfile_no_sabado",
        "https://downloads.adventistas.org/pt/desbravadores/documentos-oficiais/omd-004-desfile-no-sabado/",
    ),
    (
        "omd_005_classe_companheiro",
        "https://downloads.adventistas.org/pt/desbravadores/documentos-oficiais/omd-005-classe-companheiro/",
    ),
    (
        "omd_006_validade_cartoes_lideranca",
        "https://downloads.adventistas.org/pt/desbravadores/documentos-oficiais/omd-006-validade-cartoes-de-lideranca/",
    ),
    (
        "omd_007_cartoes_amigo_e_pesquisador",
        "https://downloads.adventistas.org/pt/desbravadores/manuais-e-guias/omd-007-cartoes-amigo-e-pesquisador/",
    ),
    (
        "omd_008_uniforme_de_departamental",
        "https://downloads.adventistas.org/pt/desbravadores/manuais-e-guias/omd-008-uniforme-de-departamental/",
    ),
    (
        "omd_009_uniforme_de_casamento",
        "https://downloads.adventistas.org/pt/desbravadores/manuais-e-guias/omd-009-uniforme-de-casamento/",
    ),
    (
        "omd_010_retificacao_manual_administrativo",
        "https://downloads.adventistas.org/pt/desbravadores/documentos-oficiais/omd-010-retificacao-no-manual-administrativo/",
    ),
    (
        "omd_011_idades",
        "https://downloads.adventistas.org/pt/desbravadores/manuais-e-guias/omd-011-idades/",
    ),
    (
        "omd_012_correcao_comando_ordem_unida",
        "https://downloads.adventistas.org/pt/desbravadores/manuais-e-guias/omd-012-correcao-de-comando-em-ordem-unida/",
    ),
    (
        "omd_013_complementacao_cartao_lideranca",
        "https://downloads.adventistas.org/pt/desbravadores/manuais-e-guias/omd-013-complementacao-em-cartao-de-lideranca/",
    ),
    (
        "omd_014_cartao_lideranca_regionais",
        "https://downloads.adventistas.org/pt/desbravadores/manuais-e-guias/omd-014-cartao-de-lideranca-regionais/",
    ),
    (
        "omd_015_alteracoes_cartao_classe_amigo",
        "https://downloads.adventistas.org/pt/desbravadores/manuais-e-guias/omd-015-alteracoes-cartao-de-classe-amigo/",
    ),
    (
        "omd_017_especialidade_biosseguranca",
        "https://downloads.adventistas.org/pt/desbravadores/outros/omd-17-especialidade-de-biosseguranca/",
    ),
    (
        "omd_019_2023_coordenador_do_sgc",
        "https://downloads.adventistas.org/pt/desbravadores/documentos-oficiais/omd-019-2023-coordenador-do-sgc/",
    ),
    (
        "omd_020_2024_nomes_de_clubes",
        "https://downloads.adventistas.org/pt/desbravadores/documentos-oficiais/omd-020-2024-nomes-de-clubes-de-desbravadores/",
    ),
    (
        "omd_021_2024_atualizacao_livros_classes",
        "https://downloads.adventistas.org/pt/desbravadores/manuais-e-guias/omd021-2024/",
    ),
    # P1 — VI Campori Sul-Americano DSA 2027
    (
        "campori_dsa_2027_manual_orientacoes",
        "https://downloads.adventistas.org/pt/desbravadores/manuais-e-guias/manual-de-orientacoes-vi-campori-dsa-2027/",
    ),
    (
        "campori_dsa_2027_manual_eventos",
        "https://downloads.adventistas.org/pt/desbravadores/manuais-e-guias/manual-de-eventos-do-vi-campori-dsa-2027/",
    ),
    (
        "campori_dsa_2027_boletim_01_2026",
        "https://downloads.adventistas.org/pt/desbravadores/manuais-e-guias/boletim-oficial-no-01-2026-vi-campori-dsa-2027/",
    ),
    (
        "campori_dsa_2027_boletim_02_2026",
        "https://downloads.adventistas.org/pt/desbravadores/manuais-e-guias/boletim-oficial-no-02-2026-vi-campori-dsa-2027/",
    ),
]

PAGINAS_INSTITUCIONAIS_EXTRAS = [
    "https://www.adventistas.org/pt/desbravadores/classes/",
    "https://www.adventistas.org/pt/desbravadores/downloads/",
    "https://www.adventistas.org/pt/desbravadores/manuais/",
    "https://www.adventistas.org/pt/desbravadores/sobre-nos/regulamento-de-uniforme/",
]


def _extrair_urls_arquivos(html: str) -> list[str]:
    padrao = re.compile(
        r'https?://[^\s"\'<>]+?\.(?:pdf|zip)(?:\?[^\s"\'<>]*)?',
        flags=re.IGNORECASE,
    )
    encontrados = []
    for m in padrao.findall(html):
        limpo = m.replace("&amp;", "&")
        if limpo not in encontrados:
            encontrados.append(limpo)
    return encontrados


def main() -> None:
    PASTA_MANUAIS.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MaraDBV-RAG-Indexer/2.0",
        "Accept": "text/html,application/pdf,*/*;q=0.8",
    }

    baixados = 0
    falhas = 0

    with httpx.Client(headers=headers, follow_redirects=True, timeout=30.0) as client:
        for slug_base, url_pagina in ITENS_PORTAL_DOWNLOADS:
            destino_pdf = PASTA_MANUAIS / f"{slug_base}.pdf"
            if destino_pdf.exists() and destino_pdf.stat().st_size > 1024:
                print(f"[CACHE] {destino_pdf.name} ({destino_pdf.stat().st_size // 1024} KB)")
                baixados += 1
                continue

            try:
                r = client.get(url_pagina)
                if r.status_code != 200:
                    print(f"[AVISO] HTTP {r.status_code} em {url_pagina}")
                    falhas += 1
                    continue

                html = r.text
                if "g-recaptcha" in html and "files.adventistas.org" not in html and ".pdf" not in html.lower():
                    print(f"[BLOQUEADO POR CAPTCHA - PULADO] {url_pagina}")
                    falhas += 1
                    continue

                links = _extrair_urls_arquivos(html)
                links_pdf = [u for u in links if ".pdf" in u.lower()]
                links_zip = [u for u in links if ".zip" in u.lower()]

                salvou = False
                for link_pdf in links_pdf:
                    rp = client.get(link_pdf)
                    if rp.status_code == 200 and rp.content.startswith(b"%PDF"):
                        # Ignora PDFs gigantes (> 25 MB, geralmente artes de gráfica vetorizadas sem texto)
                        if len(rp.content) > 25 * 1024 * 1024:
                            print(f"[PULADO >25MB] {slug_base}: {len(rp.content) // (1024*1024)} MB")
                            continue
                        destino_pdf.write_bytes(rp.content)
                        print(f"[OK PDF] {destino_pdf.name} ({len(rp.content) // 1024} KB) <- {link_pdf}")
                        baixados += 1
                        salvou = True
                        break

                if not salvou and links_zip:
                    for link_zip in links_zip:
                        rz = client.get(link_zip)
                        if rz.status_code == 200 and len(rz.content) < 30 * 1024 * 1024:
                            try:
                                with zipfile.ZipFile(io.BytesIO(rz.content)) as zf:
                                    pdfs_internos = [n for n in zf.namelist() if n.lower().endswith(".pdf") and not n.startswith("__MACOSX")]
                                    if pdfs_internos:
                                        dados_pdf = zf.read(pdfs_internos[0])
                                        if dados_pdf.startswith(b"%PDF"):
                                            destino_pdf.write_bytes(dados_pdf)
                                            print(f"[OK ZIP->PDF] {destino_pdf.name} ({len(dados_pdf) // 1024} KB)")
                                            baixados += 1
                                            salvou = True
                                            break
                            except Exception:
                                pass

                if not salvou:
                    print(f"[SEM PDF DIRETO] {slug_base} (links achados: {links[:3]})")
                time.sleep(0.25)
            except Exception as exc:
                print(f"[ERRO] {slug_base}: {exc}")
                falhas += 1

        print("\n--- Inspecionando páginas institucionais extras (adventistas.org/pt/desbravadores/) ---")
        for url_extra in PAGINAS_INSTITUCIONAIS_EXTRAS:
            try:
                rext = client.get(url_extra)
                print(f"[EXTRA {rext.status_code}] {url_extra}")
                if rext.status_code == 200:
                    achados = _extrair_urls_arquivos(rext.text)
                    for a in achados[:25]:
                        print("   ->", a)
            except Exception as exc:
                print(f"[EXTRA ERRO] {url_extra}: {exc}")

    print(f"\nResumo da coleta: {baixados} PDFs salvos em data/manuais/ | {falhas} avisos.")


if __name__ == "__main__":
    main()
