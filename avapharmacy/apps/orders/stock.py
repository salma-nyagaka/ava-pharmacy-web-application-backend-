from dataclasses import dataclass

from django.db import transaction

from apps.products.models import Product, ProductInventory, ProductVariant, StockMovement


@dataclass
class InventoryAllocation:
    stock_quantity: int = 0
    backorder_quantity: int = 0
    branch_quantity: int = 0
    warehouse_quantity: int = 0


def _lock_product_inventories(product):
    return list(
        ProductInventory.objects.select_for_update()
        .filter(product=product)
        .order_by('location')
    )


def _consume_product_inventory(product, quantity):
    remaining = quantity
    allocation = InventoryAllocation()
    inventories = _lock_product_inventories(product)

    for location in (Product.STOCK_BRANCH, Product.STOCK_WAREHOUSE):
        inventory = next((item for item in inventories if item.location == location), None)
        if inventory is None or remaining <= 0:
            continue
        take = min(inventory.stock_quantity, remaining)
        if take:
            before = inventory.stock_quantity
            inventory.stock_quantity -= take
            inventory.save(update_fields=['stock_quantity', 'updated_at'])
            StockMovement.objects.create(
                product=product,
                movement_type=StockMovement.TYPE_SALE,
                source=StockMovement.SOURCE_ORDER,
                quantity_change=-take,
                quantity_before=before,
                quantity_after=inventory.stock_quantity,
                reason='Order stock commitment',
            )
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
                before = inventory.max_backorder_quantity
                inventory.max_backorder_quantity -= take
                inventory.save(update_fields=['max_backorder_quantity', 'updated_at'])
                StockMovement.objects.create(
                    product=product,
                    movement_type=StockMovement.TYPE_RESERVE,
                    source=StockMovement.SOURCE_ORDER,
                    quantity_change=-take,
                    quantity_before=before,
                    quantity_after=inventory.max_backorder_quantity,
                    reason='Order backorder commitment',
                )
                remaining -= take
                allocation.backorder_quantity += take

    if remaining > 0:
        raise ValueError(f'Unable to allocate {quantity} units for {product.name}.')
    return allocation


def _release_product_inventory(product, *, branch_quantity=0, warehouse_quantity=0, backorder_quantity=0):
    inventories = _lock_product_inventories(product)
    for location, quantity in (
        (Product.STOCK_BRANCH, branch_quantity),
        (Product.STOCK_WAREHOUSE, warehouse_quantity),
    ):
        if quantity <= 0:
            continue
        inventory = next((item for item in inventories if item.location == location), None)
        if inventory is None:
            continue
        before = inventory.stock_quantity
        inventory.stock_quantity += quantity
        inventory.save(update_fields=['stock_quantity', 'updated_at'])
        StockMovement.objects.create(
            product=product,
            movement_type=StockMovement.TYPE_RELEASE,
            source=StockMovement.SOURCE_ORDER,
            quantity_change=quantity,
            quantity_before=before,
            quantity_after=inventory.stock_quantity,
            reason='Order stock release',
        )

    if backorder_quantity > 0:
        inventory = next((item for item in inventories if item.allow_backorder), None)
        if inventory is not None:
            before = inventory.max_backorder_quantity
            inventory.max_backorder_quantity += backorder_quantity
            inventory.save(update_fields=['max_backorder_quantity', 'updated_at'])
            StockMovement.objects.create(
                product=product,
                movement_type=StockMovement.TYPE_RELEASE,
                source=StockMovement.SOURCE_ORDER,
                quantity_change=backorder_quantity,
                quantity_before=before,
                quantity_after=inventory.max_backorder_quantity,
                reason='Order backorder release',
            )


@transaction.atomic
def commit_order_inventory(order):
    for item in order.items.select_related('product', 'product_variant'):
        if item.product_variant_id:
            variant = ProductVariant.objects.select_for_update().get(pk=item.product_variant_id)
            before = variant.stock_quantity
            remaining = item.quantity
            stock_take = min(variant.stock_quantity, remaining)
            variant.stock_quantity -= stock_take
            remaining -= stock_take
            backorder_take = 0
            if remaining:
                backorder_take = min(variant.max_backorder_quantity, remaining)
                variant.max_backorder_quantity -= backorder_take
                remaining -= backorder_take
            if remaining:
                raise ValueError(f'Unable to allocate {item.quantity} units for {item.product_name}.')
            variant.save(update_fields=['stock_quantity', 'max_backorder_quantity', 'updated_at'])
            StockMovement.objects.create(
                product=item.product,
                movement_type=StockMovement.TYPE_SALE,
                source=StockMovement.SOURCE_ORDER,
                quantity_change=-item.quantity,
                quantity_before=before,
                quantity_after=variant.stock_quantity,
                reason=f'Order stock commitment for variant {variant.sku}',
                reference=order.order_number,
            )
            item.allocated_branch_quantity = stock_take
            item.allocated_warehouse_quantity = 0
            item.allocated_backorder_quantity = backorder_take
            item.save(update_fields=[
                'allocated_branch_quantity',
                'allocated_warehouse_quantity',
                'allocated_backorder_quantity',
            ])
            continue

        allocation = _consume_product_inventory(item.product, item.quantity)
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
    for item in order.items.select_related('product', 'product_variant'):
        if item.product_variant_id:
            variant = ProductVariant.objects.select_for_update().get(pk=item.product_variant_id)
            variant.stock_quantity += item.allocated_branch_quantity + item.allocated_warehouse_quantity
            variant.max_backorder_quantity += item.allocated_backorder_quantity
            variant.save(update_fields=['stock_quantity', 'max_backorder_quantity', 'updated_at'])
        elif item.product_id:
            _release_product_inventory(
                item.product,
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
