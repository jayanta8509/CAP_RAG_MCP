from typing import Any, Dict, List, Optional, Union
from mcp.server.fastmcp import FastMCP

from db import fetch_one, fetch_all, build_ilike_pattern

mcp = FastMCP("DB_Customer_Chatbot")

BASE_URL = "https://adminapi.showmecustomapparel.com"


#utilities
def _safe_str(v: Any) -> str:
    return "" if v is None else str(v)


def _full_url(path_or_url: Optional[str]) -> Optional[str]:
    """
    If DB has a relative path like "/uploads/x.jpg", return BASE_URL + path.
    If DB already stores full URL (http/https), return as-is.
    """
    if not path_or_url:
        return None
    s = str(path_or_url).strip()
    if s.startswith("http://") or s.startswith("https://"):
        return s
    if not s.startswith("/"):
        s = "/" + s
    return BASE_URL + s


def _normalize_hat_name(name: str) -> str:
    return " ".join(name.strip().split())


async def _find_hat_by_name_exact_or_like(hat_name: str) -> Optional[Dict[str, Any]]:
    """
    Try exact-ish match first; if not found, fallback to ILIKE.
    """
    hn = _normalize_hat_name(hat_name)
    row = await fetch_one(
        """
        SELECT id, name, description, min_qty, size_chart_json
        FROM hats
        WHERE is_active = 1 AND LOWER(name) = LOWER($1)
        LIMIT 1
        """,
        hn,
    )
    if row:
        return row

    pat = build_ilike_pattern(hn)
    row = await fetch_one(
        """
        SELECT id, name, description, min_qty, size_chart_json
        FROM hats
        WHERE is_active = 1
          AND (name ILIKE $1 OR COALESCE(description,'') ILIKE $1)
        ORDER BY
          CASE WHEN name ILIKE $1 THEN 0 ELSE 1 END,
          id ASC
        LIMIT 1
        """,
        pat,
    )
    return row


async def _get_hat_style_images(hat_id: int) -> List[Dict[str, Any]]:
    rows = await fetch_all(
        """
        SELECT image_url, image_type, alt_text, sort_order, is_primary
        FROM hat_images
        WHERE hat_style_id = $1
          AND is_active = 1
        ORDER BY is_primary DESC, sort_order ASC NULLS LAST
        """,
        hat_id,
    )
    for r in rows:
        r["image_url"] = _full_url(r.get("image_url"))
    return rows


async def _get_color_images(hat_color_id: int) -> List[Dict[str, Any]]:
    rows = await fetch_all(
        """
        SELECT image_url, image_type, alt_text, sort_order, is_primary
        FROM hat_images
        WHERE hat_color_id = $1
          AND is_active = 1
        ORDER BY is_primary DESC, sort_order ASC NULLS LAST
        """,
        hat_color_id,
    )
    for r in rows:
        r["image_url"] = _full_url(r.get("image_url"))
    return rows


async def _get_sizes_for_hat(hat_id: int) -> List[Dict[str, Any]]:
    """
    Returns sizes grouped by color name (no IDs exposed).
    """
    rows = await fetch_all(
        """
        SELECT
          hc.name as color_name,
          hsv.size_label,
          hsv.variant_name
        FROM hat_colors hc
        JOIN hat_size_variants hsv
          ON hsv.hat_color_id = hc.id
         AND hsv.is_active = 1
        WHERE hc.hat_style_id = $1
          AND hc.is_active = 1
        ORDER BY hc.name ASC, hsv.size_label ASC, hsv.variant_name ASC
        """,
        hat_id,
    )

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        c = r["color_name"]
        grouped.setdefault(c, []).append(
            {
                "size_label": r["size_label"],
                "variant_name": r["variant_name"],
            }
        )

    out = []
    for color_name in sorted(grouped.keys()):
        out.append({"color_name": color_name, "sizes": grouped[color_name]})
    return out


async def _get_colors_for_hat(hat_id: int) -> List[Dict[str, Any]]:
    rows = await fetch_all(
        """
        SELECT id, name, color_code, primary_image_url
        FROM hat_colors
        WHERE hat_style_id = $1
          AND is_active = 1
        ORDER BY name ASC
        """,
        hat_id,
    )

    out = []
    for r in rows:
        color_id = int(r["id"])
        color_images = await _get_color_images(color_id)

        out.append(
            {
                "color_name": r["name"],
                "color_code": r.get("color_code"),
                "primary_image_url": _full_url(r.get("primary_image_url")),
                "color_images": color_images,
            }
        )
    return out


