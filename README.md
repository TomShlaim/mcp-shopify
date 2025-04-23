# Shopify Product Creator

This Python script provides a comprehensive solution for creating products in Shopify using the Admin API. It includes all available parameters and supports features like variants, media, SEO settings, metafields, and more.

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
export SHOPIFY_SHOP_URL="your-shop.myshopify.com"
export SHOPIFY_ACCESS_TOKEN="your-access-token"
```

## Usage

The script provides a `create_product` function that accepts various parameters for creating a product. Here's an example of how to use it:

```python
from main import create_product

# Example product data
product_data = {
    "title": "Example Product",
    "description_html": "<p>A detailed product description</p>",
    "product_type": "Accessories",
    "vendor": "My Brand",
    "handle": "example-product",
    "tags": ["new", "featured"],
    "status": "ACTIVE",
    "seo": {
        "title": "Example Product - My Brand",
        "description": "SEO optimized description"
    },
    "product_options": [
        {
            "name": "Size",
            "values": ["Small", "Medium", "Large"]
        }
    ],
    "variants": [
        {
            "title": "Small",
            "price": "29.99",
            "sku": "PROD-001-S",
            "inventory_quantity": 10
        }
    ],
    "collections": ["gid://shopify/Collection/your-collection-id"],
    "metafields": [
        {
            "namespace": "custom",
            "key": "material",
            "value": "Cotton",
            "type": "single_line_text_field"
        }
    ]
}

# Create the product
result = create_product(
    shop_url=os.getenv("SHOPIFY_SHOP_URL"),
    access_token=os.getenv("SHOPIFY_ACCESS_TOKEN"),
    **product_data
)
```

## Parameters

The `create_product` function accepts the following parameters:

- `shop_url` (required): Your Shopify shop URL (e.g., "your-shop.myshopify.com")
- `access_token` (required): Your Shopify Admin API access token
- `title` (required): Product title
- `description_html`: HTML description of the product
- `product_type`: Type/category of the product
- `vendor`: Product vendor/brand name
- `handle`: URL-friendly product handle
- `tags`: List of product tags
- `status`: Product status ("ACTIVE" or "DRAFT")
- `seo`: Dictionary containing SEO title and description
- `product_options`: List of product options (e.g., Size, Color)
- `variants`: List of product variants with their details
- `media`: List of media items (images, videos) to attach to the product
- `gift_card`: Boolean indicating if the product is a gift card
- `requires_selling_plan`: Boolean indicating if the product requires a selling plan
- `collections`: List of collection IDs to add the product to
- `metafields`: List of metafields to attach to the product

## Error Handling

The script includes comprehensive error handling for:
- API authentication issues
- Product creation failures
- Variant creation errors
- Media upload problems
- Invalid parameter values

Errors are raised with descriptive messages to help identify and resolve issues quickly.
