# Política de Segurança (SECURITY)

A segurança dos dados dos clubes e, sobretudo, a proteção de crianças e adolescentes (10 a 15 anos) que utilizam a **Mara** são prioridades absolutas para o mantenedor **Edmilton Cabral Martins Junior** (selo **Infinito Soft**).

---

## 1. Versões Suportadas

| Versão | Status de Suporte de Segurança |
| :--- | :--- |
| `2.0.x` (`FastAPI + Next.js PWA`) | Suportada ativamente |
| `1.x` (`PoC Streamlit`) | Descontinuada |

---

## 2. Como Reportar uma Vulnerabilidade de forma Responsável

**NÃO abra uma *Issue* pública no GitHub** para relatar falhas de segurança (como bypass de autenticação administrativa, injeção, XSS, exposição de credenciais ou bypass de filtros de proteção infantojuvenil / *prompt injection*).

Envie o relato de forma privada por um dos canais oficiais:
- **GitHub Private Vulnerability Reporting** (aba *Security > Report a vulnerability* deste repositório); ou
- Contato institucional através do portal oficial **[infinitosoft.com](https://infinitosoft.com)**.

Inclua no relato:
1. Descrição clara do vetor e impacto potencial;
2. Passos mínimos para reprodução (PoC);
3. Sugestão de mitigação (opcional).

Nos comprometemos a confirmar o recebimento em até **72 horas** e publicar a correção antes da divulgação pública.

---

## 3. Boas Práticas Obrigatórias para Auto-Hospedagem (*Self-Hosting*)

Caso você hospede sua própria instância da Mara (lembrando das obrigações da **Seção 13 da GNU AGPLv3** e do [`NOTICE.md`](./NOTICE.md)):

1. **Altere `ADMIN_PASSWORD` imediatamente:** Nunca suba para a internet mantendo o valor padrão de `.env.example`. Utilize uma senha longa e aleatória (`24+` caracteres).
2. **Use sempre HTTPS (TLS):** Os cookies de sessão administrativa (`HttpOnly`, `SameSite=Lax`) exigem transporte criptografado via reverse proxy (como Caddy, Nginx ou Cloudflare).
3. **Proteja o arquivo `.env`:** Restrinja permissões de leitura no servidor (`chmod 600 .env`) e nunca exponha chaves `GEMINI_API_KEY` no frontend.
4. **Preserve as travas de proteção infantojuvenil:** Mantenha intactas as instruções de escopo estrito e segurança etária em `src/chatdbv/rag.py`.
