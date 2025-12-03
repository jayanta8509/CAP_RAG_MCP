"""
MCP Server Functions for NexusFlow AI
Small, modular functions to fetch data from local CSV files
"""

import pandas as pd
from typing import Dict
import os
import json
from mcp.server.fastmcp import FastMCP
# Define paths to data files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_PATH = os.path.join(BASE_DIR, 'products.csv')
PATCHES_PATH = os.path.join(BASE_DIR, 'patches.json')

mcp = FastMCP("Data_Fetcher")

# Load data files
def load_csv_data():
    """Load products CSV file into pandas DataFrame"""
    try:
        products = pd.read_csv(PRODUCTS_PATH)
        return products
    except Exception as e:
        raise ValueError(f"Error loading products CSV file: {str(e)}")


def load_patches_data():
    """Load patches JSON file"""
    try:
        with open(PATCHES_PATH, 'r') as file:
            patches = json.load(file)
        return patches
    except Exception as e:
        raise ValueError(f"Error loading patches JSON file: {str(e)}")






# ==================== PRODUCT CATALOG FUNCTIONS ====================
@mcp.tool()
def get_product_info(product_id: str) -> Dict:
    """
    Get detailed information about a specific product from the catalog.

    Look up product details including title, features, pricing, and available colors.
    Supports both product IDs with and without 'i' prefix (e.g., 'i3038' or '3038').

    Args:
        product_id: Product identifier (e.g., 'i3038', '3038', 'i7041', 'i8501')

    Returns:
        Dictionary containing:
        - product_id: The product identifier
        - title: Product name/title
        - features: Product features and specifications
        - sizing: Available sizing information
        - pricing: Embroidery pricing for different quantities
        - available_colors: List of available colors

    Example usage:
        - "Show me details for product i3038"
        - "What are the features of product 8501?"
        - "Get pricing information for i7041"
        - "What colors are available for product i7256?"
    """
    products = load_csv_data()

    # Normalize product_id - handle both with and without 'i' prefix
    if not product_id.startswith('i'):
        product_id = 'i' + product_id

    # Filter by product ID
    product = products[products['id'] == product_id]

    if product.empty:
        # Try to find similar product IDs
        available_ids = products['id'].tolist()[:10]
        return {
            "error": f"Product {product_id} not found",
            "available_product_ids_sample": available_ids,
            "hint": "Try using product ID with or without 'i' prefix"
        }

    product_data = product.iloc[0]

    # Extract pricing information
    pricing = {
        "flat_embroidery": {
            "24": product_data.get('flat_embroidery_24'),
            "48": product_data.get('flat_embroidery_48'),
            "96": product_data.get('flat_embroidery_96'),
            "144": product_data.get('flat_embroidery_144'),
            "576": product_data.get('flat_embroidery_576'),
            "2500+": product_data.get('flat_embroidery_2500+')
        },
        "3d_embroidery": {
            "24": product_data.get('3d_embroidery_24'),
            "48": product_data.get('3d_embroidery_48'),
            "96": product_data.get('3d_embroidery_96'),
            "144": product_data.get('3d_embroidery_144'),
            "576": product_data.get('3d_embroidery_576'),
            "2500+": product_data.get('3d_embroidery_2500+')
        }
    }

    # Parse available colors
    colors_str = product_data.get('available_colors', '')
    colors = [color.strip() for color in colors_str.split(';') if color.strip()]

    return {
        "product_id": product_data['id'],
        "title": product_data['title'],
        "features": product_data['features'],
        "sizing": product_data['sizing'],
        "pricing": pricing,
        "available_colors": colors
    }

@mcp.tool()
def search_products(keyword: str) -> Dict:
    """
    Search for products by keyword in title, features, or other attributes.

    Perfect for finding products that match specific criteria like "trucker",
    "performance", "mesh", "wool", etc.

    Args:
        keyword: Search term to find in product catalog

    Returns:
        Dictionary containing:
        - keyword: Search term used
        - matches: Number of products found
        - products: List of matching products with id, title, and key features

    Example usage:
        - "Find trucker caps"
        - "Search for performance products"
        - "Show me mesh back caps"
        - "Find wool blend products"
    """
    products = load_csv_data()

    # Search in title and features (case insensitive)
    mask = (
        products['title'].str.contains(keyword, case=False, na=False) |
        products['features'].str.contains(keyword, case=False, na=False)
    )

    matches = products[mask]

    if matches.empty:
        # Suggest alternative keywords
        sample_titles = products['title'].tolist()[:5]
        return {
            "error": f"No products found for '{keyword}'",
            "sample_products": sample_titles,
            "hint": "Try keywords like: trucker, performance, mesh, wool, athletic"
        }

    # Return simplified product info for search results
    results = []
    for _, product in matches.iterrows():
        results.append({
            "product_id": product['id'],
            "title": product['title'],
            "features": product['features'][:100] + "..." if len(str(product['features'])) > 100 else product['features']
        })

    return {
        "keyword": keyword,
        "matches": len(results),
        "products": results
    }

