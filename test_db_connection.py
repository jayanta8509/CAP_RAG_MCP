import asyncio
from dotenv import load_dotenv

load_dotenv()

from db import fetch_one, fetch_all


async def main():
    print(" Testing DB connectivity...")

    row = await fetch_one("SELECT 1 AS ok;")
    if row and row.get("ok") == 1:
        print("DB connected: SELECT 1 returned ok=1")
    else:
        print("DB not responding correctly:", row)
        return

    print("\n Checking core tables exist...")
    tables = await fetch_all(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='public'
          AND table_name IN (
            'hats','hat_colors','hat_size_variants','hat_images',
            'style_decoration_price_tiers','primary_decoration_types',
            'inventory_items','decoration_addons','decoration_addon_price_tiers',
            'shipping_methods','shipping_rules',
            'artwork_setup_plans','artwork_setup_rules'
          )
        ORDER BY table_name;
        """
    )
    print(" Found tables:", [t["table_name"] for t in tables])

    print("\n DB connection test completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
