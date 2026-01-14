import asyncio
from dotenv import load_dotenv

load_dotenv()

from mcp_functions_db import (
    db_health_check,

    list_hats,
    get_hat_by_id,
    search_hats,
    get_hat_min_qty,

    list_hat_colors,
    get_hat_color_by_id,
    search_colors_for_hat,

    list_sizes_for_color,
    list_sizes_for_hat,
    get_size_variant_by_id,

    list_hat_images,
    list_color_images,
    get_primary_image_for_hat,

    list_primary_decoration_types,
    get_primary_decoration_type,

    list_style_price_tiers_for_hat,
    get_style_unit_price,

    get_inventory_by_size_variant,
    get_inventory_for_color,
    get_inventory_for_hat,

    list_decoration_addons,
    get_decoration_addon_by_code,
    list_addon_price_tiers,
    get_addon_unit_price,

    list_artwork_setup_plans,
    get_artwork_setup_plan_by_code,
    list_artwork_setup_rules,
    get_artwork_setup_fee,

    list_shipping_methods,
    list_shipping_rules,
    get_shipping_cost,

    get_hat_full_summary,
    estimate_order_pricing,
)

from db import fetch_one, fetch_all


async def _pick_sample_ids():
    """
    Picks valid ids from DB so test calls don't fail due to missing IDs.
    Returns dict with:
      hat_id, hat_color_id, hat_size_variant_id, decoration_type_id,
      addon_id, addon_code, shipping_method_id, setup_plan_id
    """
    hat = await fetch_one("SELECT id FROM hats WHERE is_active=1 ORDER BY id ASC LIMIT 1;")
    if not hat:
        raise RuntimeError("No active hats found in DB.")
    hat_id = hat["id"]

    color = await fetch_one(
        "SELECT id FROM hat_colors WHERE hat_style_id=$1 AND is_active=1 ORDER BY id ASC LIMIT 1;",
        hat_id,
    )
    hat_color_id = color["id"] if color else None

    size = None
    if hat_color_id:
        size = await fetch_one(
            "SELECT id FROM hat_size_variants WHERE hat_color_id=$1 AND is_active=1 ORDER BY id ASC LIMIT 1;",
            hat_color_id,
        )
    hat_size_variant_id = size["id"] if size else None

    dec = await fetch_one(
        "SELECT id FROM primary_decoration_types WHERE is_active=1 ORDER BY id ASC LIMIT 1;"
    )
    decoration_type_id = dec["id"] if dec else None

    addon = await fetch_one(
        "SELECT id, code FROM decoration_addons WHERE is_active=1 ORDER BY id ASC LIMIT 1;"
    )
    addon_id = addon["id"] if addon else None
    addon_code = addon["code"] if addon else None

    shipping = await fetch_one(
        "SELECT id FROM shipping_methods WHERE is_active=1 ORDER BY id ASC LIMIT 1;"
    )
    shipping_method_id = shipping["id"] if shipping else None

    setup = await fetch_one(
        "SELECT id, code FROM artwork_setup_plans WHERE is_active=1 ORDER BY id ASC LIMIT 1;"
    )
    setup_plan_id = setup["id"] if setup else None
    setup_plan_code = setup["code"] if setup else None

    return {
        "hat_id": hat_id,
        "hat_color_id": hat_color_id,
        "hat_size_variant_id": hat_size_variant_id,
        "decoration_type_id": decoration_type_id,
        "addon_id": addon_id,
        "addon_code": addon_code,
        "shipping_method_id": shipping_method_id,
        "setup_plan_id": setup_plan_id,
        "setup_plan_code": setup_plan_code,
    }


