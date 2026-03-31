from dataclasses import dataclass

from django.db import transaction

from apps.products.models import Product, StockMovement, Variant, VariantInventory


@dataclass
class InventoryAllocation:
    stock_quantity: int = 0
    backorder_quantity: int = 0
    branch_quantity: int = 0
    warehouse_quantity: int = 0


def _lock_product_inventories(product):
    return []


def _consume_product_inventory(product, quantity):
    raise ValueError(f'Product-level stock commitment is disabled for {product.name}. Select a variant instead.')


def _release_product_inventory(product, *, branch_quantity=0, warehouse_quantity=0, backorder_quantity=0):
    raise ValueError(f'Product-level stock release is disabled for {product.name}. Use variant inventory instead.')


def _lock_variant_inventories(variant):
    inventories = list(
        VariantInventory.objects.select_for_update()
        .filter(variant=variant)
        .order_by('location')
    )
    inventory_map = {inventory.location: inventory for inventory in inventories}
    created = False
    for location in (Product.STOCK_BRANCH, Product.STOCK_WAREHOUSE):
        if location not in inventory_map:
            inventory_map[location] = VariantInventory.objects.create(
                variant=variant,
                location=location,
                stock_quantity=0,
                low_stock_threshold=5 if location == Product.STOCK_BRANCH else 0,
            )
            created = True
    if created:
        inventories = list(
            VariantInventory.objects.select_for_update()
            .filter(variant=variant)
            .order_by('location')
        )
    return inventories


def _consume_variant_inventory(variant, quantity):
    remaining = quantity
    allocation = InventoryAllocation()
    inventories = _lock_variant_inventories(variant)
    movement_inventory = None

    for location in (Product.STOCK_BRANCH, Product.STOCK_WAREHOUSE):
        inventory = next((item for item in inventories if item.location == location), None)
        if inventory is None or remaining <= 0:
            continue
        take = min(inventory.stock_quantity, remaining)
        if take:
            if movement_inventory is None:
                movement_inventory = inventory
            inventory.stock_quantity -= take
            inventory.save(update_fields=['stock_quantity', 'updated_at'])
            remaining -= take
            allocation.stock_quantity += take
            if location == Product.STOCK_BRANCH:
                allocation.branch_quantity += take
            else:
                allocation.warehouse_quantity += take

    if remaining > 0:
        for location in (Product.STOCK_BRANCH, Product.STOCK_WAREHOUSE):
            inventory = next((item for item in inventories if item.location == location), None)
            if inventory is None or remaining <= 0 or not inventory.allow_backorder:
                continue
            take = min(inventory.max_backorder_quantity, remaining)
            if take:
                if movement_inventory is None:
                    movement_inventory = inventory
                inventory.max_backorder_quantity -= take
                inventory.save(update_fields=['max_backorder_quantity', 'updated_at'])
                remaining -= take
                allocation.backorder_quantity += take

    if remaining > 0:
        raise ValueError(f'Unable to allocate {quantity} units for {variant}.')

    variant._clear_inventory_cache()
    before = variant.stock_quantity
    variant.save()
    StockMovement.objects.create(
        variant_inventory=movement_inventory or inventories[0],
        movement_type=StockMovement.TYPE_SALE,
        source=StockMovement.SOURCE_ORDER,
        quantity_change=-quantity,
        quantity_before=before,
        quantity_after=variant.stock_quantity,
        reason=f'Order stock commitment for variant {variant.sku}',
    )
    return allocation


def _release_variant_inventory(variant, *, branch_quantity=0, warehouse_quantity=0, backorder_quantity=0):
    inventories = _lock_variant_inventories(variant)
    before = variant.stock_quantity
    movement_inventory = None
    for location, quantity in (
        (Product.STOCK_BRANCH, branch_quantity),
        (Product.STOCK_WAREHOUSE, warehouse_quantity),
    ):
        if quantity <= 0:
            continue
        inventory = next((item for item in inventories if item.location == location), None)
        if inventory is None:
            continue
        if movement_inventory is None:
            movement_inventory = inventory
        inventory.stock_quantity += quantity
        inventory.save(update_fields=['stock_quantity', 'updated_at'])

    if backorder_quantity > 0:
        inventory = next((item for item in inventories if item.allow_backorder), None)
        if inventory is not None:
            if movement_inventory is None:
                movement_inventory = inventory
            inventory.max_backorder_quantity += backorder_quantity
            inventory.save(update_fields=['max_backorder_quantity', 'updated_at'])

    variant._clear_inventory_cache()
    variant.save()
    StockMovement.objects.create(
        variant_inventory=movement_inventory or inventories[0],
        movement_type=StockMovement.TYPE_RELEASE,
        source=StockMovement.SOURCE_ORDER,
        quantity_change=branch_quantity + warehouse_quantity + backorder_quantity,
        quantity_before=before,
        quantity_after=variant.stock_quantity,
        reason=f'Order stock release for variant {variant.sku}',
    )


@transaction.atomic
def commit_order_inventory(order):
    for item in order.items.select_related('variant'):
        if not item.variant_id:
            raise ValueError(f'Order item {item.product_name} is missing a variant. Product-level inventory is disabled.')
        variant = Variant.objects.select_for_update().get(pk=item.variant_id)
        allocation = _consume_variant_inventory(variant, item.quantity)
        item.allocated_branch_quantity = allocation.branch_quantity
        item.allocated_warehouse_quantity = allocation.warehouse_quantity
        item.allocated_backorder_quantity = allocation.backorder_quantity
        item.save(update_fields=[
            'allocated_branch_quantity',
            'allocated_warehouse_quantity',
            'allocated_backorder_quantity',
        ])


@transaction.atomic
def release_order_inventory(order):
    for item in order.items.select_related('variant'):
        if not item.variant_id:
            raise ValueError(f'Order item {item.product_name} is missing a variant. Product-level inventory is disabled.')
        variant = Variant.objects.select_for_update().get(pk=item.variant_id)
        _release_variant_inventory(
            variant,
            branch_quantity=item.allocated_branch_quantity,
            warehouse_quantity=item.allocated_warehouse_quantity,
            backorder_quantity=item.allocated_backorder_quantity,
        )
        item.allocated_branch_quantity = 0
        item.allocated_warehouse_quantity = 0
        item.allocated_backorder_quantity = 0
        item.save(update_fields=[
            'allocated_branch_quantity',
            'allocated_warehouse_quantity',
            'allocated_backorder_quantity',
        ])
