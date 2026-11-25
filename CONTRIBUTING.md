# Guia de Contribuição — Mara (IA dos Desbravadores)

Obrigado pelo interesse em colaborar com a evolução da **Mara**! Este guia descreve o fluxo de desenvolvimento, os padrões técnicos e os requisitos legais para envio de contribuições.

---

## 1. Pré-requisito Obrigatório: Acordo de Licença de Contribuidor (CLA)

Todas as contribuições submetidas a este repositório são regidas pelo **[Acordo Individual de Licença de Contribuidor (`CLA.md`)](./CLA.md)**, outorgado ao autor e mantenedor titular **Edmilton Cabral Martins Junior** (selo *Infinito Soft*).

- Antes de abrir qualquer *Pull Request*, leia integralmente o arquivo [`CLA.md`](./CLA.md) e o arquivo [`NOTICE.md`](./NOTICE.md).
- *Pull Requests* sem a marcação expressa de aceite do CLA no formulário de revisão **não serão mesclados**.
- Nunca submeta código copiado de terceiros sem permissão compatível, nem inclua chaves de API, senhas ou dados pessoais.

---

## 2. Visão Rápida da Arquitetura

| Diretório | Tecnologia | Responsabilidade |
| :--- | :--- | :--- |
| `src/chatdbv/` | Python 3.12+ | Núcleo RAG híbrido (RRF + BM25/IDF + Embeddings 768d), extração `PyMuPDF`, *Zero-Token Guard*, catálogo da Biblioteca e exportador PDF editorial (`fpdf2`). |
| `src/mara_api/` | FastAPI + Uvicorn | API REST stateless, streaming SSE (`/api/chat/stream`), simulado estruturado JSON (`/api/quiz/generate`), autenticação `HttpOnly` HMAC e rate-limiting. |
| `web/` | Next.js 15 + React 19 + TS | Aplicativo Web estático (`output: 'export'`), Quiz interativo clicável, PWA Offline (*Modo Acampamento*) e manifesto Capacitor (`Android` / `iOS`). |
| `tests/` | Pytest + FastAPI TestClient | Suíte automatizada de unidade, busca híbrida, PDFs, SSE e segurança. |

---

## 3. Configurando o Ambiente de Desenvolvimento

### Pré-requisitos
- **Python 3.12+**
- **Node.js 22+ ou 24+** (`npm`)
- Uma chave de API gratuita do [Google AI Studio](https://aistudio.google.com/apikey) (`GEMINI_API_KEY`)

### Passo a passo

1. Copie `.env.example` para `.env` e informe sua `GEMINI_API_KEY`:
   ```bash
   cp .env.example .env
   ```
2. Crie o ambiente virtual Python, instale as dependências e indexe os manuais:
   ```bash
   python -m venv .venv
   # Linux/macOS: source .venv/bin/activate
   # Windows PowerShell: .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python scripts/ingest.py
   ```
3. Instale e compile o frontend PWA:
   ```bash
   cd web
   npm install
   npm run build
   cd ..
   ```
4. Suba o servidor unificado na porta `8501`:
   ```bash
   uvicorn --app-dir src mara_api.main:app --host 127.0.0.1 --port 8501 --reload
   ```

---

## 4. Padrões de Qualidade e Testes Obrigatórios

Antes de abrir um *Pull Request*, valide localmente:

1. **Testes Backend e Contrato da API:**
   ```bash
   pytest -v
   ```
2. **Tipagem Estrita TypeScript e Build Estático:**
   ```bash
   npm --prefix web run typecheck
   npm --prefix web run build
   ```
3. **Fidelidade Normativa DSA:** Qualquer ajuste em regras de uniformes, classes, especialidades ou administração deve ser estritamente fundamentado em manual oficial vigente ou **OMD** da Divisão Sul-Americana (citando documento e página na descrição do PR).
4. **Estilo de Commits:** Utilize *Conventional Commits* em português (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).
