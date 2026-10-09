UNKNOWN_COMUNA = "Comuna sin identificar"

ENGINE_FIELDS = {
    "anomalias": {"product": "product", "price": "unit_price_clp_gross", "basis": "bruto"},
    "convenio_marco": {"product": "oc_text", "price": "unit_price_clp_net", "basis": "neto"},
    "precio_pares": {"product": "product", "price": "unit_price_clp_gross", "basis": "bruto"},
}


def usable_comuna(value) -> str:
    text = str(value or "").strip()
    if not text or not any(ch.isalpha() for ch in text):
        return UNKNOWN_COMUNA
    return text


def public_row(engine: str, lead: dict, decision: dict | None) -> dict:
    fields = ENGINE_FIELDS[engine]
    row = {
        "id": lead["id"],
        "engine": engine,
        "status": "en_revision",
        "comuna": usable_comuna(lead.get("comuna")),
        "product": lead.get(fields["product"]),
        "quantity": lead.get("quantity"),
        "price_paid_clp": lead.get(fields["price"]),
        "price_basis": fields["basis"],
        "oc_id": lead.get("oc_id"),
        "correlativo": lead.get("correlativo"),
        "oc_url": lead.get("oc_url"),
        "captured_at": lead.get("captured_at"),
    }
    if decision and decision.get("decision") == "dismiss":
        row["status"] = "descartado"
        row["review_note"] = decision.get("note")
        row["reviewed_at"] = decision.get("reviewed_at")
    return row


def public_leads(queues: dict[str, list[dict]], decisions: dict, confirmed_ids: set[str]) -> list[dict]:
    rows = []
    for engine, items in queues.items():
        for lead in items:
            if lead.get("id") in confirmed_ids:
                continue
            rows.append(public_row(engine, lead, decisions.get(lead.get("id"))))
    rows.sort(key=lambda r: (r["engine"], r["comuna"], str(r["oc_id"]), r["correlativo"] or 0, r["id"]))
    return rows
