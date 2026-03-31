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
        string barcode
        string pos_product_id
        string slug UK
        string name
        string strength
        int brand_id FK
        int category_id FK
        int subcategory_id FK
        int catalog_subcategory_id FK
        string image
        string short_description
        text description
        json features
        text directions
        text warnings
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
        int[] health_concern_ids FK
        text dosage_instructions
        text directions
        text warnings
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