@mcp.tool()
def get_product_pricing(product_id: str, embroidery_type: str = "flat", quantity: int = 24) -> Dict:
    """
    Get specific pricing information for a product based on embroidery type and quantity.

    Calculate exact pricing for different order quantities and embroidery options.

    Args:
        product_id: Product identifier (e.g., 'i3038', '3038', 'i7041')
        embroidery_type: Type of embroidery ('flat' or '3d')
        quantity: Number of units (24, 48, 96, 144, 576, or 2500+)

    Returns:
        Dictionary containing:
        - product_id: Product identifier
        - product_title: Product name
        - embroidery_type: Type of embroidery requested
        - quantity: Order quantity
        - unit_price: Price per unit
        - total_cost: Total cost for the order

    Example usage:
        - "What's the price for 24 units of product i3038 with flat embroidery?"
        - "Get pricing for 144 pieces of product i7041 with 3D embroidery"
        - "How much for 500 units of product i8501?"
    """
    products = load_csv_data()

    # Normalize product_id
    if not product_id.startswith('i'):
        product_id = 'i' + product_id

    # Find product
    product = products[products['id'] == product_id]

    if product.empty:
        return {"error": f"Product {product_id} not found"}

    product_data = product.iloc[0]

    # Determine pricing column
    embroidery_type = embroidery_type.lower()
    if embroidery_type not in ['flat', '3d']:
        embroidery_type = 'flat'

    # Find appropriate pricing column based on quantity
    if quantity >= 2500:
        qty_column = f"{embroidery_type}_embroidery_2500+"
    elif quantity >= 576:
        qty_column = f"{embroidery_type}_embroidery_576"
    elif quantity >= 144:
        qty_column = f"{embroidery_type}_embroidery_144"
    elif quantity >= 96:
        qty_column = f"{embroidery_type}_embroidery_96"
    elif quantity >= 48:
        qty_column = f"{embroidery_type}_embroidery_48"
    else:
        qty_column = f"{embroidery_type}_embroidery_24"

    unit_price = product_data.get(qty_column)

    if pd.isna(unit_price):
        return {
            "error": f"Pricing not available for {embroidery_type} embroidery at quantity {quantity}",
            "available_quantities": [24, 48, 96, 144, 576, "2500+"]
        }

    total_cost = unit_price * quantity

    return {
        "product_id": product_id,
        "product_title": product_data['title'],
        "embroidery_type": embroidery_type,
        "quantity": quantity,
        "unit_price": float(unit_price),
        "total_cost": float(total_cost),
        "currency": "USD"
    }

@mcp.tool()
def get_all_products() -> Dict:
    """
    Get complete product catalog with all available products.

    Useful for browsing the entire catalog or getting a full product list.

    Returns:
        Dictionary containing:
        - total_products: Total number of products in catalog
        - products: List of all products with id, title, features, and available colors

    Example usage:
        - "Show me all products"
        - "Get the complete product catalog"
        - "List all available caps"
    """
    products = load_csv_data()

    # Remove any empty rows
    products = products.dropna(subset=['id', 'title'])

    # Parse colors for each product
    result_products = []
    for _, product in products.iterrows():
        colors_str = product.get('available_colors', '')
        colors = [color.strip() for color in colors_str.split(';') if color.strip()]

        result_products.append({
            "product_id": product['id'],
            "title": product['title'],
            "features": product['features'],
            "sizing": product['sizing'],
            "available_colors": colors
        })

    return {
        "total_products": len(result_products),
        "products": result_products
    }






# ==================== PATCH FUNCTIONS ====================

@mcp.tool()
def get_patch_pricing(patch_name: str = None) -> Dict:
    """
    Get pricing information for patches and customization options.

    Perfect for customers asking about adding patches, embroidery alternatives,
    or custom branding options to their cap orders.

    Args:
        patch_name: Specific patch name (e.g., "Molded Rubber Patch", "Woven Patch")
                   If None, returns all available patch options

    Returns:
        Dictionary containing:
        - patch_name: Name of the patch (if specified)
        - patch_price: Price per unit for the patch
        - total_patches: Number of available patch types (if none specified)
        - available_patches: List of all patch options with pricing (if none specified)

    Example usage:
        - "How much is a Molded Rubber Patch?"
        - "What patch options do you have?"
        - "Show me all patch pricing"
        - "Price for Woven Patch"
    """
    patches = load_patches_data()

    if patch_name:
        # Find specific patch
        patch_name_lower = patch_name.lower()
        for patch in patches:
            if patch_name_lower in patch['name'].lower():
                return {
                    "patch_name": patch['name'],
                    "patch_price": float(patch['price']),
                    "currency": "USD",
                    "price_per_unit": True
                }

        # If not found, suggest alternatives
        available_names = [p['name'] for p in patches]
        return {
            "error": f"Patch '{patch_name}' not found",
            "available_patches": available_names[:5],
            "hint": "Try: Molded Rubber Patch, Woven Patch, or Embroidered Patch"
        }
    else:
        # Return all patches
        return {
            "total_patches": len(patches),
            "available_patches": patches,
            "price_range": {
                "min_price": min(p['price'] for p in patches),
                "max_price": max(p['price'] for p in patches)
            }
        }

