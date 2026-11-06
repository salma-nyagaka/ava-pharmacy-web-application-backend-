from django.db import migrations


CREATE_INVENTORY_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION products_check_inventory_listing_variant()
RETURNS trigger AS $$
BEGIN
    IF NEW.store_listing_id IS NOT NULL AND NOT EXISTS (
        SELECT 1
        FROM products_storevariantlisting listing
        WHERE listing.id = NEW.store_listing_id
          AND listing.variant_id = NEW.variant_id
    ) THEN
        RAISE EXCEPTION
            'VariantInventory.variant_id must match StoreVariantListing.variant_id'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER products_inventory_listing_variant_check
BEFORE INSERT OR UPDATE OF variant_id, store_listing_id
ON products_variantinventory
FOR EACH ROW
EXECUTE FUNCTION products_check_inventory_listing_variant();
"""


CREATE_LISTING_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION products_check_listing_inventory_variants()
RETURNS trigger AS $$
BEGIN
    IF NEW.variant_id <> OLD.variant_id AND EXISTS (
        SELECT 1
        FROM products_variantinventory inventory
        WHERE inventory.store_listing_id = NEW.id
          AND inventory.variant_id <> NEW.variant_id
    ) THEN
        RAISE EXCEPTION
            'Cannot move a store listing while inventory rows reference its variant'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER products_listing_inventory_variant_check
BEFORE UPDATE OF variant_id
ON products_storevariantlisting
FOR EACH ROW
EXECUTE FUNCTION products_check_listing_inventory_variants();
"""


DROP_TRIGGERS_SQL = """
DROP TRIGGER IF EXISTS products_inventory_listing_variant_check
ON products_variantinventory;
DROP FUNCTION IF EXISTS products_check_inventory_listing_variant();
DROP TRIGGER IF EXISTS products_listing_inventory_variant_check
ON products_storevariantlisting;
DROP FUNCTION IF EXISTS products_check_listing_inventory_variants();
"""


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0064_store_variant_listings'),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_INVENTORY_TRIGGER_SQL,
            reverse_sql=DROP_TRIGGERS_SQL,
        ),
        migrations.RunSQL(
            sql=CREATE_LISTING_TRIGGER_SQL,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