async def _get_decoration_types() -> List[Dict[str, Any]]:
    rows = await fetch_all(
        """
        SELECT name, code, description
        FROM primary_decoration_types
        WHERE is_active = 1
        ORDER BY id ASC
        """
    )
    # no internal ids
    return [
        {"name": r["name"], "code": r["code"], "description": r.get("description")}
        for r in rows
    ]


async def _get_style_price_tiers_for_hat(hat_id: int) -> Dict[str, Any]:
    """
    Returns tiers grouped by decoration type CODE (e.g., EMBROIDERY / LEATHER_PATCH).
    """
    rows = await fetch_all(
        """
        SELECT
          pdt.name as decoration_name,
          pdt.code as decoration_code,
          sdt.min_qty,
          sdt.max_qty,
          sdt.display_label,
          sdt.unit_price
        FROM style_decoration_price_tiers sdt
        JOIN primary_decoration_types pdt
          ON pdt.id = sdt.decoration_type_id
        WHERE sdt.hat_id = $1
          AND sdt.is_active = 1
          AND pdt.is_active = 1
        ORDER BY pdt.id ASC, sdt.min_qty ASC
        """,
        hat_id,
    )

    grouped: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        code = r["decoration_code"]
        grouped.setdefault(
            code,
            {
                "decoration_name": r["decoration_name"],
                "decoration_code": code,
                "tiers": [],
            },
        )
        grouped[code]["tiers"].append(
            {
                "min_qty": int(r["min_qty"]),
                "max_qty": int(r["max_qty"]) if r.get("max_qty") is not None else None,
                "display_label": r.get("display_label"),
                "unit_price": float(r["unit_price"]),
            }
        )

    # keep stable order
    return {"price_tiers_by_decoration": list(grouped.values()), "currency": "USD"}


async def _best_tier_unit_price(hat_id: int, decoration_code_or_name: str, quantity: int) -> Optional[Dict[str, Any]]:
    """
    Find the single best matching tier row for a hat + decoration by code/name.
    """
    q = int(quantity)
    key = decoration_code_or_name.strip()

    row = await fetch_one(
        """
        SELECT
          pdt.name as decoration_name,
          pdt.code as decoration_code,
          sdt.min_qty,
          sdt.max_qty,
          sdt.display_label,
          sdt.unit_price
        FROM style_decoration_price_tiers sdt
        JOIN primary_decoration_types pdt ON pdt.id = sdt.decoration_type_id
        WHERE sdt.hat_id = $1
          AND sdt.is_active = 1
          AND pdt.is_active = 1
          AND (pdt.code ILIKE $2 OR pdt.name ILIKE $2)
          AND sdt.min_qty <= $3
          AND (sdt.max_qty IS NULL OR $3 <= sdt.max_qty)
        ORDER BY sdt.min_qty DESC
        LIMIT 1
        """,
        hat_id,
        build_ilike_pattern(key),
        q,
    )
    if row:
        return {
            "decoration_name": row["decoration_name"],
            "decoration_code": row["decoration_code"],
            "min_qty": int(row["min_qty"]),
            "max_qty": int(row["max_qty"]) if row.get("max_qty") is not None else None,
            "display_label": row.get("display_label"),
            "unit_price": float(row["unit_price"]),
            "currency": "USD",
        }

    # fallback: closest min_qty <= quantity (even if max_qty mismatch)
    row = await fetch_one(
        """
        SELECT
          pdt.name as decoration_name,
          pdt.code as decoration_code,
          sdt.min_qty,
          sdt.max_qty,
          sdt.display_label,
          sdt.unit_price
        FROM style_decoration_price_tiers sdt
        JOIN primary_decoration_types pdt ON pdt.id = sdt.decoration_type_id
        WHERE sdt.hat_id = $1
          AND sdt.is_active = 1
          AND pdt.is_active = 1
          AND (pdt.code ILIKE $2 OR pdt.name ILIKE $2)
          AND sdt.min_qty <= $3
        ORDER BY sdt.min_qty DESC
        LIMIT 1
        """,
        hat_id,
        build_ilike_pattern(key),
        q,
    )
    if not row:
        return None

    return {
        "decoration_name": row["decoration_name"],
        "decoration_code": row["decoration_code"],
        "min_qty": int(row["min_qty"]),
        "max_qty": int(row["max_qty"]) if row.get("max_qty") is not None else None,
        "display_label": row.get("display_label"),
        "unit_price": float(row["unit_price"]),
        "currency": "USD",
    }


