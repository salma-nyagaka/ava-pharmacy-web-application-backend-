"""Location-specific medication selection shared by staff catalogs and checkout."""
from .compliance import medicine_inventory_rows


def location_options(variant):
    rows = medicine_inventory_rows(variant, list(variant.inventories.all()))
    return [
        {
            'inventory_id': row.pk,
            'branch_name': row.store_name or row.get_location_display(),
            'location': row.location,
            'available_quantity': row.stock_quantity,
            'batch_number': row.batch_number,
        }
        for row in rows
        if row.stock_quantity > 0
        and row.effective_status not in {'expired', 'damaged'}
        and (not row.store_listing_id or (
            row.store_listing.is_active and row.store_listing.store.is_active
        ))
    ]


def validate_inventory_selection(variant, inventory_id, quantity):
    if inventory_id is None:
        return
    try:
        inventory_id = int(inventory_id)
    except (TypeError, ValueError):
        raise ValueError('Select a valid medication location.')
    option = next((row for row in location_options(variant) if row['inventory_id'] == inventory_id), None)
    if not option:
        raise ValueError('The selected medication location is unavailable or does not match this variant.')
    if quantity > option['available_quantity']:
        raise ValueError(f"Only {option['available_quantity']} unit(s) are available at {option['branch_name']}.")


def resolve_staff_inventory_selection(variant, inventory_id, quantity):
    if inventory_id is None:
        options = location_options(variant)
        if len(options) > 1:
            raise ValueError('Select the medication branch/location before continuing.')
        if options:
            inventory_id = options[0]['inventory_id']
    validate_inventory_selection(variant, inventory_id, quantity)
    return inventory_id