async def main():
    print(" Running MCP Tool Test Suite")

    ids = await _pick_sample_ids()
    hat_id = ids["hat_id"]
    hat_color_id = ids["hat_color_id"]
    hat_size_variant_id = ids["hat_size_variant_id"]
    decoration_type_id = ids["decoration_type_id"]
    addon_id = ids["addon_id"]
    addon_code = ids["addon_code"]
    shipping_method_id = ids["shipping_method_id"]
    setup_plan_id = ids["setup_plan_id"]
    setup_plan_code = ids["setup_plan_code"]

    quantity = 48

    # HEALTH
    print("\n--- db_health_check ---")
    print(await db_health_check())

    # HATS
    print("\n--- list_hats ---")
    print(await list_hats(limit=5, offset=0, active_only=True))

    print("\n--- get_hat_by_id ---")
    print(await get_hat_by_id(hat_id))

    print("\n--- search_hats ---")
    print(await search_hats(keyword="cap", limit=5))

    print("\n--- get_hat_min_qty ---")
    print(await get_hat_min_qty(hat_id))

    # COLORS
    print("\n--- list_hat_colors ---")
    print(await list_hat_colors(hat_id))

    if hat_color_id:
        print("\n--- get_hat_color_by_id ---")
        print(await get_hat_color_by_id(hat_color_id))

        print("\n--- search_colors_for_hat ---")
        print(await search_colors_for_hat(hat_id, keyword="black", limit=5))
    else:
        print("\n No hat_color_id found for sample hat; skipping color-based tests.")

    # SIZES
    if hat_color_id:
        print("\n--- list_sizes_for_color ---")
        print(await list_sizes_for_color(hat_color_id))

    print("\n--- list_sizes_for_hat ---")
    print(await list_sizes_for_hat(hat_id))

    if hat_size_variant_id:
        print("\n--- get_size_variant_by_id ---")
        print(await get_size_variant_by_id(hat_size_variant_id))
    else:
        print("\n No hat_size_variant_id found; skipping size-variant single lookup.")

    # IMAGES
    print("\n--- list_hat_images ---")
    print(await list_hat_images(hat_id))

    print("\n--- get_primary_image_for_hat ---")
    print(await get_primary_image_for_hat(hat_id))

    if hat_color_id:
        print("\n--- list_color_images ---")
        print(await list_color_images(hat_color_id))

    # DECORATION TYPES
    print("\n--- list_primary_decoration_types ---")
    types = await list_primary_decoration_types()
    print(types)

    if decoration_type_id:
        print("\n--- get_primary_decoration_type ---")
        print(await get_primary_decoration_type(decoration_type_id))
    else:
        print("\n No decoration types found; skipping get_primary_decoration_type.")

    # STYLE PRICE TIERS
    print("\n--- list_style_price_tiers_for_hat ---")
    print(await list_style_price_tiers_for_hat(hat_id))

    if decoration_type_id:
        print("\n--- get_style_unit_price ---")
        print(await get_style_unit_price(hat_id, decoration_type_id, quantity))
    else:
        print("\n No decoration_type_id; skipping get_style_unit_price.")

    # INVENTORY
    if hat_size_variant_id:
        print("\n--- get_inventory_by_size_variant ---")
        print(await get_inventory_by_size_variant(hat_size_variant_id))

    if hat_color_id:
        print("\n--- get_inventory_for_color ---")
        print(await get_inventory_for_color(hat_color_id))

    print("\n--- get_inventory_for_hat ---")
    print(await get_inventory_for_hat(hat_id))

    # ADDONS
    print("\n--- list_decoration_addons ---")
    addons = await list_decoration_addons()
    print(addons)

    if addon_code:
        print("\n--- get_decoration_addon_by_code ---")
        print(await get_decoration_addon_by_code(addon_code))
    else:
        print("\n No addon_code found; skipping get_decoration_addon_by_code.")

    if addon_id:
        print("\n--- list_addon_price_tiers ---")
        print(await list_addon_price_tiers(addon_id))

        print("\n--- get_addon_unit_price ---")
        print(await get_addon_unit_price(addon_id, quantity))
    else:
        print("\n No addon_id found; skipping addon tier tests.")

    # ARTWORK SETUP
    print("\n--- list_artwork_setup_plans ---")
    plans = await list_artwork_setup_plans()
    print(plans)

    if setup_plan_code:
        print("\n--- get_artwork_setup_plan_by_code ---")
        print(await get_artwork_setup_plan_by_code(setup_plan_code))

    if setup_plan_id:
        print("\n--- list_artwork_setup_rules ---")
        print(await list_artwork_setup_rules(setup_plan_id))

        print("\n--- get_artwork_setup_fee ---")
        print(await get_artwork_setup_fee(setup_plan_id, total_items=quantity))
    else:
        print("\n No setup plan found; skipping setup rule/fee tests.")

    # SHIPPING
    print("\n--- list_shipping_methods ---")
    methods = await list_shipping_methods()
    print(methods)

    if shipping_method_id:
        print("\n--- list_shipping_rules ---")
        print(await list_shipping_rules(shipping_method_id))

        print("\n--- get_shipping_cost ---")
        print(await get_shipping_cost(shipping_method_id, total_items=quantity, subtotal_amount=999.0))
    else:
        print("\n No shipping_method_id found; skipping shipping tests.")

    #SUMMARY / ESTIMATE
    print("\n--- get_hat_full_summary ---")
    print(await get_hat_full_summary(hat_id))

    if decoration_type_id:
        print("\n--- estimate_order_pricing ---")
        print(await estimate_order_pricing(
            hat_id=hat_id,
            decoration_type_id=decoration_type_id,
            quantity=quantity,
            addon_ids=[addon_id] if addon_id else None,
            shipping_method_id=shipping_method_id,
            artwork_setup_plan_id=setup_plan_id,
        ))
    else:
        print("\n No decoration_type_id; skipping estimate_order_pricing.")

    print("\n All tests executed.")


if __name__ == "__main__":
    asyncio.run(main())
