"""Data tools the agent can call. Pure Python + pandas, no LLM here."""
import json, unicodedata
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import pandas as pd

DATA = Path(__file__).parent / "data"

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return s.lower().strip()

products = pd.read_csv(DATA / "products.csv")
categories = pd.read_csv(DATA / "categories.csv")
promotions = pd.read_csv(DATA / "promotions.csv")
orders = pd.read_csv(DATA / "orders.csv")
items = pd.read_csv(DATA / "order_items.csv")
customers = pd.read_csv(DATA / "customers.csv")

products = products.merge(categories[["category_id", "name"]].rename(columns={"name": "category"}), on="category_id")
active_promos = promotions[promotions.is_active == 1].drop_duplicates("product_id", keep="last")

STATUS_PT = {"active": "disponível", "discontinued": "descontinuado", "coming_soon": "em breve (pré-lançamento)"}
ORDER_STATUS_PT = {"pending": "aguardando pagamento", "confirmed": "pagamento confirmado, em separação",
                   "shipped": "enviado", "delivered": "entregue", "cancelled": "cancelado"}

def _money(x) -> float:
    return float(Decimal(str(x)).quantize(Decimal("0.01"), ROUND_HALF_UP))

def _product_view(r) -> dict:
    promo = active_promos[active_promos.product_id == r.product_id]
    d = {"product_id": int(r.product_id), "name": r["name"], "category": r.category,
         "price_brl": float(r.price_brl), "status": STATUS_PT.get(r.status, r.status),
         "in_stock": bool(r.stock_quantity > 0 and r.status == "active"),
         "stock_quantity": int(r.stock_quantity), "description": r.description,
         "specs": json.loads(r.specs)}
    if len(promo):
        p = promo.iloc[0]
        d["promotion"] = {"name": p.description, "discount_percent": int(p.discount_percent),
                          "promo_price_brl": _money(r.price_brl * (100 - p.discount_percent) / 100)}
    else:
        d["pix_price_brl"] = _money(r.price_brl * 0.95)  # 5% PIX, not cumulative with promos
    return d

def search_products(query: str = "", category: str = "", max_price: float | None = None,
                    min_price: float | None = None, only_in_stock: bool = True, limit: int = 30) -> list[dict]:
    """Search the catalog by free text (name/description/specs), category, and price range."""
    df = products
    if category:
        df = df[df.category.map(_norm).str.contains(_norm(category).rstrip("s"))]
    if query:
        terms = _norm(query).split()
        hay = (df["name"] + " " + df.description + " " + df.specs).map(_norm)
        df = df[hay.map(lambda h: all(t in h for t in terms))]
    if max_price is not None:
        df = df[df.price_brl <= max_price]
    if min_price is not None:
        df = df[df.price_brl >= min_price]
    if only_in_stock:
        df = df[(df.stock_quantity > 0) & (df.status == "active")]
    return [_product_view(r) for _, r in df.sort_values("price_brl").head(limit).iterrows()]

def get_order_status(order_id: int, customer_email_or_phone: str) -> dict:
    """Order status. Requires the customer's e-mail or phone to match (LGPD: never expose others' data)."""
    o = orders[orders.order_id == int(order_id)]
    if o.empty:
        return {"error": "Pedido não encontrado."}
    o = o.iloc[0]
    c = customers[customers.customer_id == o.customer_id].iloc[0]
    key = _norm(customer_email_or_phone)
    digits = "".join(ch for ch in key if ch.isdigit())
    ok = key == _norm(c.email) or (digits and digits == "".join(ch for ch in c.phone if ch.isdigit()))
    if not ok:
        return {"error": "Os dados informados não conferem com o pedido. Peça o e-mail ou telefone do cadastro."}
    its = items[items.order_id == o.order_id].merge(products[["product_id", "name"]], on="product_id")
    return {"order_id": int(o.order_id), "customer_first_name": c["name"].split()[0],
            "order_date": o.order_date, "status": ORDER_STATUS_PT.get(o.status, o.status),
            "total_brl": float(o.total_brl), "payment_method": o.payment_method,
            "tracking_code": None if pd.isna(o.tracking_code) else o.tracking_code,
            "estimated_delivery": None if pd.isna(o.estimated_delivery) else o.estimated_delivery,
            "notes": None if pd.isna(o.notes) else o.notes,
            "items": [{"name": r["name"], "quantity": int(r.quantity)} for _, r in its.iterrows()]}

def list_active_promotions() -> list[dict]:
    """All promotions currently active (is_active = 1)."""
    df = products[products.product_id.isin(active_promos.product_id)]
    return [_product_view(r) for _, r in df.iterrows()]

TOOLS = {"search_products": search_products, "get_order_status": get_order_status,
         "list_active_promotions": list_active_promotions}

TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "search_products",
        "description": "Busca instrumentos no catálogo (preço, estoque, promoção ativa, specs). Use sempre antes de falar de preço ou disponibilidade.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Palavras do nome/descrição, ex.: 'takamine gd20', 'nylon', 'yamaha'"},
            "category": {"type": "string", "description": "Guitarras, Baixos, Baterias, Teclados, Violões, Ukuleles..."},
            "max_price": {"type": "number"}, "min_price": {"type": "number"},
            "only_in_stock": {"type": "boolean", "description": "false para ver também esgotados/descontinuados"}}}}},
    {"type": "function", "function": {"name": "get_order_status",
        "description": "Status de um pedido. Exige número do pedido E e-mail ou telefone do cliente.",
        "parameters": {"type": "object", "properties": {
            "order_id": {"type": "integer"}, "customer_email_or_phone": {"type": "string"}},
            "required": ["order_id", "customer_email_or_phone"]}}},
    {"type": "function", "function": {"name": "list_active_promotions",
        "description": "Lista as promoções vigentes.", "parameters": {"type": "object", "properties": {}}}},
]
