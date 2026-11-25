# Mara v2.0 — IA dos Desbravadores (Infinito Soft · DSA)

Instrutora virtual oficial, geradora de simulados interativos e biblioteca de campo fundamentada nos manuais da **Divisão Sul-Americana (DSA)** para o Clube de Desbravadores.

Desenvolvida pela **Infinito Soft** com arquitetura **API-First Stateless (`FastAPI` + SSE)** + **Aplicativo Web / PWA Offline (`Next.js Static Export` + `React 19` + `TypeScript`)** e suporte nativo para lojas móveis via **Capacitor (`Android` / `iOS`)**.

---

## Arquitetura Mara v2.0

- **`src/chatdbv/` (Núcleo RAG & PDF Editorial):**
  - Busca híbrida (**Embeddings Gemini 768d + BM25/IDF + Reciprocal Rank Fusion**) com suporte transparente a `PostgreSQL + pgvector` ou `SQLite + NumPy`.
  - **Zero-Token Guard:** intercepta saudações e perguntas fora de escopo em `< 5 ms` sem consumir tokens da API Gemini.
  - **Simulado Estruturado JSON (`gerar_quiz_estruturado`):** gera questões de múltipla escolha tipadas com explicação fundamentada no manual e página.
  - **Motor Editorial PDF (`pdf_export.py`):** gera apostilas, cadernos de estudo e provas oficiais com linhas vetoriais de cabeçalho, bolhas de marcação `○`, tabelas multilinha proporcionais e **Folha do Instrutor (Gabarito Comentado)** separada automaticamente na Página 2.
- **`src/mara_api/` (API Stateless FastAPI + Uvicorn):**
  - Streaming em tempo real via **Server-Sent Events (`POST /api/chat/stream`)**.
  - Simulado interativo (`POST /api/quiz/generate`), Biblioteca Oficial (`GET /api/library`), exportação PDF (`/api/pdf/*`) e Painel da Diretoria protegido por cookie `HttpOnly` assinado (`HMAC-SHA256`) e rate-limiting em memória.
  - Serve diretamente o bundle estático compilado de `web/out` na porta `8501`.
- **`web/` (App Web, PWA "Modo Acampamento Offline" & Capacitor):**
  - Design editorial anti-slop alinhado ao Design System **Infinito Soft × Taste Skill** (`IBM Plex Sans` + `IBM Plex Mono`, superfície neutra clara, *equal edges*, alvos de toque `44px`).
  - **Composer Inline estilo Gemini** com retorno instantâneo de foco ao campo de texto.
  - **Modo Acampamento Offline (`sw.js` + `localStorage`):** mantém a Biblioteca do Conselheiro e os estudos recentes acessíveis no celular mesmo sem sinal de internet.
  - **`capacitor.config.ts`:** pronto para empacotar `.aab` (Google Play) e `.ipa` (App Store).

---

## Como Executar Localmente (Windows PowerShell)

### 1. Compilar o Aplicativo Web (primeira vez ou após alterar `web/`)

```powershell
cd web
npm install
npm run build
cd ..
```

### 2. Iniciar o Servidor Unificado (API + App PWA na porta `8501`)

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\uvicorn.exe mara_api.main:app --host 127.0.0.1 --port 8501
```

Acesse `http://localhost:8501` no navegador.

### 3. Executar a Suíte de Testes Automatizados

```powershell
.\.venv\Scripts\pytest.exe
```

---

## Build em Container Docker (Multi-Stage)

```powershell
docker build -t infinito-mara-app:2.0 .
docker run --rm -p 8501:8501 --env-file .env infinito-mara-app:2.0
```