@mcp.tool()
def calculate_total_price(product_id: str, quantity: int = 24, embroidery_type: str = "flat", patch_name: str = None) -> Dict:
    """
    Calculate complete pricing including base product, embroidery, and patches.

    This is the ultimate pricing tool that combines product pricing with customization options.

    Args:
        product_id: Product identifier (e.g., 'i3038', '3038', 'i7041')
        quantity: Number of units (24, 48, 96, 144, 576, or 2500+)
        embroidery_type: Type of embroidery ('flat', '3d', or 'none')
        patch_name: Optional patch name (e.g., 'Molded Rubber Patch')

    Returns:
        Dictionary containing:
        - product_id: Product identifier
        - product_title: Product name
        - quantity: Order quantity
        - embroidery_type: Type of embroidery
        - base_price: Product price per unit
        - embroidery_price: Embroidery cost per unit (if applicable)
        - patch_price: Patch cost per unit (if applicable)
        - unit_price: Total price per unit
        - total_cost: Total cost for the order
        - itemized_breakdown: Detailed cost breakdown

    Example usage:
        - "Calculate total price for i7041 with 48 units and molded rubber patch"
        - "What's the cost for 96 units of i8501 with 3D embroidery and leather patch?"
        - "Price for 24 units of i7256 with flat embroidery only"
    """
    products = load_csv_data()
    patches = load_patches_data()

    # Normalize product_id
    if not product_id.startswith('i'):
        product_id = 'i' + product_id

    # Find product
    product = products[products['id'] == product_id]
    if product.empty:
        return {"error": f"Product {product_id} not found"}

    product_data = product.iloc[0]

    # Determine embroidery pricing
    embroidery_type = embroidery_type.lower()
    if embroidery_type not in ['flat', '3d', 'none']:
        embroidery_type = 'flat'

    # Find appropriate pricing column based on quantity
    if quantity >= 2500:
        qty_column = f"{embroidery_type}_embroidery_2500+"
    elif quantity >= 576:
        qty_column = f"{embroidery_type}_embroidery_576"
    elif quantity >= 144:
        qty_column = f"{embroidery_type}_embroidery_144"
    elif quantity >= 96:
        qty_column = f"{embroidery_type}_embroidery_96"
    elif quantity >= 48:
        qty_column = f"{embroidery_type}_embroidery_48"
    else:
        qty_column = f"{embroidery_type}_embroidery_24"

    base_price = product_data.get(qty_column)
    if pd.isna(base_price):
        return {"error": f"Pricing not available for {embroidery_type} embroidery at quantity {quantity}"}

    # Calculate patch price if specified
    patch_cost = 0
    patch_display_name = None
    if patch_name:
        patch_name_lower = patch_name.lower()
        for patch in patches:
            if patch_name_lower in patch['name'].lower():
                patch_cost = patch['price']
                patch_display_name = patch['name']
                break

    # Calculate totals
    unit_price = float(base_price) + patch_cost
    total_cost = unit_price * quantity

    # Create itemized breakdown
    breakdown = {
        "base_product": {
            "name": product_data['title'],
            "unit_price": float(base_price),
            "total": float(base_price) * quantity
        }
    }

    if patch_cost > 0:
        breakdown["patch"] = {
            "name": patch_display_name,
            "unit_price": patch_cost,
            "total": patch_cost * quantity
        }

    return {
        "product_id": product_id,
        "product_title": product_data['title'],
        "quantity": quantity,
        "embroidery_type": embroidery_type,
        "base_price": float(base_price),
        "embroidery_cost": float(base_price) if embroidery_type != 'none' else 0,
        "patch_name": patch_display_name,
        "patch_cost": patch_cost,
        "unit_price": unit_price,
        "total_cost": total_cost,
        "currency": "USD",
        "itemized_breakdown": breakdown
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")

# ==================== MCP TOOL DEFINITIONS ====================

"""
NexusFlow AI - Product Catalog MCP Server
==========================================

PRODUCT CATALOG:
27 Real Cap Products with IDs like i3038, i7041, i7256, i8501, etc.
- Performance caps, trucker mesh, wool blend, athletic styles
- Real pricing for flat & 3D embroidery (24 to 2500+ units)
- Color options and sizing information

4 INTELLIGENT TOOLS:

📦 PRODUCT CATALOG:
1. get_product_info() - Detailed product information by ID
2. search_products() - Find products by keyword
3. get_product_pricing() - Calculate pricing for orders
4. get_all_products() - Complete product catalog

USAGE EXAMPLES:
"Show me details for product i3038" → get_product_info('i3038')
"Find trucker caps" → search_products('trucker')
"Price for 24 units of i3038" → get_product_pricing('i3038', 'flat', 24)
"Show me all products" → get_all_products()

Product functions accept IDs with or without 'i' prefix (e.g., '3038' or 'i3038').
"""