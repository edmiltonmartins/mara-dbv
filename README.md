# ⛺ Chat DBV — PoC RAG (Clube de Desbravadores - DSA)

Prova de Conceito (PoC) do **Chat DBV**, um consultor e repositório inteligente baseado em **RAG (Retrieval-Augmented Generation)** para o Clube de Desbravadores na Divisão Sul-Americana (DSA / Brasil).

Projetado desde o primeiro dia para validar a ingestão de manuais, a busca híbrida (**Semântica + Full-Text Search com Reciprocal Rank Fusion**) e a precisão das citações antes da migração para **Java (Spring Boot + Spring AI) + Angular**, compartilhando o mesmo esquema **PostgreSQL + `pgvector`**.

---

## 📂 Estrutura do Projeto

```text
chat-dbv/
├── app.py                      # Interface Web interativa (Streamlit) com Chat, Filtro, Upload e Modo Quiz
├── docker-compose.yml          # PostgreSQL 17 + pgvector pronto para subir
├── requirements.txt            # Dependências Python (google-genai >= 2.25, psycopg3, pgvector, pypdf)
├── .env.example                # Modelo de configuração de ambiente
├── sql/
│   └── 001_init.sql            # Esquema oficial PostgreSQL + pgvector (HNSW) + tsvector (PT-BR)
├── data/
│   └── manuais/                # Base de conhecimento inicial (Ideais, Uniformes, Classes, Administrativo)
├── scripts/
│   └── ingest.py               # CLI de ingestão e indexação idempotente (SHA-256)
├── src/chatdbv/
│   ├── config.py               # Leitura e validação de variáveis (.env)
│   ├── chunking.py             # Extração de PDF/MD preservando fronteiras de página
│   ├── embeddings.py           # Cliente gemini-embedding-001 (768d normalizado)
│   ├── db.py                   # Repositório Híbrido (PostgreSQL+pgvector e fallback SQLite+NumPy)
│   ├── ingestao.py             # Pipeline de ingestão com detecção automática de categoria
│   └── rag.py                  # Orquestrador RAG com Interactions API (gemini-3.8-flash + streaming)
└── tests/
    └── test_poc.py             # Testes automatizados (pytest)
```

---

## 🚀 Como Executar no Windows (PowerShell)

### 1. Configurar a Chave da API Gemini (`GEMINI_API_KEY`)

Obtenha uma chave gratuita no [Google AI Studio](https://aistudio.google.com/apikey).

No PowerShell, dentro da pasta `chat-dbv`, execute o comando abaixo (a digitação ficará oculta por segurança e salvará direto no arquivo `.env`):

```powershell
$sec = Read-Host "Digite sua GEMINI_API_KEY" -AsSecureString; $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)); Add-Content -Path "c:\Users\Edmilton Junior\Documents\GeminiFiles\chat-dbv\.env" -Value "GEMINI_API_KEY=$plain"; Write-Output "Chave salva em .env com sucesso!"
```

### 2. Escolher o Banco de Dados

A PoC funciona em **dois modos automáticos**:

- **Modo A — Zero-Config Local (Imediato):**
  Se `DATABASE_URL` estiver vazio no `.env`, o sistema usa automaticamente `data/chatdbv_local.sqlite` com busca vetorial via NumPy + RRF. Ideal para testar em 10 segundos sem instalar banco.
- **Modo B — PostgreSQL + `pgvector` (Docker, Supabase ou Neon):**
  Adicione no `.env`:
  ```env
  DATABASE_URL=postgresql://dbv:dbv_secret@localhost:5432/chatdbv
  ```
  *(Se tiver Docker instalado, basta rodar `docker compose up -d`).*

### 3. Iniciar a Interface Web do Chat DBV

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

Na primeira abertura (ou clicando em **"🔄 Indexar pasta data/manuais/"** na barra lateral), os 4 manuais de referência da DSA já incluídos serão indexados automaticamente. Você também pode enviar novos arquivos `.pdf`, `.md` ou `.txt` diretamente pelo painel lateral!

---

## 🔄 Como será a Migração para Java (Spring Boot) + Angular?

Como o esquema [`sql/001_init.sql`](./sql/001_init.sql) já cria as tabelas `manuais`, `chunks` (com `vector(768)` e `tsvector`) e `feedback` no PostgreSQL:

1. **Zero re-ingestão:** Todos os PDFs já processados e vetorizados na PoC permanecem prontos no PostgreSQL.
2. **Backend Java (Spring Boot 3.4+ / Spring AI):**
   - Conecta ao mesmo banco `chatdbv`.
   - Usa o mesmo modelo `gemini-embedding-001` (`outputDimensionality = 768`) e executa a mesma query híbrida RRF via `JdbcClient` / `NamedParameterJdbcTemplate`.
   - Expõe endpoints REST (`/api/manuais`, `/api/chat/stream` via `SseEmitter` / `Flux<String>`).
3. **Frontend Angular:**
   - Consome o endpoint SSE de streaming e o painel de upload de manuais.