async def _list_addons_with_tiers() -> List[Dict[str, Any]]:
    addons = await fetch_all(
        """
        SELECT id, name, code, type, description
        FROM decoration_addons
        WHERE is_active = 1
        ORDER BY type ASC, name ASC
        """
    )

    out = []
    for a in addons:
        tiers = await fetch_all(
            """
            SELECT min_qty, max_qty, unit_price
            FROM decoration_addon_price_tiers
            WHERE decoration_addon_id = $1
              AND is_active = 1
            ORDER BY min_qty ASC
            """,
            int(a["id"]),
        )
        out.append(
            {
                "name": a["name"],
                "code": a["code"],
                "type": a["type"],
                "description": a.get("description"),
                "tiers": [
                    {
                        "min_qty": int(t["min_qty"]),
                        "max_qty": int(t["max_qty"]) if t.get("max_qty") is not None else None,
                        "unit_price": float(t["unit_price"]),
                    }
                    for t in tiers
                ],
            }
        )
    return out


async def _addon_best_unit_price_by_code(addon_code: str, quantity: int) -> Optional[Dict[str, Any]]:
    q = int(quantity)
    addon = await fetch_one(
        """
        SELECT id, name, code, type
        FROM decoration_addons
        WHERE is_active = 1 AND code = $1
        LIMIT 1
        """,
        addon_code,
    )
    if not addon:
        return None

    row = await fetch_one(
        """
        SELECT min_qty, max_qty, unit_price
        FROM decoration_addon_price_tiers
        WHERE decoration_addon_id = $1
          AND is_active = 1
          AND min_qty <= $2
          AND (max_qty IS NULL OR $2 <= max_qty)
        ORDER BY min_qty DESC
        LIMIT 1
        """,
        int(addon["id"]),
        q,
    )
    if not row:
        row = await fetch_one(
            """
            SELECT min_qty, max_qty, unit_price
            FROM decoration_addon_price_tiers
            WHERE decoration_addon_id = $1
              AND is_active = 1
              AND min_qty <= $2
            ORDER BY min_qty DESC
            LIMIT 1
            """,
            int(addon["id"]),
            q,
        )
    if not row:
        return None

    return {
        "addon_name": addon["name"],
        "addon_code": addon["code"],
        "addon_type": addon["type"],
        "unit_price": float(row["unit_price"]),
        "min_qty": int(row["min_qty"]),
        "max_qty": int(row["max_qty"]) if row.get("max_qty") is not None else None,
        "currency": "USD",
    }


async def _list_artwork_setup_plans_with_rules() -> List[Dict[str, Any]]:
    plans = await fetch_all(
        """
        SELECT id, name, code, base_fee, description
        FROM artwork_setup_plans
        WHERE is_active = 1
        ORDER BY id ASC
        """
    )

    out = []
    for p in plans:
        rules = await fetch_all(
            """
            SELECT min_total_items, discount_type, discount_value
            FROM artwork_setup_rules
            WHERE setup_plan_id = $1
              AND is_active = 1
            ORDER BY min_total_items ASC
            """,
            int(p["id"]),
        )
        out.append(
            {
                "name": p["name"],
                "code": p["code"],
                "base_fee": float(p["base_fee"]),
                "description": p.get("description"),
                "rules": [
                    {
                        "min_total_items": int(r["min_total_items"]),
                        "discount_type": r["discount_type"],
                        "discount_value": float(r["discount_value"]),
                    }
                    for r in rules
                ],
            }
        )
    return out


async def _calc_artwork_setup_fee_by_code(setup_plan_code: str, total_items: int) -> Optional[Dict[str, Any]]:
    items = int(total_items)
    plan = await fetch_one(
        """
        SELECT id, name, code, base_fee
        FROM artwork_setup_plans
        WHERE is_active = 1 AND code = $1
        LIMIT 1
        """,
        setup_plan_code,
    )
    if not plan:
        return None

    rule = await fetch_one(
        """
        SELECT min_total_items, discount_type, discount_value
        FROM artwork_setup_rules
        WHERE setup_plan_id = $1
          AND is_active = 1
          AND min_total_items <= $2
        ORDER BY min_total_items DESC
        LIMIT 1
        """,
        int(plan["id"]),
        items,
    )

    base_fee = float(plan["base_fee"])
    final_fee = base_fee
    applied = None

    if rule:
        dtype = (_safe_str(rule["discount_type"])).upper()
        dval = float(rule["discount_value"])
        if dtype in ("PERCENT", "PERCENTAGE"):
            final_fee = max(0.0, base_fee * (1.0 - dval / 100.0))
        elif dtype in ("FLAT", "AMOUNT"):
            final_fee = max(0.0, base_fee - dval)
        applied = {"discount_type": dtype, "discount_value": dval, "min_total_items": int(rule["min_total_items"])}

    return {
        "setup_plan": {"name": plan["name"], "code": plan["code"]},
        "base_fee": base_fee,
        "applied_discount": applied,
        "final_fee": round(final_fee, 2),
        "currency": "USD",
    }


