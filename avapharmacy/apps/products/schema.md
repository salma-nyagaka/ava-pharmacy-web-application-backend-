```mermaid
erDiagram
    PRODUCT ||--o{ VARIANT : "has many"
    PRODUCT ||--o{ PRODUCT_IMAGE : "has many"
    VARIANT ||--o{ VARIANT_INVENTORY : "has many"
    VARIANT ||--o{ VARIANT_REVIEW : "has many"
    VARIANT ||--o{ WISHLIST : "saved by users"
    VARIANT ||--o{ CART_ITEM : "added to cart"
    VARIANT ||--o{ ORDER_ITEM : "ordered"
    VARIANT_INVENTORY ||--o{ STOCK_MOVEMENT : "movement log"

    PRODUCT {
        int id PK
        string sku UK
        string barcode
        string pos_product_id
        string slug UK
        string name
        int brand_id FK
        string image
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    VARIANT {
        int id PK
        int product_id FK
        string sku UK
        string barcode
        string pos_product_id
        string name
        string strength
        int category_id FK
        int subcategory_id FK
        int[] health_concern_ids FK
        string short_description
        text description
        json features
        text dosage_instructions
        text directions
        text warnings
        string dosage_quantity
        string dosage_unit
        string dosage_frequency
        string dosage_notes
        json attributes
        decimal price
        decimal cost_price
        decimal original_price
        string image
        boolean requires_prescription
        boolean is_active
        int sort_order
        datetime created_at
        datetime updated_at
    }

    VARIANT_INVENTORY {
        int id PK
        int variant_id FK
        string location
        string source_name
        int stock_quantity
        int low_stock_threshold
        boolean allow_backorder
        int max_backorder_quantity
        date next_restock_date
        boolean is_pos_synced
        datetime last_synced_at
        datetime created_at
        datetime updated_at
    }

    VARIANT_REVIEW {
        int id PK
        int variant_id FK
        int user_id FK
        int rating
        text comment
        boolean is_approved
        datetime created_at
    }

    WISHLIST {
        int id PK
        int user_id FK
        int variant_id FK
        datetime added_at
    }

    CART_ITEM {
        int id PK
        int cart_id FK
        int variant_id FK
        int quantity
        int prescription_id FK
        int prescription_item_id FK
        string prescription_reference
        datetime added_at
    }

    ORDER_ITEM {
        int id PK
        int order_id FK
        int variant_id FK
        string product_name
        string product_sku
        string variant_name
        string variant_sku
        int quantity
        decimal unit_price
        int allocated_branch_quantity
        int allocated_warehouse_quantity
        int allocated_backorder_quantity
        int prescription_id FK
        int prescription_item_id FK
        string prescription_reference
        decimal discount_total
    }

    STOCK_MOVEMENT {
        int id PK
        int variant_inventory_id FK
        string movement_type
        string source
        int quantity_change
        int quantity_before
        int quantity_after
        string reason
        string reference
        int created_by FK
        int updated_by FK
        datetime created_at
        datetime updated_at
    }

    PRODUCT_IMAGE {
        int id PK
        int product_id FK
        string image
        string alt_text
        int order
    }
```

Current design rules:

- `Product` is a catalog parent only.
- `Variant` is the sellable unit.
- Pricing lives on `Variant`.
- Reviews live on `Variant`.
- Wishlist entries point to `Variant`.
- Cart items point to `Variant`.
- Order items point to `Variant`.
- Stock lives on `VariantInventory`.
- Stock movement logs point to `VariantInventory`.

## Workflow Diagram

```mermaid
flowchart TD
    A["Product
    Generic parent record
    Example: Panadol"] --> B["Variant
    Sellable child record
    Example: Panadol Extra"]

    B --> C1["VariantInventory
    Main Shop stock"]
    B --> C2["VariantInventory
    POS Store stock"]

    B --> D["Wishlist
    User saves a specific variant"]
    B --> E["CartItem
    User adds a specific variant to cart"]

    C1 --> E
    C2 --> E

    E --> F["OrderItem
    Snapshot of the purchased variant"]
    F --> G["Order
    Customer order record"]

    C1 --> H["StockMovement
    Reserve / release / deduct log"]
    C2 --> H
```

## Workflow Notes

1. `Product` is created as the generic catalog parent.
2. One or more `Variant` records are created under that product.
3. Each variant gets one or more `VariantInventory` rows by location.
4. The customer interacts with the `Variant`, not the parent product, for wishlist and cart actions.
5. Checkout converts `CartItem` rows into `OrderItem` rows.
6. Inventory changes are recorded against `VariantInventory` and logged in `StockMovement`.

## Category Architecture

Current category-related tables:

- `products_category`
- `products_subcategory`

Current source of truth for live product classification:

- `products_category`
- `products_subcategory`

Why these are the active tables:

- `Variant.category_id` points to `Category`
- `Variant.subcategory_id` points to `products_subcategory`
- public category APIs use `Category`
- admin category APIs under `/admin/categories/` use `Category`
- product filters and serializers use `Category` and `subcategory`

Current practical model:

```text
products_category
  root category

products_subcategory
  child subcategory linked to products_category via category_id

products_productsubcategory
  child subcategory
  optional link back to products_category via category_node_id
```

## Consolidation Recommendation

Target state:

- keep `products_category` only
- represent root categories with `parent_id = NULL`
- represent subcategories with `parent_id = <root category id>`
- remove `products_productcategory` and `products_productsubcategory` after code and data migration

Safe rollout order:

1. Freeze all new writes to `ProductCategory` and `ProductSubcategory`.
2. Update every remaining command, serializer, view, and frontend endpoint name so they explicitly use `Category`.
3. Migrate any remaining legacy rows from `products_productcategory` and `products_productsubcategory` into `products_category`.
4. Remove legacy foreign keys and code paths that still mention `ProductCategory` or `ProductSubcategory`.
5. Drop the legacy tables in a final migration only after checks and data verification pass.

Files that still need cleanup before dropping legacy category tables:

- [models.py](/Users/salmanyagaka/Downloads/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/models.py)
- [serializers.py](/Users/salmanyagaka/Downloads/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/serializers.py)
- [views.py](/Users/salmanyagaka/Downloads/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py)
- [urls.py](/Users/salmanyagaka/Downloads/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/urls.py)
- [seed_catalog.py](/Users/salmanyagaka/Downloads/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/management/commands/seed_catalog.py)
- [rebuild_pharmacy_taxonomy.py](/Users/salmanyagaka/Downloads/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/management/commands/rebuild_pharmacy_taxonomy.py)
