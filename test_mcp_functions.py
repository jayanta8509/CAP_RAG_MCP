import asyncio
import json
from typing import Any, Dict, Optional

from mcp_functions_db import (
    health_check,
    search_hats_catalog,
    get_hat_info_by_name,
    get_hat_full_summary,
    list_pricing_guide,
    get_hat_price_only,
    estimate_total_order_price,
    list_customization_options,
    list_artwork_setup_and_calculator,
    list_shipping_and_calculator,
)

from db import fetch_one


def pretty(title: str, data: Any) -> None:
    print("\n" + "=" * 90)
    print(title)
    print("=" * 90)
    print(json.dumps(data, indent=2, ensure_ascii=False))


async def pick_any_hat_name() -> Optional[str]:
    """
    Picks one active hat name from DB to use for testing.
    """
    row = await fetch_one(
        """
        SELECT name
        FROM hats
        WHERE is_active = 1
        ORDER BY id ASC
        LIMIT 1
        """
    )
    return row["name"] if row else None


async def pick_any_decoration_code_for_hat(hat_name: str) -> Optional[str]:
    """
    Picks one decoration code that actually exists for that hat in tiers.
    Falls back to common codes if none found.
    """
    hat_row = await fetch_one(
        """
        SELECT id
        FROM hats
        WHERE is_active=1 AND LOWER(name)=LOWER($1)
        LIMIT 1
        """,
        hat_name,
    )
    if not hat_row:
        return "EMBROIDERY"

    hid = int(hat_row["id"])
    row = await fetch_one(
        """
        SELECT pdt.code
        FROM style_decoration_price_tiers sdt
        JOIN primary_decoration_types pdt ON pdt.id = sdt.decoration_type_id
        WHERE sdt.hat_id = $1
          AND sdt.is_active = 1
          AND pdt.is_active = 1
        ORDER BY pdt.id ASC
        LIMIT 1
        """,
        hid,
    )
    return row["code"] if row and row.get("code") else "EMBROIDERY"


async def pick_any_addon_code() -> Optional[str]:
    row = await fetch_one(
        """
        SELECT code
        FROM decoration_addons
        WHERE is_active=1
        ORDER BY id ASC
        LIMIT 1
        """
    )
    return row["code"] if row else None


async def pick_any_setup_plan_code() -> Optional[str]:
    row = await fetch_one(
        """
        SELECT code
        FROM artwork_setup_plans
        WHERE is_active=1
        ORDER BY id ASC
        LIMIT 1
        """
    )
    return row["code"] if row else None


async def pick_any_shipping_method_code() -> Optional[str]:
    row = await fetch_one(
        """
        SELECT code
        FROM shipping_methods
        WHERE is_active=1
        ORDER BY id ASC
        LIMIT 1
        """
    )
    return row["code"] if row else None


async def main():
    hat_name = await pick_any_hat_name()
    if not hat_name:
        print("❌ No active hat found in DB. Cannot run hat-based tests.")
        return

    decoration_code = await pick_any_decoration_code_for_hat(hat_name)
    addon_code = await pick_any_addon_code()
    setup_code = await pick_any_setup_plan_code()
    ship_code = await pick_any_shipping_method_code()

    qty = 48  # sample quantity

    print(f"Using hat_name: {hat_name}")
    print(f"Using decoration: {decoration_code}")
    print(f"Using addon_code: {addon_code}")
    print(f"Using setup_plan_code: {setup_code}")
    print(f"Using shipping_method_code: {ship_code}")
    print(f"Using quantity: {qty}")

    # 1) health_check
    pretty("1) health_check()", await health_check())

    # 2) search_hats_catalog
    pretty(
        "2) search_hats_catalog(search_text='I7042', limit=5)",
        await search_hats_catalog("I7042", 5),
    )

    # 3) get_hat_info_by_name
    pretty(
        f"3) get_hat_info_by_name(hat_name='{hat_name}')",
        await get_hat_info_by_name(hat_name),
    )

    # 4) get_hat_full_summary
    pretty(
        f"4) get_hat_full_summary(hat_name='{hat_name}')",
        await get_hat_full_summary(hat_name),
    )

    # 5) list_pricing_guide
    pretty("5) list_pricing_guide()", await list_pricing_guide())

    # 6) get_hat_price_only
    pretty(
        f"6) get_hat_price_only(hat_name='{hat_name}', quantity={qty}, decoration='{decoration_code}')",
        await get_hat_price_only(hat_name, qty, decoration_code),
    )

    # 7) estimate_total_order_price
    addon_codes = [addon_code] if addon_code else None
    pretty(
        "7) estimate_total_order_price(hat_name, qty, decoration, addon_codes, setup_plan_code, shipping_method_code)",
        await estimate_total_order_price(
            hat_name=hat_name,
            quantity=qty,
            decoration=decoration_code,
            addon_codes=addon_codes,
            setup_plan_code=setup_code,
            shipping_method_code=ship_code,
        ),
    )

    # 8) list_customization_options
    pretty("8) list_customization_options()", await list_customization_options())

    # 9) list_artwork_setup_and_calculator
    pretty(
        "9) list_artwork_setup_and_calculator(total_items=48)",
        await list_artwork_setup_and_calculator(48),
    )

    # 10) list_shipping_and_calculator
    pretty(
        "10) list_shipping_and_calculator(total_items=48, subtotal_amount=600.0)",
        await list_shipping_and_calculator(48, 600.0),
    )

    print("\n✅ All MCP customer tools tested.\n")


if __name__ == "__main__":
    asyncio.run(main())
