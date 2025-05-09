from typing import Any
import httpx
import os
import json
import requests
from typing import Dict, List, Optional, Union
from typing_extensions import TypedDict
from urllib.parse import urljoin, urlunparse
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import base64
import mimetypes

# Load environment variables
load_dotenv()

# Get credentials from environment variables
SHOP_URL = os.getenv("SHOPIFY_SHOP_URL")
ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")

if not SHOP_URL or not ACCESS_TOKEN:
    raise ValueError("SHOPIFY_SHOP_URL and SHOPIFY_ACCESS_TOKEN must be set in .env file")

mcp = FastMCP("shopify")

class ProductOption(TypedDict):
    name: str
    values: List[str]

class ProductVariant(TypedDict, total=False):
    title: str
    price: str
    sku: str
    inventory_quantity: int
    barcode: str
    weight: float
    weight_unit: str
    requires_shipping: bool
    taxable: bool
    inventory_management: str
    inventory_policy: str
    compare_at_price: str
    fulfillment_service: str
    option1: str
    option2: str
    option3: str
    position: int

class SEO(TypedDict):
    title: str
    description: str

class Metafield(TypedDict):
    namespace: str
    key: str
    value: str
    type: str

class ProductMedia(TypedDict):
    type: str
    src: str
    alt: Optional[str]

def create_shopify_product(
    shop_url: str,
    access_token: str,
    title: str,
    description_html: Optional[str] = None,
    product_type: Optional[str] = None,
    vendor: Optional[str] = None,
    handle: Optional[str] = None,
    tags: Optional[List[str]] = None,
    status: str = "ACTIVE",
    seo: Optional[SEO] = None,
    product_options: Optional[List[ProductOption]] = None,
    variants: Optional[List[ProductVariant]] = None,
    media: Optional[List[ProductMedia]] = None,
    gift_card: bool = False,
    requires_selling_plan: bool = False,
    collections: Optional[List[str]] = None,
    metafields: Optional[List[Metafield]] = None
) -> Dict:
    """
    Create a new product in Shopify using the Admin API.
    
    Args:
        shop_url: Your Shopify shop URL (e.g., "your-shop.myshopify.com")
        access_token: Your Shopify Admin API access token
        title: Product title
        description_html: HTML description of the product
        product_type: Type/category of the product
        vendor: Product vendor/brand name
        handle: URL-friendly product handle
        tags: List of product tags
        status: Product status ("ACTIVE" or "DRAFT")
        seo: Dictionary containing SEO title and description
        product_options: List of product options (e.g., Size, Color)
        variants: List of product variants with their details
        media: List of media items (images, videos) to attach to the product
        gift_card: Boolean indicating if the product is a gift card
        requires_selling_plan: Boolean indicating if the product requires a selling plan
        collections: List of collection IDs to add the product to
        metafields: List of metafields to attach to the product
    
    Returns:
        Dict: The created product data from Shopify
    
    Raises:
        requests.exceptions.RequestException: If the API request fails
        ValueError: If required parameters are missing or invalid
    """
    if not all([shop_url, access_token, title]):
        raise ValueError("shop_url, access_token, and title are required parameters")

    # Prepare the GraphQL mutation
    mutation = """
    mutation productCreate($input: ProductInput!) {
        productCreate(input: $input) {
            product {
                id
                title
                handle
                description
                descriptionHtml
                productType
                vendor
                status
                tags
                options {
                    id
                    name
                    values
                }
                variants(first: 100) {
                    edges {
                        node {
                            id
                            title
                            sku
                            price
                            inventoryQuantity
                        }
                    }
                }
                media(first: 100) {
                    edges {
                        node {
                            id
                            mediaContentType
                            alt
                            ... on MediaImage {
                                image {
                                    originalSrc
                                }
                            }
                        }
                    }
                }
                seo {
                    title
                    description
                }
                metafields(first: 100) {
                    edges {
                        node {
                            id
                            namespace
                            key
                            value
                            type
                        }
                    }
                }
            }
            userErrors {
                field
                message
            }
        }
    }
    """

    # Prepare the variables for the mutation
    variables = {
        "input": {
            "title": title,
            "status": status,
            "giftCard": gift_card,
            "requiresSellingPlan": requires_selling_plan
        }
    }

    # Add optional fields if provided
    if description_html:
        variables["input"]["descriptionHtml"] = description_html
    if product_type:
        variables["input"]["productType"] = product_type
    if vendor:
        variables["input"]["vendor"] = vendor
    if handle:
        variables["input"]["handle"] = handle
    if tags:
        variables["input"]["tags"] = tags
    if seo:
        variables["input"]["seo"] = seo
    if product_options:
        variables["input"]["options"] = product_options
    if variants:
        variables["input"]["variants"] = variants
    if collections:
        variables["input"]["collectionsToJoin"] = collections

    # Prepare the request headers
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token
    }

    # Construct URL properly
    full_url = f"https://{shop_url}/admin/api/2024-01/graphql.json"
    print(f"Making request to: {full_url}")
    
    try:
        response = requests.post(
            full_url,
            json={"query": mutation, "variables": variables},
            headers=headers,
            verify=True
        )
    except Exception as e:
        print(f"Request failed: {str(e)}")
        raise

    # Check for request errors
    response.raise_for_status()
    
    data = response.json()
    
    # Check for GraphQL errors
    if "errors" in data:
        raise ValueError(f"GraphQL errors: {json.dumps(data['errors'], indent=2)}")
    
    # Check for user errors
    user_errors = data.get("data", {}).get("productCreate", {}).get("userErrors", [])
    if user_errors:
        raise ValueError(f"User errors: {json.dumps(user_errors, indent=2)}")

    # Get the created product
    product = data.get("data", {}).get("productCreate", {}).get("product")
    if not product:
        raise ValueError("Product creation failed: No product data returned")

    # If media is provided, attach it to the product
    if media and product.get("id"):
        _attach_media(shop_url, access_token, product["id"], media)

    # If metafields are provided, create them
    if metafields and product.get("id"):
        _create_metafields(shop_url, access_token, product["id"], metafields)

    return product