async def _list_shipping_methods_with_rules() -> List[Dict[str, Any]]:
    methods = await fetch_all(
        """
        SELECT id, name, code, base_rate
        FROM shipping_methods
        WHERE is_active = 1
        ORDER BY id ASC
        """
    )

    out = []
    for m in methods:
        rules = await fetch_all(
            """
            SELECT min_total_items, min_subtotal_amount, discount_type, discount_value
            FROM shipping_rules
            WHERE shipping_method_id = $1
              AND is_active = 1
            ORDER BY min_total_items ASC, COALESCE(min_subtotal_amount, 0) ASC
            """,
            int(m["id"]),
        )
        out.append(
            {
                "name": m["name"],
                "code": m["code"],
                "base_rate": float(m["base_rate"]),
                "rules": [
                    {
                        "min_total_items": int(r["min_total_items"]),
                        "min_subtotal_amount": float(r["min_subtotal_amount"]) if r.get("min_subtotal_amount") is not None else None,
                        "discount_type": r["discount_type"],
                        "discount_value": float(r["discount_value"]),
                    }
                    for r in rules
                ],
            }
        )
    return out


async def _calc_shipping_cost_by_code(shipping_code: str, total_items: int, subtotal_amount: float) -> Optional[Dict[str, Any]]:
    items = int(total_items)
    subtotal = float(subtotal_amount or 0.0)

    method = await fetch_one(
        """
        SELECT id, name, code, base_rate
        FROM shipping_methods
        WHERE is_active = 1 AND code = $1
        LIMIT 1
        """,
        shipping_code,
    )
    if not method:
        return None

    rule = await fetch_one(
        """
        SELECT min_total_items, min_subtotal_amount, discount_type, discount_value
        FROM shipping_rules
        WHERE shipping_method_id = $1
          AND is_active = 1
          AND min_total_items <= $2
          AND (min_subtotal_amount IS NULL OR min_subtotal_amount <= $3)
        ORDER BY min_total_items DESC, COALESCE(min_subtotal_amount, 0) DESC
        LIMIT 1
        """,
        int(method["id"]),
        items,
        subtotal,
    )

    base_rate = float(method["base_rate"])
    final = base_rate
    applied = None

    if rule:
        dtype = (_safe_str(rule["discount_type"])).upper()
        dval = float(rule["discount_value"])
        if dtype in ("PERCENT", "PERCENTAGE"):
            final = max(0.0, base_rate * (1.0 - dval / 100.0))
        elif dtype in ("FLAT", "AMOUNT"):
            final = max(0.0, base_rate - dval)
        elif dtype in ("FREE",):
            final = 0.0
        applied = {
            "discount_type": dtype,
            "discount_value": dval,
            "min_total_items": int(rule["min_total_items"]),
            "min_subtotal_amount": float(rule["min_subtotal_amount"]) if rule.get("min_subtotal_amount") is not None else None,
        }

    return {
        "shipping_method": {"name": method["name"], "code": method["code"]},
        "base_rate": base_rate,
        "applied_discount": applied,
        "final_shipping_cost": round(final, 2),
        "currency": "USD",
    }


#MCP functions
@mcp.tool()
async def health_check() -> Dict[str, Any]:
    """
    Purpose:
      - Confirm DB connectivity for the chatbot backend.

    Args:
      - None

    Returns:
      - {"ok": true/false}

    Expected user questions this supports:
      - "Is the system working?"
      - "Are you online?"
      - "Can you check the database connection?"
    """
    row = await fetch_one("SELECT 1 AS ok;")
    return {"ok": bool(row and row.get("ok") == 1)}


