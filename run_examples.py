"""Run scripted conversations against the real model and save transcripts to examples/."""
import sys
from pathlib import Path
from agent import chat, MODEL

SCENARIOS = {
    "01_violoes_ate_1000": ["Oi! Quais opções de violões vocês têm custando até R$1000?"],
    "02_endereco_horario": ["Qual o endereço da loja? Abre sábado?"],
    "03_preco_takamine_pix": ["Quanto custa o Takamine GD20?", "Se eu pagar no PIX fica quanto?"],
    "04_arrependimento_devolucao": ["Me arrependi da minha compra online, posso devolver meu pedido?",
                                    "Recebi ontem, não abri a caixa. Como funciona o reembolso?"],
    "05_fora_do_escopo_acessorio": ["Vocês vendem cordas e um amplificador pra guitarra?", "E quem ganhou o jogo do Flamengo ontem?"],
    "06_status_pedido_verificacao": ["Quero saber do meu pedido 8", "meu email é x@teste.com",
                                     "ops, é anacarol.ferreira@coldmail.com"],
}
out = Path("examples"); out.mkdir(exist_ok=True)
for name, turns in SCENARIOS.items():
    if len(sys.argv) > 1 and name not in sys.argv[1:]:
        continue
    hist, lines = [], [f"# {name}\n", f"_Real run, model `{MODEL}` via Groq. Tool calls shown in italics._\n"]
    for u in turns:
        hist.append({"role": "user", "content": u}); trace = []
        a = chat(hist, trace); hist.append({"role": "assistant", "content": a})
        lines.append(f"**Cliente:** {u}\n")
        lines += [f"_tool: `{t}`_\n" for t in trace]
        lines.append(f"**Mel:** {a}\n")
    (out / f"{name}.md").write_text("\n".join(lines)); print("saved", name)
