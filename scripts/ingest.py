"""Script de linha de comando para indexar manuais da pasta data/manuais/."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from chatdbv.config import Config
from chatdbv.db import criar_repositorio
from chatdbv.embeddings import Embedder
from chatdbv.ingestao import ingerir_pasta


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingestão de manuais do Chat DBV")
    parser.add_argument(
        "--forcar",
        action="store_true",
        help="Reindexa todos os arquivos mesmo que o hash SHA-256 não tenha mudado.",
    )
    args = parser.parse_args()

    cfg = Config.carregar()
    if not cfg.gemini_api_key:
        print(
            "ERRO: GEMINI_API_KEY não configurada no arquivo .env.\n"
            "Defina GEMINI_API_KEY no arquivo chat-dbv/.env antes de rodar a ingestão.",
            file=sys.stderr,
        )
        return 1

    repo = criar_repositorio(cfg)
    embedder = Embedder(cfg)

    print(f"Backend de banco selecionado: {repo.nome_backend}")
    print(f"Lendo manuais em: {cfg.pasta_manuais}")

    resultados = ingerir_pasta(cfg.pasta_manuais, repo, embedder, forcar=args.forcar)
    if not resultados:
        print("Nenhum arquivo .pdf, .md ou .txt encontrado em data/manuais/.")
        return 0

    for r in resultados:
        if r.ignorado_por_cache:
            print(f"  [CACHE] {r.arquivo} -> sem alterações (já indexado)")
        else:
            print(
                f"  [OK]    {r.arquivo} -> '{r.titulo}' | "
                f"Categoria: {r.categoria} | {r.paginas} pág(s) | {r.chunks} chunks"
            )

    manuais = repo.listar_manuais()
    total_chunks = sum(m.total_chunks for m in manuais)
    print(f"\nResumo da Base: {len(manuais)} manuais indexados ({total_chunks} chunks no total).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