@mcp.tool()
async def search_hats_catalog(search_text: str, limit: int = 10) -> Dict[str, Any]:
    """
    Purpose:
      - Customer-friendly hat search using a natural phrase.
      - Searches in hat name + description.

    Args:
      - search_text (str): any phrase like "trucker", "mesh", "snapback", "camo", etc.
      - limit (int): max hats to return (default 10)

    Returns:
      - {
          "query": "...",
          "count": N,
          "hats": [
            {
              "hat_name": "...",
              "description": "...",
              "min_order_qty": 24,
              "primary_image": "https://.../path.jpg"
            }, ...
          ]
        }

    Expected user questions this supports:
      - "Show me trucker hats"
      - "Do you have camo hats?"
      - "I want hats for outdoor events"
      - "Find snapback options"
      - "Search hats with mesh"
    """
    pat = build_ilike_pattern(search_text)
    rows = await fetch_all(
        """
        SELECT id, name, description, min_qty
        FROM hats
        WHERE is_active = 1
          AND (name ILIKE $1 OR COALESCE(description,'') ILIKE $1)
        ORDER BY id ASC
        LIMIT $2
        """,
        pat,
        int(limit),
    )

    hats = []
    for r in rows:
        imgs = await _get_hat_style_images(int(r["id"]))
        primary = None
        if imgs:
            primary = imgs[0].get("image_url")
        hats.append(
            {
                "hat_name": r["name"],
                "description": r.get("description"),
                "min_order_qty": r.get("min_qty"),
                "primary_image": primary,
            }
        )

    return {"query": search_text, "count": len(hats), "hats": hats}


@mcp.tool()
async def get_hat_info_by_name(hat_name: str) -> Dict[str, Any]:
    """
    Purpose:
      - The MUST-HAVE tool: customer asks by hat name and gets full details:
        - hat description + min order qty
        - hat style images
        - colors available + each color's images
        - sizes available (grouped by color)
        - decoration types available
        - tier pricing for Embroidery + Leather Patch (and any other decoration types)

    Args:
      - hat_name (str): customer-provided name (full or partial)

    Returns:
      - {
          "hat_name": "...",
          "description": "...",
          "min_order_qty": 24,
          "style_images": [...],
          "colors": [...],
          "sizes_by_color": [...],
          "decoration_types": [...],
          "pricing_tiers": {...}
        }

    Expected user questions this supports:
      - "Tell me about <hat name>"
      - "Show details of <hat name>"
      - "What colors and sizes are available for <hat name>?"
      - "What is embroidery price and leather patch price for <hat name>?"
      - "Show me full details including images for <hat name>"
    """
    hat = await _find_hat_by_name_exact_or_like(hat_name)
    if not hat:
        return {"error": f"Hat not found for name: '{hat_name}'. Try a different spelling or use search."}

    hid = int(hat["id"])
    style_images = await _get_hat_style_images(hid)
    colors = await _get_colors_for_hat(hid)
    sizes_by_color = await _get_sizes_for_hat(hid)
    decoration_types = await _get_decoration_types()
    pricing_tiers = await _get_style_price_tiers_for_hat(hid)

    return {
        "hat_name": hat["name"],
        "description": hat.get("description"),
        "min_order_qty": hat.get("min_qty"),
        "size_chart": hat.get("size_chart_json"),
        "style_images": style_images,
        "colors": colors,
        "sizes_by_color": sizes_by_color,
        "decoration_types": decoration_types,
        "pricing_tiers": pricing_tiers,
    }


