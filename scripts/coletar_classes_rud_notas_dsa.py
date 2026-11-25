# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 Edmilton Cabral Martins Junior <junior.edmilton@gmail.com>

"""Inspeciona e coleta os PDFs e requisitos oficiais de Classes, Liderança,
Notas Explicativas do RUD e OMDs 020/021 diretamente das páginas oficiais da DSA."""
from __future__ import annotations

import html as _html
import re
import time
from pathlib import Path
import httpx

RAIZ = Path(__file__).resolve().parents[1]
PASTA_MANUAIS = RAIZ / "data" / "manuais"

PAGINAS_OFICIAIS = [
    ("classes_requisitos", "https://www.adventistas.org/pt/desbravadores/classes/classes-requisitos/"),
    ("classes_home", "https://www.adventistas.org/pt/desbravadores/classes/"),
    ("lideres", "https://www.adventistas.org/pt/desbravadores/lideres/"),
    ("notas_explicativas_rud", "https://www.adventistas.org/pt/desbravadores/notas-explicativas/"),
    ("omds_lista", "https://www.adventistas.org/pt/desbravadores/orientacoes-do-ministerio-de-desbravadores/"),
    ("simbolos", "https://www.adventistas.org/pt/desbravadores/simbolos/"),
    ("fundando_clube", "https://www.adventistas.org/pt/desbravadores/fundando-um-clube-de-desbravadores/"),
    ("omd_020_page", "https://downloads.adventistas.org/pt/desbravadores/documentos-oficiais/omd-020-2024-nomes-de-clubes-de-desbravadores/"),
    ("omd_021_page", "https://downloads.adventistas.org/pt/desbravadores/manuais-e-guias/omd021-2024/"),
]


def limpar_html_para_markdown(raw_html: str) -> str:
    # Extrai apenas <article> ou <main> se existir
    m = re.search(r"<article\b[^>]*>(.*?)</article>", raw_html, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        m = re.search(r"<main\b[^>]*>(.*?)</main>", raw_html, flags=re.DOTALL | re.IGNORECASE)
    corpo = m.group(1) if m else raw_html
    corpo = re.sub(r"<(script|style|nav|footer|header|svg|noscript)\b[^>]*>.*?</\1>", "", corpo, flags=re.DOTALL | re.IGNORECASE)
    corpo = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n\n# \1\n\n", corpo, flags=re.DOTALL | re.IGNORECASE)
    corpo = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n\n## \1\n\n", corpo, flags=re.DOTALL | re.IGNORECASE)
    corpo = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n\n### \1\n\n", corpo, flags=re.DOTALL | re.IGNORECASE)
    corpo = re.sub(r"<li[^>]*>(.*?)</li>", r"\n- \1", corpo, flags=re.DOTALL | re.IGNORECASE)
    corpo = re.sub(r"<br\s*/?>", "\n", corpo, flags=re.IGNORECASE)
    corpo = re.sub(r"</p>", "\n\n", corpo, flags=re.IGNORECASE)
    corpo = re.sub(r"<[^>]+>", " ", corpo)
    corpo = _html.unescape(corpo)
    corpo = re.sub(r"[ \t]+", " ", corpo)
    corpo = re.sub(r"\n{3,}", "\n\n", corpo)
    return corpo.strip()


def main() -> None:
    headers = {"User-Agent": "Mozilla/5.0 MaraDBV/2.0"}
    todos_pdfs_descobertos: list[str] = []

    with httpx.Client(headers=headers, follow_redirects=True, timeout=30.0) as client:
        for chave, url in PAGINAS_OFICIAIS:
            r = client.get(url)
            print(f"\n[{r.status_code}] {chave} -> {url}")
            if r.status_code != 200:
                continue
            # Procura qualquer URL de arquivo (pdf, doc, zip, backblaze, deptos, files)
            urls = re.findall(r'https?://[^\s"\'<>]+', r.text)
            arqs = []
            for u in urls:
                u_clean = _html.unescape(u).rstrip(").,;\"'")
                low = u_clean.lower()
                if any(ext in low for ext in (".pdf", ".docx", ".zip", "backblazeb2.com/file/", "deptos.adventistas.org/", "files.adventistas.org/")):
                    if not any(ign in low for ign in (".css", ".js", ".png", ".jpg", ".svg", ".woff", "favicon")):
                        if u_clean not in arqs:
                            arqs.append(u_clean)
            for a in arqs[:30]:
                print("   ARQ:", a)
                if a not in todos_pdfs_descobertos:
                    todos_pdfs_descobertos.append(a)

            txt = limpar_html_para_markdown(r.text)
            print(f"   Texto útil extraído: {len(txt)} chars | Prévia: {txt[:220]!r}")

            # Salva páginas institucionais densas como Markdown oficial complementar
            if chave in ("notas_explicativas_rud", "simbolos", "fundando_clube", "classes_requisitos", "lideres") and len(txt) > 500:
                arq_md = PASTA_MANUAIS / f"oficial_dsa_{chave}.md"
                arq_md.write_text(f"--- PAGINA 1 ---\n# Fonte Oficial DSA: {chave}\nURL: {url}\n\n{txt}\n", encoding="utf-8")
                print(f"   [SALVO MD] {arq_md.name} ({len(txt)} chars)")

        # Baixa PDFs importantes descobertos nas páginas de Classes, Líderes, RUD e OMDs!
        print(f"\n=== Baixando PDFs oficiais descobertos ({len(todos_pdfs_descobertos)} candidatos) ===")
        for u_pdf in todos_pdfs_descobertos:
            if not u_pdf.lower().split("?")[0].endswith(".pdf"):
                continue
            nome_orig = Path(u_pdf.split("?")[0]).name
            nome_limpo = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", httpx.URL(u_pdf).path.split("/")[-1])
            if not nome_limpo.lower().endswith(".pdf"):
                nome_limpo += ".pdf"
            # Evita baixar de novo se já temos equivalente
            destino = PASTA_MANUAIS / f"dsa_{nome_limpo.lower()}"
            if destino.exists():
                continue
            try:
                rp = client.get(u_pdf)
                if rp.status_code == 200 and rp.content.startswith(b"%PDF") and len(rp.content) <= 25 * 1024 * 1024:
                    destino.write_bytes(rp.content)
                    print(f"   [BAIXADO PDF] {destino.name} ({len(rp.content) // 1024} KB)")
                time.sleep(0.2)
            except Exception as e:
                print(f"   [FALHA] {u_pdf}: {e}")


if __name__ == "__main__":
    main()
