from typing import Any, Dict, List, Optional, Union
from mcp.server.fastmcp import FastMCP

from db import fetch_one, fetch_all, build_ilike_pattern

mcp = FastMCP("DB_Data_Fetcher")


#utility
def _normalize_int(v: Union[str, int]) -> int:
    if isinstance(v, int):
        return v
    return int(str(v).strip())


def _tier_bucket(quantity: int) -> int:
    """
    Your old CSV logic used buckets like 24/48/96/144/576/2500+
    For DB tiers: we select the best tier where min_qty <= quantity
    and (max_qty is null or quantity <= max_qty)
    """
    return int(quantity)


#health
@mcp.tool()
async def db_health_check() -> Dict[str, Any]:
    row = await fetch_one("SELECT 1 as ok;")
    return {"ok": bool(row and row.get("ok") == 1)}


#hats
@mcp.tool()
async def list_hats(limit: int = 50, offset: int = 0, active_only: bool = True) -> Dict[str, Any]:
    """
    Purpose:
      List hat styles from the `hats` table with pagination support.

    Args:
      limit (int): Max number of hats to return.
      offset (int): Number of hats to skip (pagination).
      active_only (bool): If True, returns only hats where is_active = 1.

    Returns:
      Dict:
        - count (int): Number of hats returned.
        - hats (List[Dict]): Each hat includes id, name, internal_style_code, description, min_qty.
    """
    where = "WHERE is_active = 1" if active_only else ""
    hats = await fetch_all(
        f"""
        SELECT id, name, internal_style_code, description, min_qty
        FROM hats
        {where}
        ORDER BY id ASC
        LIMIT $1 OFFSET $2
        """,
        limit, offset
    )
    return {"count": len(hats), "hats": hats}


@mcp.tool()
async def get_hat_by_id(hat_id: Union[str, int]) -> Dict[str, Any]:
    """
    Purpose:
      Fetch a single hat record by hat id.

    Args:
      hat_id (str|int): Hat style primary key (hats.id).

    Returns:
      Dict:
        - If found: Hat fields including id, name, internal_style_code, description, size_chart_json, min_qty, is_active.
        - If not found: {"error": "..."}.
    """
    hid = _normalize_int(hat_id)
    hat = await fetch_one(
        """
        SELECT id, name, internal_style_code, description, size_chart_json, min_qty, is_active
        FROM hats
        WHERE id = $1
        """,
        hid
    )
    return hat or {"error": f"Hat id {hid} not found"}


@mcp.tool()
async def search_hats(keyword: str, limit: int = 30) -> Dict[str, Any]:
    """
    Purpose:
      Search hat by keyword across name, internal_style_code, and description.

    Args:
      keyword (str): Search keyword.
      limit (int): Max number of results to return.

    Returns:
      Dict:
        - keyword (str): Input keyword.
        - count (int): Number of hats returned.
        - hats (List[Dict]): Matching hats (id, name, internal_style_code, description, min_qty).
    """
    pat = build_ilike_pattern(keyword)
    hats = await fetch_all(
        """
        SELECT id, name, internal_style_code, description, min_qty
        FROM hats
        WHERE is_active = 1
          AND (name ILIKE $1 OR internal_style_code ILIKE $1 OR COALESCE(description,'') ILIKE $1)
        ORDER BY id ASC
        LIMIT $2
        """,
        pat, limit
    )
    return {"keyword": keyword, "count": len(hats), "hats": hats}


@mcp.tool()
async def get_hat_min_qty(hat_id: Union[str, int]) -> Dict[str, Any]:
    """
    Purpose:
      Fetch the min_qty for a hat.

    Args:
      hat_id (str|int): Hat style id (hats.id).

    Returns:
      Dict:
        - If found: {"id": <hat_id>, "min_qty": <int|null>}
        - If not found: {"error": "..."}
    """
    hid = _normalize_int(hat_id)
    row = await fetch_one("SELECT id, min_qty FROM hats WHERE id=$1", hid)
    return row or {"error": f"Hat id {hid} not found"}


#COLORS
@mcp.tool()
async def list_hat_colors(hat_id: Union[str, int], active_only: bool = True) -> Dict[str, Any]:
    """
    Purpose:
      List available colors for a given hat.

    Args:
      hat_id (str|int): Hat style id (hat_colors.hat_style_id).
      active_only (bool): If True, return only colors where is_active = 1.

    Returns:
      Dict:
        - hat_id (int): Normalized hat id.
        - count (int): Number of colors returned.
        - colors (List[Dict]): Each color includes id, name, color_code, primary_image_url.
    """
    hid = _normalize_int(hat_id)
    where = "AND hc.is_active = 1" if active_only else ""
    colors = await fetch_all(
        f"""
        SELECT hc.id, hc.name, hc.color_code, hc.primary_image_url
        FROM hat_colors hc
        WHERE hc.hat_style_id = $1
        {where}
        ORDER BY hc.id ASC
        """,
        hid
    )
    return {"hat_id": hid, "count": len(colors), "colors": colors}


