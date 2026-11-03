# Empório da Música — Customer Service Agent (prototype)

A text-message agent ("Mel") for a fictional musical-instrument store. It answers store questions from the policy manual and checks live data (catalog, prices, stock, promotions, orders) by calling tools.

## How to run
```bash
git clone https://github.com/MichaelMachad0/artefact-emporio-agent && cd artefact-emporio-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # put your Groq key (free tier) in GROQ_API_KEY
python agent.py             # new conversation
python agent.py --resume    # continue the last conversation (history.json)
DEBUG=1 python agent.py     # print tool calls
python run_examples.py      # regenerate the transcripts in examples/
```
Config (env vars): `LLM_BASE_URL` (default `https://api.groq.com/openai/v1`), `LLM_MODEL` (default `openai/gpt-oss-120b`), `GROQ_API_KEY` or `LLM_API_KEY`. Any OpenAI-compatible provider works (OpenAI, Ollama at `http://localhost:11434/v1`, etc.).

## Example conversations (real runs, `examples/`)
| File | Scenario |
|---|---|
| `01_violoes_ate_1000.md` | catalog search: acoustic guitars up to R$1,000 (12 results) |
| `02_endereco_horario.md` | store address and Saturday hours (policy) |
| `03_preco_takamine_pix.md` | Takamine GD20 price + 5% PIX rule (no active promotion) |
| `04_arrependimento_devolucao.md` | regret return: 7-day rule, refund conditions |
| `05_fora_do_escopo_acessorio.md` | accessories refused + off-topic question declined |
| `06_status_pedido_verificacao.md` | order status: wrong e-mail rejected, then verified |

## Architecture (kept simple on purpose)
```
user ──> LLM (system prompt = persona + rules + full policy manual)
            │  function calling (max 5 rounds)
            ├─ search_products(query, category, min/max price, only_in_stock)
            ├─ get_order_status(order_id, customer_email_or_phone)
            └─ list_active_promotions()
```
- **Policies in the prompt, no RAG.** The manual is ~8 pages (~4k tokens). It fits in the context window, so a vector database would add complexity and retrieval errors without real benefit. With a much larger manual I would add RAG.
- **Structured data via function calling, not text-to-SQL.** The tables are small and the questions are predictable (price, stock, order). Fixed tools are safer (no arbitrary queries, no data leaks), easier to test, and the business rules live in code, not in the model.
- **Business rules in code:** active promotion price; 5% PIX discount only when there is no promotion (the policy says they don't stack); out-of-stock/discontinued/coming-soon flags.
- **Privacy (LGPD):** order lookups require the order number **and** the customer's e-mail or phone. The agent never lists customer data.
- **Model:** `openai/gpt-oss-120b` on Groq: free tier, fast, reliable tool calling and good Portuguese. I first tried `llama-3.3-70b-versatile`, but it was not available on my Groq account. Swappable by env vars.
- **Interface:** CLI. The focus is the agent working correctly.
- **History:** kept in memory for the conversation and saved to `history.json` (`--resume`), which is what a WhatsApp-style chat would need.

## Data treatment and assumptions
- The CSVs are loaded with pandas; products are joined with categories; only `is_active = 1` promotions are used (duplicates per product: last one wins).
- Inconsistencies found (documented, not "fixed" silently):
  - Two WhatsApp numbers in the manual: (67) 3341-4444 (company data) and (67) 3321-4500 (section 7). The agent gives the company data number. **Assumption.**
  - E-mail written as `contato@empóriodamusica.com.br` (with accent) in one place; I use the version without accent.
  - Order 20 total (R$ 1,400) ≠ sum of items (R$ 1,488); order 3 has 2 × product 130 (R$ 3,498) but total R$ 3,450, and product 130 is `coming_soon`. The agent reports the order total as recorded and does not recompute.
  - Order dates are in 2025–2026, so "7 days for regret" is checked against the delivery date when the customer asks.
- Accessories (strings, cables, picks, pedals, amps, cases) are out of scope by policy and politely refused.

## Known limitations / with more time
- In the regret-return example the model added a step not in the manual ("we send a label or a courier picks it up"). The manual does not describe how the return pickup works; a stricter prompt or a fixed answer template would avoid this kind of small invention.
- Free-tier rate limits: the full policy manual goes in every request, so each call uses ~5k tokens. Fine for a prototype; with RAG or caching it would be cheaper.
- Bugs found while testing: the product search had a default limit of 10 and hid 2 of the 12 guitars under R$1,000 (fixed); the model sometimes recalculated PIX prices itself with rounding errors (fixed by rounding in code and telling it to use tool values); it offered human handoff for a football question (fixed in the prompt).
- No automated eval set yet: I would create ~30 test questions with expected tool calls and answers and run them in CI.
- Shipping cost to other cities is not computable (the policy depends on CEP/weight) — the agent says a quote is needed.
- Human handoff is only a message; a real system would open a ticket.
- Business-hours awareness relies on the current date in the prompt.
- A WhatsApp channel (webhook API) and a small web UI.

## Use of AI coding assistants
I work as an AI manager. I have been studying programming since 2024, and I build my own multi-tenant SaaS for schools (GIA) by turning my ideas into clear prompts (goal, rules, constraints) for AI coding assistants such as Claude Code, Cursor, Codex and ChatGPT, which write most of the code. My job is to orchestrate them: I split the work across specialized AI agents (architecture, implementation, QA, security, database), require evidence before accepting a change (tests, commit hashes, real runs), and keep strict safety rules such as AI features that stay off unless explicitly enabled and no access to production without my approval. I used the same workflow here: I defined what the agent must do and must never do (LGPD check before showing an order, prices only from tools, no invented policies), ran the real conversations, read every transcript and asked for fixes when something was wrong, which is why the commit history shows the bugs found and fixed.
