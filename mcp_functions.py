"""
MCP Server Functions for NexusFlow AI
Small, modular functions to fetch data from local CSV files
"""

import pandas as pd
from typing import Dict
import os
from mcp.server.fastmcp import FastMCP
# Define paths to CSV files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_PATH = os.path.join(BASE_DIR, 'products.csv')

mcp = FastMCP("Data_Fetcher")

# Load CSV files
def load_csv_data():
    """Load products CSV file into pandas DataFrame"""
    try:
        products = pd.read_csv(PRODUCTS_PATH)
        return products
    except Exception as e:
        raise ValueError(f"Error loading products CSV file: {str(e)}")






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