@mcp.tool()
async def get_hat_color_by_id(hat_color_id: Union[str, int]) -> Dict[str, Any]:
    """
    Purpose:
      Fetch a single hat color record by its id.

    Args:
      hat_color_id (str|int): HatColor primary key (hat_colors.id).

    Returns:
      Dict:
        - If found: Color fields including id, hat_style_id, name, color_code, primary_image_url, is_active.
        - If not found: {"error": "..."}.
    """
    cid = _normalize_int(hat_color_id)
    color = await fetch_one(
        """
        SELECT id, hat_style_id, name, color_code, primary_image_url, is_active
        FROM hat_colors
        WHERE id = $1
        """,
        cid
    )
    return color or {"error": f"HatColor id {cid} not found"}


@mcp.tool()
async def search_colors_for_hat(hat_id: Union[str, int], keyword: str, limit: int = 30) -> Dict[str, Any]:
    """
    Purpose:
      Search colors for a given hat style by keyword (name or color_code).

    Args:
      hat_id (str|int): Hat style id (hat_colors.hat_style_id).
      keyword (str): Search keyword.
      limit (int): Max number of results.

    Returns:
      Dict:
        - hat_id (int): Normalized hat id.
        - keyword (str): Input keyword.
        - count (int): Number of colors returned.
        - colors (List[Dict]): Matching colors (id, name, color_code, primary_image_url).
    """
    hid = _normalize_int(hat_id)
    pat = build_ilike_pattern(keyword)
    colors = await fetch_all(
        """
        SELECT id, name, color_code, primary_image_url
        FROM hat_colors
        WHERE hat_style_id = $1
          AND is_active = 1
          AND (name ILIKE $2 OR COALESCE(color_code,'') ILIKE $2)
        ORDER BY id ASC
        LIMIT $3
        """,
        hid, pat, limit
    )
    return {"hat_id": hid, "keyword": keyword, "count": len(colors), "colors": colors}


# SIZES (variants)
@mcp.tool()
async def list_sizes_for_color(hat_color_id: Union[str, int], active_only: bool = True) -> Dict[str, Any]:
    """
    Purpose:
      List all size variants for a specific hat color.

    Args:
      hat_color_id (str|int): HatColor id (hat_size_variants.hat_color_id).
      active_only (bool): If True, return only sizes where is_active = 1.

    Returns:
      Dict:
        - hat_color_id (int): Normalized color id.
        - count (int): Number of sizes returned.
        - sizes (List[Dict]): Each size includes id, size_label, variant_name, supplier_sku.
    """
    cid = _normalize_int(hat_color_id)
    where = "AND hsv.is_active = 1" if active_only else ""
    sizes = await fetch_all(
        f"""
        SELECT hsv.id, hsv.size_label, hsv.variant_name, hsv.supplier_sku
        FROM hat_size_variants hsv
        WHERE hsv.hat_color_id = $1
        {where}
        ORDER BY hsv.id ASC
        """,
        cid
    )
    return {"hat_color_id": cid, "count": len(sizes), "sizes": sizes}


@mcp.tool()
async def list_sizes_for_hat(hat_id: Union[str, int]) -> Dict[str, Any]:
    """
    Purpose:
      List all size variants for a hat across all its colors.

    Args:
      hat_id (str|int): Hat style id (hat_colors.hat_style_id).

    Returns:
      Dict:
        - hat_id (int): Normalized hat id.
        - count (int): Number of size records returned.
        - sizes (List[Dict]): Rows include hat_color_id, color_name, hat_size_variant_id, size_label, variant_name, supplier_sku.
    """
    hid = _normalize_int(hat_id)
    sizes = await fetch_all(
        """
        SELECT
          hc.id as hat_color_id,
          hc.name as color_name,
          hsv.id as hat_size_variant_id,
          hsv.size_label,
          hsv.variant_name,
          hsv.supplier_sku
        FROM hat_colors hc
        JOIN hat_size_variants hsv ON hsv.hat_color_id = hc.id
        WHERE hc.hat_style_id = $1
          AND hc.is_active = 1
          AND hsv.is_active = 1
        ORDER BY hc.id, hsv.id
        """,
        hid
    )
    return {"hat_id": hid, "count": len(sizes), "sizes": sizes}


@mcp.tool()
async def get_size_variant_by_id(hat_size_variant_id: Union[str, int]) -> Dict[str, Any]:
    """
    Purpose:
      Fetch a single size variant record by its id.

    Args:
      hat_size_variant_id (str|int): Size variant id (hat_size_variants.id).

    Returns:
      Dict:
        - If found: id, hat_color_id, size_label, variant_name, supplier_sku, is_active.
        - If not found: {"error": "..."}.
    """
    sid = _normalize_int(hat_size_variant_id)
    row = await fetch_one(
        """
        SELECT id, hat_color_id, size_label, variant_name, supplier_sku, is_active
        FROM hat_size_variants
        WHERE id = $1
        """,
        sid
    )
    return row or {"error": f"HatSizeVariant id {sid} not found"}


