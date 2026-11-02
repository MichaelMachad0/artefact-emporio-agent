"""Empório da Música customer-service agent: policies in the system prompt + function calling for live data."""
import json, os, sys
from datetime import datetime
from pathlib import Path
from openai import OpenAI
try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass
from tools import TOOLS, TOOL_SCHEMAS

POLICIES = (Path(__file__).parent / "data" / "politicas_da_loja.txt").read_text()
MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
client = OpenAI(  # any OpenAI-compatible provider (Groq by default)
    base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
    api_key=os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY"),
)

SYSTEM = f"""Você é a Mel, assistente virtual da Empório da Música (Campo Grande/MS), loja que vende SOMENTE instrumentos musicais.
Tom: informal mas profissional, como um amigo que entende de música. Respostas curtas, em português.
Regras:
- NUNCA invente preço, estoque, prazo ou status de pedido: use as ferramentas.
- Regras da loja (horário, pagamento, trocas, frete, garantia) vêm SOMENTE do manual abaixo.
- Promoção: mostre preço original, % e preço promocional. Desconto PIX (5%) não acumula com promoção.
- Produto esgotado/descontinuado: diga com transparência e sugira alternativas disponíveis.
- Pedido: peça número do pedido e o e-mail ou telefone do cadastro antes de consultar.
- Acessórios (cordas, cabos, palhetas, pedais, amplificadores, cases) e assuntos fora da loja: recuse com gentileza e volte ao foco.
- Reclamação ou dúvida fora do manual: acolha e diga que vai encaminhar a um atendente humano (retorno em até 24h úteis).
Data/hora atual: {{now}}.

=== MANUAL DA LOJA ===
{POLICIES}"""

def chat(history: list[dict], trace: list | None = None) -> str:
    msgs = [{"role": "system", "content": SYSTEM.replace("{now}", datetime.now().strftime("%A %d/%m/%Y %H:%M"))}] + history
    for _ in range(5):  # small ReAct-style loop
        r = client.chat.completions.create(model=MODEL, messages=msgs, tools=TOOL_SCHEMAS, temperature=0.2)
        m = r.choices[0].message
        if not m.tool_calls:
            return m.content
        msgs.append(m)
        for tc in m.tool_calls:
            try:
                out = TOOLS[tc.function.name](**json.loads(tc.function.arguments or "{}"))
            except Exception as e:
                out = {"error": str(e)}
            if trace is not None:
                trace.append(f"{tc.function.name}({tc.function.arguments})")
            if os.getenv("DEBUG"):
                print(f"  [tool] {tc.function.name}({tc.function.arguments})", file=sys.stderr)
            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(out, ensure_ascii=False)})
    return "Desculpe, tive um problema aqui. Vou chamar um atendente humano pra te ajudar."

if __name__ == "__main__":
    hist_file = Path("history.json")
    history = json.loads(hist_file.read_text()) if "--resume" in sys.argv and hist_file.exists() else []
    print("Mel (Empório da Música) — digite 'sair' para encerrar.")
    while (user := input("\nVocê: ").strip()).lower() not in {"sair", "exit"}:
        history.append({"role": "user", "content": user})
        answer = chat(history)
        history.append({"role": "assistant", "content": answer})
        hist_file.write_text(json.dumps(history, ensure_ascii=False, indent=1))
        print(f"\nMel: {answer}")