@mcp.tool()
async def get_hat_full_summary(hat_name: str) -> Dict[str, Any]:
    """
    Purpose:
      - A compact, customer-friendly summary view for a hat:
        - description + min qty
        - colors count + sizes count
        - 1 primary image
        - quick view of available decoration type codes

    Args:
      - hat_name (str): customer-provided hat name (full/partial)

    Returns:
      - {
          "hat_name": "...",
          "description": "...",
          "min_order_qty": 24,
          "primary_image": "https://...",
          "colors_available": [ ... ],
          "total_colors": N,
          "total_sizes": M,
          "available_decorations": [ {"name":"Embroidery","code":"EMBROIDERY"}, ... ]
        }

    Expected user questions this supports:
      - "Give me a quick summary of <hat name>"
      - "Do you have this hat in many colors?"
      - "How many sizes are available for <hat name>?"
      - "What decoration options are available for <hat name>?"
    """
    hat = await _find_hat_by_name_exact_or_like(hat_name)
    if not hat:
        return {"error": f"Hat not found for name: '{hat_name}'."}

    hid = int(hat["id"])

    # colors
    color_rows = await fetch_all(
        """
        SELECT id, name, primary_image_url
        FROM hat_colors
        WHERE hat_style_id = $1 AND is_active=1
        ORDER BY name ASC
        """,
        hid,
    )

    colors_available = []
    total_sizes = 0

    for c in color_rows:
        cid = int(c["id"])
        sizes = await fetch_all(
            """
            SELECT size_label, variant_name
            FROM hat_size_variants
            WHERE hat_color_id=$1 AND is_active=1
            """,
            cid,
        )
        total_sizes += len(sizes)

        colors_available.append(
            {
                "color_name": c["name"],
                "primary_image_url": _full_url(c.get("primary_image_url")),
            }
        )

    # primary style image
    imgs = await _get_hat_style_images(hid)
    primary_image = imgs[0].get("image_url") if imgs else None

    # decorations available for this hat (from tiers)
    dec_rows = await fetch_all(
        """
        SELECT DISTINCT pdt.name, pdt.code
        FROM style_decoration_price_tiers sdt
        JOIN primary_decoration_types pdt ON pdt.id = sdt.decoration_type_id
        WHERE sdt.hat_id=$1 AND sdt.is_active=1 AND pdt.is_active=1
        ORDER BY pdt.code ASC
        """,
        hid,
    )

    return {
        "hat_name": hat["name"],
        "description": hat.get("description"),
        "min_order_qty": hat.get("min_qty"),
        "primary_image": primary_image,
        "colors_available": colors_available,
        "total_colors": len(color_rows),
        "total_sizes": total_sizes,
        "available_decorations": [{"name": r["name"], "code": r["code"]} for r in dec_rows],
    }


@mcp.tool()
async def list_pricing_guide() -> Dict[str, Any]:
    """
    Purpose:
      - One tool to return ALL global pricing configuration info needed by chatbot:
        - Primary decoration types
        - Decoration addons + addon price tiers (includes stitching, puff, patch options etc)
        - Artwork setup plans + setup rules
        - Shipping methods + shipping rules

    Args:
      - None

    Returns:
      - {
          "decoration_types": [...],
          "decoration_addons": [...],
          "artwork_setup_plans": [...],
          "shipping_methods": [...],
          "currency": "USD"
        }

    Expected user questions this supports:
      - "What customization options do you offer?"
      - "What are the available add-ons and their pricing tiers?"
      - "What artwork setup plans exist?"
      - "How does shipping pricing and free shipping work?"
      - "Show me all pricing rules and options"
    """
    decoration_types = await _get_decoration_types()
    addons_with_tiers = await _list_addons_with_tiers()
    setup_plans_with_rules = await _list_artwork_setup_plans_with_rules()
    shipping_methods_with_rules = await _list_shipping_methods_with_rules()

    return {
        "decoration_types": decoration_types,
        "decoration_addons": addons_with_tiers,
        "artwork_setup_plans": setup_plans_with_rules,
        "shipping_methods": shipping_methods_with_rules,
        "currency": "USD",
    }


@mcp.tool()
async def get_hat_price_only(
    hat_name: str,
    quantity: int,
    decoration: str,
) -> Dict[str, Any]:
    """
    Purpose:
      - Return ONLY the hat's base tier unit price for a given quantity and decoration type.
      - This is useful when customer asks: "What's the price per hat for 48 with embroidery?"

    Args:
      - hat_name (str): customer hat name
      - quantity (int): order qty
      - decoration (str): decoration type code or name (e.g., "EMBROIDERY", "Leather Patch")

    Returns:
      - {
          "hat_name": "...",
          "quantity": 48,
          "decoration": {"name":"Embroidery","code":"EMBROIDERY"},
          "matched_tier": {...},
          "unit_price": 12.50,
          "items_total": 600.00,
          "currency": "USD"
        }

    Expected user questions this supports:
      - "Price for 48 hats with embroidery for <hat name>"
      - "What’s the leather patch price tier for 144 of <hat name>?"
      - "Give me per-unit price for 24 with embroidery for <hat name>"
    """
    hat = await _find_hat_by_name_exact_or_like(hat_name)
    if not hat:
        return {"error": f"Hat not found: '{hat_name}'."}

    hid = int(hat["id"])
    tier = await _best_tier_unit_price(hid, decoration, int(quantity))
    if not tier:
        return {"error": f"No pricing tiers found for '{hat['name']}' with decoration '{decoration}'."}

    unit = float(tier["unit_price"])
    qty = int(quantity)
    return {
        "hat_name": hat["name"],
        "quantity": qty,
        "decoration": {"name": tier["decoration_name"], "code": tier["decoration_code"]},
        "matched_tier": {
            "min_qty": tier["min_qty"],
            "max_qty": tier["max_qty"],
            "display_label": tier.get("display_label"),
        },
        "unit_price": unit,
        "items_total": round(unit * qty, 2),
        "currency": "USD",
    }