# IMAGES
@mcp.tool()
async def list_hat_images(hat_id: Union[str, int], image_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Purpose:
      List images for a hat. Optionally filter by image_type.

    Args:
      hat_id (str|int): Hat style id (hat_images.hat_style_id).
      image_type (Optional[str]): If provided, filter by hat_images.image_type.

    Returns:
      Dict:
        - hat_id (int)
        - image_type (Optional[str])
        - count (int)
        - images (List[Dict]): Each includes id, image_url, image_type, alt_text, sort_order, is_primary.
    """
    hid = _normalize_int(hat_id)
    if image_type:
        rows = await fetch_all(
            """
            SELECT id, image_url, image_type, alt_text, sort_order, is_primary
            FROM hat_images
            WHERE hat_style_id = $1
              AND is_active = 1
              AND image_type = $2
            ORDER BY is_primary DESC, sort_order ASC, id ASC
            """,
            hid, image_type
        )
    else:
        rows = await fetch_all(
            """
            SELECT id, image_url, image_type, alt_text, sort_order, is_primary
            FROM hat_images
            WHERE hat_style_id = $1
              AND is_active = 1
            ORDER BY is_primary DESC, sort_order ASC, id ASC
            """,
            hid
        )
    return {"hat_id": hid, "image_type": image_type, "count": len(rows), "images": rows}


@mcp.tool()
async def list_color_images(hat_color_id: Union[str, int]) -> Dict[str, Any]:
    """
    Purpose:
      List images for a specific hat color.

    Args:
      hat_color_id (str|int): HatColor id (hat_images.hat_color_id).

    Returns:
      Dict:
        - hat_color_id (int)
        - count (int)
        - images (List[Dict]): id, image_url, image_type, alt_text, sort_order, is_primary.
    """
    cid = _normalize_int(hat_color_id)
    rows = await fetch_all(
        """
        SELECT id, image_url, image_type, alt_text, sort_order, is_primary
        FROM hat_images
        WHERE hat_color_id = $1
          AND is_active = 1
        ORDER BY is_primary DESC, sort_order ASC, id ASC
        """,
        cid
    )
    return {"hat_color_id": cid, "count": len(rows), "images": rows}


@mcp.tool()
async def get_primary_image_for_hat(hat_id: Union[str, int]) -> Dict[str, Any]:
    """
    Purpose:
      Fetch the primary image for a hat style (is_primary = 1).

    Args:
      hat_id (str|int): Hat style id (hat_images.hat_style_id).

    Returns:
      Dict:
        - If found: id, image_url, image_type, alt_text
        - If not found: {"error": "..."}
    """
    hid = _normalize_int(hat_id)
    row = await fetch_one(
        """
        SELECT id, image_url, image_type, alt_text
        FROM hat_images
        WHERE hat_style_id = $1
          AND is_active = 1
          AND is_primary = 1
        ORDER BY id ASC
        LIMIT 1
        """,
        hid
    )
    return row or {"error": f"No primary image found for hat {hid}"}


# PRIMARY DECORATION TYPES
@mcp.tool()
async def list_primary_decoration_types(active_only: bool = True) -> Dict[str, Any]:
    """
    Purpose:
      List all primary decoration types (e.g., Embroidery, Leather Patch).

    Args:
      active_only (bool): If True, return only decoration types where is_active = 1.

    Returns:
      Dict:
        - count (int)
        - decoration_types (List[Dict]): id, name, code, description, is_primary, is_active.
    """
    where = "WHERE is_active = 1" if active_only else ""
    rows = await fetch_all(
        f"""
        SELECT id, name, code, description, is_primary, is_active
        FROM primary_decoration_types
        {where}
        ORDER BY id ASC
        """
    )
    return {"count": len(rows), "decoration_types": rows}


@mcp.tool()
async def get_primary_decoration_type(decoration_type_id: Union[str, int]) -> Dict[str, Any]:
    """
    Purpose:
      Fetch a single primary decoration type record by id.

    Args:
      decoration_type_id (str|int): PrimaryDecorationType id.

    Returns:
      Dict:
        - If found: id, name, code, description, is_primary, is_active
        - If not found: {"error": "..."}
    """
    did = _normalize_int(decoration_type_id)
    row = await fetch_one(
        """
        SELECT id, name, code, description, is_primary, is_active
        FROM primary_decoration_types
        WHERE id = $1
        """,
        did
    )
    return row or {"error": f"PrimaryDecorationType id {did} not found"}


# STYLE DECORATION PRICE TIERS (base unit price)
@mcp.tool()
async def list_style_price_tiers_for_hat(hat_id: Union[str, int], decoration_type_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Purpose:
      List all style decoration price tiers for a hat.
      Optionally filter tiers by decoration_type_id.

    Args:
      hat_id (str|int): Hat style id (style_decoration_price_tiers.hat_id).
      decoration_type_id (Optional[int]): If provided, returns tiers only for that decoration type.

    Returns:
      Dict:
        - hat_id (int)
        - decoration_type_id (Optional[int])
        - count (int)
        - tiers (List[Dict]): id, decoration_type_id, min_qty, max_qty, display_label, unit_price.
    """
    hid = _normalize_int(hat_id)
    if decoration_type_id:
        did = _normalize_int(decoration_type_id)
        rows = await fetch_all(
            """
            SELECT id, decoration_type_id, min_qty, max_qty, display_label, unit_price
            FROM style_decoration_price_tiers
            WHERE hat_id = $1
              AND decoration_type_id = $2
              AND is_active = 1
            ORDER BY min_qty ASC
            """,
            hid, did
        )
    else:
        rows = await fetch_all(
            """
            SELECT id, decoration_type_id, min_qty, max_qty, display_label, unit_price
            FROM style_decoration_price_tiers
            WHERE hat_id = $1
              AND is_active = 1
            ORDER BY decoration_type_id ASC, min_qty ASC
            """,
            hid
        )
    return {"hat_id": hid, "decoration_type_id": decoration_type_id, "count": len(rows), "tiers": rows}


@mcp.tool()
async def get_style_unit_price(hat_id: Union[str, int], decoration_type_id: Union[str, int], quantity: int) -> Dict[str, Any]:
    """
    Purpose:
      Return the best matching style price tier (unit price) for:
      hat_id + decoration_type_id + quantity.

    Args:
      hat_id (str|int): Hat style id.
      decoration_type_id (str|int): Primary decoration type id.
      quantity (int): Total order quantity.

    Returns:
      Dict:
        - If found: id, min_qty, max_qty, unit_price, display_label
        - If not found: {"error": "..."}
    """
    hid = _normalize_int(hat_id)
    did = _normalize_int(decoration_type_id)
    qty = _tier_bucket(_normalize_int(quantity))

    row = await fetch_one(
        """
        SELECT id, min_qty, max_qty, unit_price, display_label
        FROM style_decoration_price_tiers
        WHERE hat_id = $1
          AND decoration_type_id = $2
          AND is_active = 1
          AND min_qty <= $3
          AND (max_qty IS NULL OR $3 <= max_qty)
        ORDER BY min_qty DESC
        LIMIT 1
        """,
        hid, did, qty
    )

    if not row:
        row = await fetch_one(
            """
            SELECT id, min_qty, max_qty, unit_price, display_label
            FROM style_decoration_price_tiers
            WHERE hat_id = $1
              AND decoration_type_id = $2
              AND is_active = 1
              AND min_qty <= $3
            ORDER BY min_qty DESC
            LIMIT 1
            """,
            hid, did, qty
        )

    return row or {"error": f"No price tier found for hat={hid}, decoration_type={did}, qty={qty}"}


# INVENTORY
@mcp.tool()
async def get_inventory_by_size_variant(hat_size_variant_id: Union[str, int]) -> Dict[str, Any]:
    """
    Purpose:
      Fetch inventory info for a specific size variant.

    Args:
      hat_size_variant_id (str|int): Hat size variant id (inventory_items.hat_size_variant_id).

    Returns:
      Dict:
        - If found: id, hat_size_variant_id, qty_on_hand, qty_reserved, qty_available, status, source
        - If not found: {"error": "..."}
    """
    sid = _normalize_int(hat_size_variant_id)
    row = await fetch_one(
        """
        SELECT id, hat_size_variant_id, qty_on_hand, qty_reserved, qty_available, status, source
        FROM inventory_items
        WHERE hat_size_variant_id = $1
          AND is_active = 1
        ORDER BY id ASC
        LIMIT 1
        """,
        sid
    )
    return row or {"error": f"No inventory row found for hat_size_variant_id={sid}"}


@mcp.tool()
async def get_inventory_for_color(hat_color_id: Union[str, int]) -> Dict[str, Any]:
    """
    Purpose:
      Fetch inventory availability for all size variants under a given color.

    Args:
      hat_color_id (str|int): HatColor id.

    Returns:
      Dict:
        - hat_color_id (int)
        - count (int)
        - inventory (List[Dict]): hat_size_variant_id, size_label, variant_name, qty_available, status.
    """
    cid = _normalize_int(hat_color_id)
    rows = await fetch_all(
        """
        SELECT
          hsv.id as hat_size_variant_id,
          hsv.size_label,
          hsv.variant_name,
          ii.qty_available,
          ii.status
        FROM hat_size_variants hsv
        LEFT JOIN inventory_items ii
          ON ii.hat_size_variant_id = hsv.id AND ii.is_active = 1
        WHERE hsv.hat_color_id = $1
          AND hsv.is_active = 1
        ORDER BY hsv.id ASC
        """,
        cid
    )
    return {"hat_color_id": cid, "count": len(rows), "inventory": rows}


@mcp.tool()
async def get_inventory_for_hat(hat_id: Union[str, int]) -> Dict[str, Any]:
    """
    Purpose:
      Fetch inventory availability for all colors and sizes of a hat style.

    Args:
      hat_id (str|int): Hat style id.

    Returns:
      Dict:
        - hat_id (int)
        - count (int)
        - inventory (List[Dict]): color + size + qty_available + status for each variant.
    """
    hid = _normalize_int(hat_id)
    rows = await fetch_all(
        """
        SELECT
          hc.id as hat_color_id,
          hc.name as color_name,
          hsv.id as hat_size_variant_id,
          hsv.size_label,
          hsv.variant_name,
          ii.qty_available,
          ii.status
        FROM hat_colors hc
        JOIN hat_size_variants hsv ON hsv.hat_color_id = hc.id AND hsv.is_active=1
        LEFT JOIN inventory_items ii ON ii.hat_size_variant_id = hsv.id AND ii.is_active=1
        WHERE hc.hat_style_id = $1
          AND hc.is_active = 1
        ORDER BY hc.id ASC, hsv.id ASC
        """,
        hid
    )
    return {"hat_id": hid, "count": len(rows), "inventory": rows}


# DECORATION ADDONS + ADDON TIERS
@mcp.tool()
async def list_decoration_addons(active_only: bool = True, addon_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Purpose:
      List available decoration add-ons (e.g. 3D puff, back stitching, etc.).
      Optionally filter by add-on type.

    Args:
      active_only (bool): If True, return only add-ons where is_active = 1.
      addon_type (Optional[str]): If provided, filter by decoration_addons.type.

    Returns:
      Dict:
        - count (int)
        - addons (List[Dict]): id, name, code, type, description, is_active.
    """
    clauses = ["1=1"]
    args: List[Any] = []
    if active_only:
        clauses.append("is_active = 1")
    if addon_type:
        clauses.append("type = $1")
        args.append(addon_type)

    where = " AND ".join(clauses)
    rows = await fetch_all(
        f"""
        SELECT id, name, code, type, description, is_active
        FROM decoration_addons
        WHERE {where}
        ORDER BY id ASC
        """,
        *args
    )
    return {"count": len(rows), "addons": rows}


@mcp.tool()
async def get_decoration_addon_by_code(code: str) -> Dict[str, Any]:
    """
    Purpose:
      Fetch one decoration add-on by its unique code.

    Args:
      code (str): DecorationAddon code (decoration_addons.code).

    Returns:
      Dict:
        - If found: id, name, code, type, description, is_active
        - If not found: {"error": "..."}
    """
    row = await fetch_one(
        """
        SELECT id, name, code, type, description, is_active
        FROM decoration_addons
        WHERE code = $1
        LIMIT 1
        """,
        code
    )
    return row or {"error": f"DecorationAddon code '{code}' not found"}


@mcp.tool()
async def list_addon_price_tiers(decoration_addon_id: Union[str, int]) -> Dict[str, Any]:
    """
    Purpose:
      List all price tiers for a decoration add-on.

    Args:
      decoration_addon_id (str|int): DecorationAddon id (decoration_addon_price_tiers.decoration_addon_id).

    Returns:
      Dict:
        - decoration_addon_id (int)
        - count (int)
        - tiers (List[Dict]): id, min_qty, max_qty, unit_price.
    """
    aid = _normalize_int(decoration_addon_id)
    rows = await fetch_all(
        """
        SELECT id, min_qty, max_qty, unit_price
        FROM decoration_addon_price_tiers
        WHERE decoration_addon_id = $1
          AND is_active = 1
        ORDER BY min_qty ASC
        """,
        aid
    )
    return {"decoration_addon_id": aid, "count": len(rows), "tiers": rows}


@mcp.tool()
async def get_addon_unit_price(decoration_addon_id: Union[str, int], quantity: int) -> Dict[str, Any]:
    """
    Purpose:
      Get the best matching add-on tier unit price for a given quantity.

    Args:
      decoration_addon_id (str|int): DecorationAddon id.
      quantity (int): Order quantity.

    Returns:
      Dict:
        - If found: id, min_qty, max_qty, unit_price
        - If not found: {"error": "..."}
    """
    aid = _normalize_int(decoration_addon_id)
    qty = _tier_bucket(_normalize_int(quantity))

    row = await fetch_one(
        """
        SELECT id, min_qty, max_qty, unit_price
        FROM decoration_addon_price_tiers
        WHERE decoration_addon_id = $1
          AND is_active = 1
          AND min_qty <= $2
          AND (max_qty IS NULL OR $2 <= max_qty)
        ORDER BY min_qty DESC
        LIMIT 1
        """,
        aid, qty
    )

    if not row:
        row = await fetch_one(
            """
            SELECT id, min_qty, max_qty, unit_price
            FROM decoration_addon_price_tiers
            WHERE decoration_addon_id = $1
              AND is_active = 1
              AND min_qty <= $2
            ORDER BY min_qty DESC
            LIMIT 1
            """,
            aid, qty
        )

    return row or {"error": f"No addon tier found for addon_id={aid}, qty={qty}"}


# ARTWORK SETUP PLAN + RULES
@mcp.tool()
async def list_artwork_setup_plans(active_only: bool = True) -> Dict[str, Any]:
    """
    Purpose:
      List available artwork setup plans (e.g., Standard, Premium) with base fees.

    Args:
      active_only (bool): If True, return only plans where is_active = 1.

    Returns:
      Dict:
        - count (int)
        - plans (List[Dict]): id, name, code, base_fee, description, is_active.
    """
    where = "WHERE is_active = 1" if active_only else ""
    rows = await fetch_all(
        f"""
        SELECT id, name, code, base_fee, description, is_active
        FROM artwork_setup_plans
        {where}
        ORDER BY id ASC
        """
    )
    return {"count": len(rows), "plans": rows}


@mcp.tool()
async def get_artwork_setup_plan_by_code(code: str) -> Dict[str, Any]:
    """
    Purpose:
      Fetch an artwork setup plan by its unique code.

    Args:
      code (str): ArtworkSetupPlan code (artwork_setup_plans.code).

    Returns:
      Dict:
        - If found: id, name, code, base_fee, description, is_active
        - If not found: {"error": "..."}
    """
    row = await fetch_one(
        """
        SELECT id, name, code, base_fee, description, is_active
        FROM artwork_setup_plans
        WHERE code = $1
        LIMIT 1
        """,
        code
    )
    return row or {"error": f"ArtworkSetupPlan code '{code}' not found"}


@mcp.tool()
async def list_artwork_setup_rules(setup_plan_id: Union[str, int]) -> Dict[str, Any]:
    """
    Purpose:
      List discount rules for a given artwork setup plan.

    Args:
      setup_plan_id (str|int): Setup plan id (artwork_setup_rules.setup_plan_id).

    Returns:
      Dict:
        - setup_plan_id (int)
        - count (int)
        - rules (List[Dict]): id, setup_plan_id, min_total_items, discount_type, discount_value, is_active.
    """
    pid = _normalize_int(setup_plan_id)
    rows = await fetch_all(
        """
        SELECT id, setup_plan_id, min_total_items, discount_type, discount_value, is_active
        FROM artwork_setup_rules
        WHERE setup_plan_id = $1
          AND is_active = 1
        ORDER BY min_total_items ASC
        """,
        pid
    )
    return {"setup_plan_id": pid, "count": len(rows), "rules": rows}


@mcp.tool()
async def get_artwork_setup_fee(setup_plan_id: Union[str, int], total_items: int) -> Dict[str, Any]:
    """
    Purpose:
      Compute the final artwork setup fee for a plan at a given total_items quantity.
      Applies the best matching rule where min_total_items <= total_items.

    Args:
      setup_plan_id (str|int): Artwork setup plan id.
      total_items (int): Total number of items in the order.

    Returns:
      Dict:
        - setup_plan (Dict): id, name, code
        - base_fee (float)
        - applied_discount (Dict|None): rule_id, discount_type, discount_value
        - final_fee (float)
        - currency (str)
      Or:
        - {"error": "..."} if plan not found/disabled
    """
    pid = _normalize_int(setup_plan_id)
    items = _normalize_int(total_items)

    plan = await fetch_one(
        """
        SELECT id, name, code, base_fee
        FROM artwork_setup_plans
        WHERE id = $1 AND is_active = 1
        """,
        pid
    )
    if not plan:
        return {"error": f"ArtworkSetupPlan id {pid} not found/disabled"}

    rule = await fetch_one(
        """
        SELECT id, min_total_items, discount_type, discount_value
        FROM artwork_setup_rules
        WHERE setup_plan_id = $1
          AND is_active = 1
          AND min_total_items <= $2
        ORDER BY min_total_items DESC
        LIMIT 1
        """,
        pid, items
    )

    base_fee = float(plan["base_fee"])
    final_fee = base_fee
    applied = None

    if rule:
        dtype = (rule["discount_type"] or "").upper()
        dval = float(rule["discount_value"])
        if dtype in ("PERCENT", "PERCENTAGE"):
            final_fee = max(0.0, base_fee * (1.0 - dval / 100.0))
        elif dtype in ("FLAT", "AMOUNT"):
            final_fee = max(0.0, base_fee - dval)
        applied = {"rule_id": rule["id"], "discount_type": dtype, "discount_value": dval}

    return {
        "setup_plan": {"id": plan["id"], "name": plan["name"], "code": plan["code"]},
        "base_fee": base_fee,
        "applied_discount": applied,
        "final_fee": round(final_fee, 2),
        "currency": "USD",
    }


# SHIPPING METHODS + RULES
@mcp.tool()
async def list_shipping_methods(active_only: bool = True) -> Dict[str, Any]:
    """
    Purpose:
      List available shipping methods.

    Args:
      active_only (bool): If True, return only active shipping methods (is_active = 1).

    Returns:
      Dict:
        - count (int)
        - methods (List[Dict]): id, name, code, base_rate, is_active.
    """
    where = "WHERE is_active = 1" if active_only else ""
    rows = await fetch_all(
        f"""
        SELECT id, name, code, base_rate, is_active
        FROM shipping_methods
        {where}
        ORDER BY id ASC
        """
    )
    return {"count": len(rows), "methods": rows}


@mcp.tool()
async def list_shipping_rules(shipping_method_id: Union[str, int]) -> Dict[str, Any]:
    """
    Purpose:
      List shipping rules for a given shipping method (e.g., free shipping above X items).

    Args:
      shipping_method_id (str|int): Shipping method id (shipping_rules.shipping_method_id).

    Returns:
      Dict:
        - shipping_method_id (int)
        - count (int)
        - rules (List[Dict]): id, shipping_method_id, min_total_items, min_subtotal_amount, discount_type, discount_value.
    """
    mid = _normalize_int(shipping_method_id)
    rows = await fetch_all(
        """
        SELECT id, shipping_method_id, min_total_items, min_subtotal_amount, discount_type, discount_value
        FROM shipping_rules
        WHERE shipping_method_id = $1
          AND is_active = 1
        ORDER BY min_total_items ASC
        """,
        mid
    )
    return {"shipping_method_id": mid, "count": len(rows), "rules": rows}


@mcp.tool()
async def get_shipping_cost(shipping_method_id: Union[str, int], total_items: int, subtotal_amount: float = 0.0) -> Dict[str, Any]:
    """
    Purpose:
      Compute shipping cost for a shipping method based on:
      base_rate minus best-matching shipping rule discount.

    Args:
      shipping_method_id (str|int): Shipping method id.
      total_items (int): Total number of items in the order.
      subtotal_amount (float): Subtotal amount (used if min_subtotal_amount is configured).

    Returns:
      Dict:
        - shipping_method (Dict): id, name, code
        - base_rate (float)
        - applied_discount (Dict|None): rule_id, discount_type, discount_value
        - final_shipping_cost (float)
        - currency (str)
      Or:
        - {"error": "..."} if method not found/disabled
    """
    mid = _normalize_int(shipping_method_id)
    items = _normalize_int(total_items)
    subtotal = float(subtotal_amount or 0.0)

    method = await fetch_one(
        """
        SELECT id, name, code, base_rate
        FROM shipping_methods
        WHERE id = $1 AND is_active = 1
        """,
        mid
    )
    if not method:
        return {"error": f"ShippingMethod id {mid} not found/disabled"}

    rule = await fetch_one(
        """
        SELECT id, min_total_items, min_subtotal_amount, discount_type, discount_value
        FROM shipping_rules
        WHERE shipping_method_id = $1
          AND is_active = 1
          AND min_total_items <= $2
          AND (min_subtotal_amount IS NULL OR min_subtotal_amount <= $3)
        ORDER BY min_total_items DESC, COALESCE(min_subtotal_amount, 0) DESC
        LIMIT 1
        """,
        mid, items, subtotal
    )

    base_rate = float(method["base_rate"])
    final = base_rate
    applied = None

    if rule:
        dtype = (rule["discount_type"] or "").upper()
        dval = float(rule["discount_value"])
        if dtype in ("PERCENT", "PERCENTAGE"):
            final = max(0.0, base_rate * (1.0 - dval / 100.0))
        elif dtype in ("FLAT", "AMOUNT"):
            final = max(0.0, base_rate - dval)
        elif dtype in ("FREE",):
            final = 0.0
        applied = {"rule_id": rule["id"], "discount_type": dtype, "discount_value": dval}

    return {
        "shipping_method": {"id": method["id"], "name": method["name"], "code": method["code"]},
        "base_rate": base_rate,
        "applied_discount": applied,
        "final_shipping_cost": round(final, 2),
        "currency": "USD",
    }


#full-summary
@mcp.tool()
async def get_hat_full_summary(hat_id: Union[str, int]) -> Dict[str, Any]:
    """
    Purpose:
      Provide a compact summary for chatbot responses:
      hat info + all colors + total size count + a primary image URL.

    Args:
      hat_id (str|int): Hat style id.

    Returns:
      Dict:
        - hat (Dict): id, name, internal_style_code, description, min_qty
        - colors (List[Dict]): id, name, color_code, primary_image_url
        - sizes_total (int): Total number of size variants across all colors
        - primary_image (str|None): Primary image URL if found
      Or:
        - {"error": "..."} if hat not found
    """
    hid = _normalize_int(hat_id)
    hat = await fetch_one(
        """
        SELECT id, name, internal_style_code, description, min_qty
        FROM hats
        WHERE id = $1
        """,
        hid
    )
    if not hat:
        return {"error": f"Hat id {hid} not found"}

    colors = await fetch_all(
        """
        SELECT id, name, color_code, primary_image_url
        FROM hat_colors
        WHERE hat_style_id = $1 AND is_active = 1
        ORDER BY id ASC
        """,
        hid
    )

    size_count = await fetch_one(
        """
        SELECT COUNT(*)::int as cnt
        FROM hat_colors hc
        JOIN hat_size_variants hsv ON hsv.hat_color_id = hc.id AND hsv.is_active=1
        WHERE hc.hat_style_id = $1 AND hc.is_active=1
        """,
        hid
    )

    primary_image = await fetch_one(
        """
        SELECT image_url
        FROM hat_images
        WHERE hat_style_id = $1 AND is_active=1
        ORDER BY is_primary DESC, sort_order ASC, id ASC
        LIMIT 1
        """,
        hid
    )

    return {
        "hat": hat,
        "colors": colors,
        "sizes_total": (size_count or {}).get("cnt", 0),
        "primary_image": (primary_image or {}).get("image_url"),
    }


@mcp.tool()
async def estimate_order_pricing(
    hat_id: Union[str, int],
    decoration_type_id: Union[str, int],
    quantity: int,
    addon_ids: Optional[List[int]] = None,
    shipping_method_id: Optional[int] = None,
    artwork_setup_plan_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Purpose:
      Provide a high-level order pricing estimate:
        - Base unit price from style_decoration_price_tiers (by decoration type and qty)
        - Optional add-ons (sum of addon tier unit prices)
        - Optional artwork setup fee (plan base fee minus discount rule)
        - Optional shipping cost (base rate minus discount rule)

    Args:
      hat_id (str|int): Hat style id.
      decoration_type_id (str|int): Primary decoration type id.
      quantity (int): Total quantity ordered.
      addon_ids (Optional[List[int]]): List of decoration_addons ids to apply.
      shipping_method_id (Optional[int]): Shipping method id to estimate shipping.
      artwork_setup_plan_id (Optional[int]): Artwork setup plan id to estimate setup fee.

    Returns:
      Dict:
        - inputs (Dict): normalized ids + quantity used
        - pricing (Dict):
            base_unit_price (float)
            addons_unit_price_total (float)
            unit_price (float)
            items_total (float)
            artwork_setup_fee (float)
            shipping_cost (float)
            grand_total (float)
            currency (str)
        - details (Dict):
            base_tier (Dict)
            addons (List[Dict])
            setup (Dict|None)
            shipping (Dict|None)
      Or:
        - {"error": "..."} if base tier cannot be resolved
    """
    hid = _normalize_int(hat_id)
    did = _normalize_int(decoration_type_id)
    qty = _normalize_int(quantity)

    base_tier = await get_style_unit_price(hid, did, qty)
    if "error" in base_tier:
        return base_tier

    base_unit = float(base_tier["unit_price"])
    addons_breakdown = []
    addons_total_unit = 0.0

    if addon_ids:
        for aid in addon_ids:
            tier = await get_addon_unit_price(aid, qty)
            if "error" in tier:
                addons_breakdown.append({"addon_id": aid, "error": tier["error"]})
                continue
            up = float(tier["unit_price"])
            addons_total_unit += up
            addons_breakdown.append({"addon_id": aid, "unit_price": up, "tier_id": tier["id"]})

    unit_price = base_unit + addons_total_unit
    items_total = unit_price * qty

    setup_fee = 0.0
    setup_info = None
    if artwork_setup_plan_id:
        setup_info = await get_artwork_setup_fee(artwork_setup_plan_id, qty)
        if "error" not in setup_info:
            setup_fee = float(setup_info["final_fee"])

    shipping_cost = 0.0
    shipping_info = None
    if shipping_method_id:
        shipping_info = await get_shipping_cost(shipping_method_id, qty, items_total)
        if "error" not in shipping_info:
            shipping_cost = float(shipping_info["final_shipping_cost"])

    grand_total = items_total + setup_fee + shipping_cost

    return {
        "inputs": {
            "hat_id": hid,
            "decoration_type_id": did,
            "quantity": qty,
            "addon_ids": addon_ids or [],
            "shipping_method_id": shipping_method_id,
            "artwork_setup_plan_id": artwork_setup_plan_id,
        },
        "pricing": {
            "base_unit_price": base_unit,
            "addons_unit_price_total": round(addons_total_unit, 2),
            "unit_price": round(unit_price, 2),
            "items_total": round(items_total, 2),
            "artwork_setup_fee": round(setup_fee, 2),
            "shipping_cost": round(shipping_cost, 2),
            "grand_total": round(grand_total, 2),
            "currency": "USD",
        },
        "details": {
            "base_tier": base_tier,
            "addons": addons_breakdown,
            "setup": setup_info,
            "shipping": shipping_info,
        },
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
