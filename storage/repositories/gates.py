from storage.db import get_connection

# ================= DEFAULTS =================
DEFAULT_GATES = {
    "stripe_auth": {
        "enabled": 1,
        "max_cards": 200,
        "cost_per_card": 1,
    },
    "shopify_charge": {
        "enabled": 1,
        "max_cards": 200,
        "cost_per_card": 1,
    },
    "braintree_auth": {
        "enabled": 1,
        "max_cards": 200,
        "cost_per_card": 1,
    },
    "stripe_charge": {
        "enabled": 1,
        "max_cards": 200,
        "cost_per_card": 1,
    },
    "paypal_donation": {
        "enabled": 1,
        "max_cards": 200,
        "cost_per_card": 1,
    },
}

# ================= INIT =================
def init_gates():
    conn = get_connection()
    cur = conn.cursor()

    for gate, data in DEFAULT_GATES.items():
        cur.execute(
            """
            INSERT OR IGNORE INTO gate_state
            (gate_key, enabled, max_cards, cost_per_card)
            VALUES (?, ?, ?, ?)
            """,
            (
                gate,
                data["enabled"],
                data["max_cards"],
                data["cost_per_card"],
            )
        )

    conn.commit()
    conn.close()


# ================= ENABLE =================
def is_gate_enabled(gate_key: str) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT enabled FROM gate_state WHERE gate_key = ?",
        (gate_key,)
    )
    row = cur.fetchone()
    conn.close()
    return bool(row and row[0] == 1)


def set_enabled(gate_key: str, value: bool):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE gate_state SET enabled = ? WHERE gate_key = ?",
        (1 if value else 0, gate_key)
    )
    conn.commit()
    conn.close()


# ================= LIMIT =================
def get_limit(gate_key: str) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT max_cards FROM gate_state WHERE gate_key = ?",
        (gate_key,)
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0


def set_limit(gate_key: str, value: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE gate_state SET max_cards = ? WHERE gate_key = ?",
        (value, gate_key)
    )
    conn.commit()
    conn.close()


# ================= COST =================
def get_cost(gate_key: str) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT cost_per_card FROM gate_state WHERE gate_key = ?",
        (gate_key,)
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0


def set_cost(gate_key: str, value: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE gate_state SET cost_per_card = ? WHERE gate_key = ?",
        (value, gate_key)
    )
    conn.commit()
    conn.close()


# ================= ALIAS (Backward Compatibility) =================
def is_enabled(gate_key: str) -> bool:
    return is_gate_enabled(gate_key)