@mcp.tool()
async def estimate_total_order_price(
    hat_name: str,
    quantity: int,
    decoration: str,
    addon_codes: Optional[List[str]] = None,
    setup_plan_code: Optional[str] = None,
    shipping_method_code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Purpose:
      - Customer-style total estimate tool:
        - Base tier price (hat + decoration)
        - Optional add-on unit prices (by addon CODE list)
        - Optional artwork setup fee (by setup plan CODE)
        - Optional shipping cost (by shipping method CODE, uses subtotal rules)

    Args:
      - hat_name (str): customer hat name
      - quantity (int): order qty
      - decoration (str): "EMBROIDERY" or "LEATHER_PATCH" or name
      - addon_codes (list[str] | None): e.g. ["BACK_STITCHING", "3D_PUFF"] (codes from list_pricing_guide)
      - setup_plan_code (str | None): e.g. "STANDARD" / "PREMIUM" (codes from list_pricing_guide)
      - shipping_method_code (str | None): e.g. "GROUND" / "EXPRESS" (codes from list_pricing_guide)

    Returns:
      - {
          "hat_name": "...",
          "quantity": 48,
          "base": { "unit_price": 12.5, "items_total": 600 },
          "addons": { "unit_addons_total": 2.0, "addons_breakdown": [...] },
          "artwork_setup": {...} | None,
          "shipping": {...} | None,
          "grand_total": 650.00,
          "currency": "USD"
        }

    Expected user questions this supports:
      - "Total cost for 48 of <hat name> with embroidery + back stitching"
      - "Estimate price for 144 <hat name> with leather patch + premium setup"
      - "How much will 96 hats cost including shipping?"
      - "What’s the total with addons and setup fee?"
    """
    hat = await _find_hat_by_name_exact_or_like(hat_name)
    if not hat:
        return {"error": f"Hat not found: '{hat_name}'."}

    hid = int(hat["id"])
    qty = int(quantity)

    # base tier
    base_tier = await _best_tier_unit_price(hid, decoration, qty)
    if not base_tier:
        return {"error": f"No base pricing tiers found for '{hat['name']}' and decoration '{decoration}'."}

    base_unit = float(base_tier["unit_price"])
    items_total = base_unit * qty

    # addons
    addons_breakdown: List[Dict[str, Any]] = []
    addons_unit_total = 0.0
    if addon_codes:
        for code in addon_codes:
            code = code.strip()
            if not code:
                continue
            best = await _addon_best_unit_price_by_code(code, qty)
            if not best:
                addons_breakdown.append({"addon_code": code, "error": "Addon not found or no tier pricing."})
                continue
            addons_unit_total += float(best["unit_price"])
            addons_breakdown.append(
                {
                    "addon_name": best["addon_name"],
                    "addon_code": best["addon_code"],
                    "addon_type": best["addon_type"],
                    "unit_price": float(best["unit_price"]),
                }
            )

    unit_price = base_unit + addons_unit_total
    items_total_with_addons = unit_price * qty

    # artwork setup
    setup_info = None
    setup_fee = 0.0
    if setup_plan_code:
        setup_info = await _calc_artwork_setup_fee_by_code(setup_plan_code, qty)
        if not setup_info:
            setup_info = {"error": f"Setup plan '{setup_plan_code}' not found."}
        else:
            setup_fee = float(setup_info["final_fee"])

    # shipping
    shipping_info = None
    shipping_cost = 0.0
    if shipping_method_code:
        shipping_info = await _calc_shipping_cost_by_code(shipping_method_code, qty, items_total_with_addons)
        if not shipping_info:
            shipping_info = {"error": f"Shipping method '{shipping_method_code}' not found."}
        else:
            shipping_cost = float(shipping_info["final_shipping_cost"])

    grand_total = items_total_with_addons + setup_fee + shipping_cost

    return {
        "hat_name": hat["name"],
        "quantity": qty,
        "decoration": {"name": base_tier["decoration_name"], "code": base_tier["decoration_code"]},
        "base": {
            "unit_price": round(base_unit, 2),
            "items_total": round(items_total, 2),
            "matched_tier": {
                "min_qty": base_tier["min_qty"],
                "max_qty": base_tier["max_qty"],
                "display_label": base_tier.get("display_label"),
            },
        },
        "addons": {
            "unit_addons_total": round(addons_unit_total, 2),
            "addons_breakdown": addons_breakdown,
        },
        "unit_price_with_addons": round(unit_price, 2),
        "items_total_with_addons": round(items_total_with_addons, 2),
        "artwork_setup": setup_info,
        "shipping": shipping_info,
        "grand_total": round(grand_total, 2),
        "currency": "USD",
    }


@mcp.tool()
async def list_customization_options() -> Dict[str, Any]:
    """
    Purpose:
      - Customer asks "What customization options do you offer?"
      - Returns:
        - decoration types (Embroidery, Leather Patch, etc.)
        - addons grouped (stitching/placement/patch options/etc.)

    Args:
      - None

    Returns:
      - {
          "decoration_types": [...],
          "addons": [...]
        }

    Expected user questions this supports:
      - "What customization options can I add?"
      - "Do you offer back stitching / side stitching?"
      - "What add-ons are available for embroidery?"
      - "Show me all add-ons"
    """
    decoration_types = await _get_decoration_types()
    addons = await _list_addons_with_tiers()
    return {"decoration_types": decoration_types, "addons": addons, "currency": "USD"}


@mcp.tool()
async def list_artwork_setup_and_calculator(total_items: int = 24) -> Dict[str, Any]:
    """
    Purpose:
      - Returns artwork setup plans + rules AND also shows computed setup fee
        for a given total_items (customer-friendly).
      - Helps user understand how setup fee discounts apply.

    Args:
      - total_items (int): quantity ordered, used to compute example final fees

    Returns:
      - {
          "total_items": 48,
          "plans": [
              {
                "name": "...",
                "code": "...",
                "base_fee": 30,
                "example_final_fee_for_total_items": 20,
                "rules": [...]
              }
          ],
          "currency": "USD"
        }

    Expected user questions this supports:
      - "What is the artwork setup fee?"
      - "Do setup fees get discounted if I order more?"
      - "Show setup plans and how they work for 48 hats"
    """
    items = int(total_items)
    plans = await _list_artwork_setup_plans_with_rules()
    enriched = []
    for p in plans:
        calc = await _calc_artwork_setup_fee_by_code(p["code"], items)
        enriched.append(
            {
                "name": p["name"],
                "code": p["code"],
                "base_fee": p["base_fee"],
                "description": p.get("description"),
                "example_final_fee_for_total_items": (calc or {}).get("final_fee", p["base_fee"]),
                "rules": p["rules"],
            }
        )
    return {"total_items": items, "plans": enriched, "currency": "USD"}


@mcp.tool()
async def list_shipping_and_calculator(total_items: int = 24, subtotal_amount: float = 0.0) -> Dict[str, Any]:
    """
    Purpose:
      - Customer-friendly shipping tool:
        - returns shipping methods + their rules
        - shows example final shipping cost for given total_items/subtotal

    Args:
      - total_items (int): total hats in order (used to evaluate shipping rules)
      - subtotal_amount (float): example subtotal to evaluate rules with min_subtotal_amount

    Returns:
      - {
          "inputs": {"total_items": 48, "subtotal_amount": 600.0},
          "shipping_methods": [
              {
                "name": "...",
                "code": "...",
                "base_rate": 25,
                "example_final_shipping_cost": 0,
                "rules": [...]
              }
          ],
          "currency": "USD"
        }

    Expected user questions this supports:
      - "What shipping options do you have?"
      - "Do you offer free shipping after a minimum order?"
      - "How much will shipping cost for 48 hats?"
      - "Show shipping rules"
    """
    items = int(total_items)
    subtotal = float(subtotal_amount or 0.0)
    methods = await _list_shipping_methods_with_rules()

    enriched = []
    for m in methods:
        calc = await _calc_shipping_cost_by_code(m["code"], items, subtotal)
        enriched.append(
            {
                "name": m["name"],
                "code": m["code"],
                "base_rate": m["base_rate"],
                "example_final_shipping_cost": (calc or {}).get("final_shipping_cost", m["base_rate"]),
                "rules": m["rules"],
            }
        )

    return {"inputs": {"total_items": items, "subtotal_amount": subtotal}, "shipping_methods": enriched, "currency": "USD"}


if __name__ == "__main__":
    mcp.run(transport="stdio")