def _attach_media(
    shop_url: str,
    access_token: str,
    product_id: str,
    media: List[ProductMedia]
) -> None:
    """
    Attach media to a product using the Admin API.
    """
    mutation = """
    mutation productCreateMedia($productId: ID!, $media: [CreateMediaInput!]!) {
        productCreateMedia(productId: $productId, media: $media) {
            media {
                id
                mediaContentType
                alt
            }
            mediaUserErrors {
                field
                message
            }
        }
    }
    """

    variables = {
        "productId": product_id,
        "media": [
            {
                "originalSource": m["src"],
                "mediaContentType": m["type"],
                "alt": m.get("alt", "")
            }
            for m in media
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token
    }

    full_url = f"http://{shop_url}/admin/api/2024-01/graphql.json"
    response = requests.post(
        full_url,
        json={"query": mutation, "variables": variables},
        headers=headers
    )

    response.raise_for_status()
    
    data = response.json()
    
    if "errors" in data:
        raise ValueError(f"Media attachment errors: {json.dumps(data['errors'], indent=2)}")

    media_errors = data.get("data", {}).get("productCreateMedia", {}).get("mediaUserErrors", [])
    if media_errors:
        raise ValueError(f"Media user errors: {json.dumps(media_errors, indent=2)}")

def _create_metafields(
    shop_url: str,
    access_token: str,
    product_id: str,
    metafields: List[Metafield]
) -> None:
    """
    Create metafields for a product using the Admin API.
    """
    mutation = """
    mutation metafieldsSet($metafields: [MetafieldsSetInput!]!) {
        metafieldsSet(metafields: $metafields) {
            metafields {
                id
                namespace
                key
                value
                type
            }
            userErrors {
                field
                message
            }
        }
    }
    """

    variables = {
        "metafields": [
            {
                "ownerId": product_id,
                "namespace": m["namespace"],
                "key": m["key"],
                "value": m["value"],
                "type": m["type"]
            }
            for m in metafields
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token
    }

    full_url = f"https://{shop_url}/admin/api/2024-01/graphql.json"
    response = requests.post(
        full_url,
        json={"query": mutation, "variables": variables},
        headers=headers
    )

    response.raise_for_status()
    
    data = response.json()
    
    if "errors" in data:
        raise ValueError(f"Metafield creation errors: {json.dumps(data['errors'], indent=2)}")

    metafield_errors = data.get("data", {}).get("metafieldsSet", {}).get("userErrors", [])
    if metafield_errors:
        raise ValueError(f"Metafield user errors: {json.dumps(metafield_errors, indent=2)}")
    
def upload_file_to_shopify(file_path: str, alt: str = None) -> dict:
    """
    Uploads a file to the Shopify store's Files section using the GraphQL Admin API.
    Args:
        file_path (str): Local path to the file.
        alt (str, optional): Alt text for the file.
    Returns:
        dict: The fileCreate mutation response from Shopify.
    """
    filename = os.path.basename(file_path)
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"
    is_image = mime_type.startswith("image/")
    resource_type = "IMAGE" if is_image else "FILE"
    content_type = "IMAGE" if is_image else "FILE"

    # Debug output
    print(f"[DEBUG] file_path: {file_path}")
    print(f"[DEBUG] filename: {filename}")
    print(f"[DEBUG] mime_type: {mime_type}")
    print(f"[DEBUG] is_image: {is_image}")
    print(f"[DEBUG] resource_type: {resource_type}")
    print(f"[DEBUG] content_type: {content_type}")

    # Step 1: Get staged upload parameters
    mutation = """
    mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
      stagedUploadsCreate(input: $input) {
        stagedTargets {
          url
          resourceUrl
          parameters {
            name
            value
          }
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    variables = {
        "input": [
            {
                "resource": resource_type,
                "filename": filename,
                "mimeType": mime_type,
                "httpMethod": "POST"
            }
        ]
    }
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": ACCESS_TOKEN
    }
    graphql_url = f"https://{SHOP_URL}/admin/api/2023-10/graphql.json"
    resp = requests.post(graphql_url, json={"query": mutation, "variables": variables}, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    print(f"[DEBUG] stagedUploadsCreate response: {json.dumps(data, indent=2)}")
    errors = data.get("data", {}).get("stagedUploadsCreate", {}).get("userErrors", [])
    if errors:
        raise Exception(f"Shopify stagedUploadsCreate error: {errors}")
    staged = data["data"]["stagedUploadsCreate"]["stagedTargets"][0]
    upload_url = staged["url"]
    resource_url = staged["resourceUrl"]
    params = {p["name"]: p["value"] for p in staged["parameters"]}

    # Step 2: Upload the file to the staged URL (S3)
    with open(file_path, "rb") as f:
        files = {"file": (filename, f, mime_type)}
        response = requests.post(upload_url, data=params, files=files)
    if response.status_code not in (200, 201, 204):
        raise Exception(f"Failed to upload file to staged URL: {response.text}")

    # Step 3: Register the file in Shopify using fileCreate
    mutation = """
    mutation fileCreate($files: [FileCreateInput!]!) {
      fileCreate(files: $files) {
        files {
          id
          fileStatus
          alt
          createdAt
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    file_input = {
        "originalSource": resource_url,
        "contentType": content_type,
        "filename": filename
    }
    if alt:
        file_input["alt"] = alt
    variables = {"files": [file_input]}
    resp = requests.post(graphql_url, json={"query": mutation, "variables": variables}, headers=headers)
    resp.raise_for_status()
    return resp.json()

def upload_theme_asset(theme_id: str, asset_key: str, file_path: str) -> dict:
    """
    Upload a file as a theme asset to Shopify using the REST Admin API.

    Args:
        theme_id (str): The ID of the theme to upload the asset to.
        asset_key (str): The asset key/path in the theme (e.g., 'assets/test.png').
        file_path (str): The local path to the file to upload.

    Returns:
        dict: The JSON response from Shopify.
    """
    with open(file_path, "rb") as file:
        encoded_string = base64.b64encode(file.read()).decode("utf-8")

    url = f"https://{SHOP_URL}/admin/api/2023-10/themes/{theme_id}/assets.json"
    headers = {
        "X-Shopify-Access-Token": ACCESS_TOKEN,
        "Content-Type": "application/json"
    }
    data = {
        "asset": {
            "key": asset_key,
            "attachment": encoded_string
        }
    }
    response = requests.put(url, json=data, headers=headers)
    response.raise_for_status()
    return response.json()

@mcp.tool()
def create_product(    
    title: str,
    descriptionHtml: Optional[str] = None,
    productType: Optional[str] = None,
    vendor: Optional[str] = None,
    handle: Optional[str] = None,
    tags: Optional[List[str]] = None,
    status: str = "ACTIVE",
    seo: Optional[Dict[str, str]] = None,
    giftCard: bool = False,
    requiresSellingPlan: bool = False,
    collectionsToJoin: Optional[List[str]] = None,
    metafields: Optional[List[Dict[str, str]]] = None) -> str:
    debug_info = []
    try:        
        result = create_shopify_product(
            shop_url=SHOP_URL,
            access_token=ACCESS_TOKEN,
            title=title,
            description_html=descriptionHtml,
            product_type=productType,
            vendor=vendor,
            handle=handle,
            tags=tags,
            status=status,
            seo=seo,
            gift_card=giftCard,
            requires_selling_plan=requiresSellingPlan,
            collections=collectionsToJoin,
            metafields=metafields
        )
        debug_info.append("Product creation successful")
        debug_info.append(f"Response: {json.dumps(result, indent=2)}")
        return "\n".join(debug_info)
    except Exception as e:
        error_msg = f"Error creating product: {str(e)}"
        debug_info.append(error_msg)
        return "\n".join(debug_info)
    
@mcp.tool()
def upload_theme_asset_tool(theme_id: str, asset_key: str, file_path: str) -> str:
    """
    MCP tool: Upload a file as a theme asset to Shopify using the REST Admin API.
    Args:
        theme_id (str): The ID of the theme to upload the asset to.
        asset_key (str): The asset key/path in the theme (e.g., 'assets/test.png').
        file_path (str): The local path to the file to upload.
    Returns:
        str: The JSON response from Shopify as a string.
    """
    try:
        result = upload_theme_asset(theme_id, asset_key, file_path)
        return json.dumps(result)
    except Exception as e:
        return f"Error uploading theme asset: {str(e)}"
    
@mcp.tool()
def upload_file_to_shopify_tool(file_path: str, alt: str = None) -> str:
    """
    MCP tool: Upload a file to the Shopify store's Files section using the GraphQL Admin API.
    Args:
        file_path (str): Local path to the file.
        alt (str, optional): Alt text for the file.
    Returns:
        str: The JSON response from Shopify as a string.
    """
    try:
        result = upload_file_to_shopify(file_path, alt)
        return json.dumps(result)   
    except Exception as e:
        return f"Error uploading file: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport='stdio')