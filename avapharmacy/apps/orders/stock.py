from dataclasses import dataclass, field
from datetime import date

from django.db import transaction
from django.db.models import Q

from .models import Order

from apps.products.models import Product, StockMovement, Variant, VariantInventory


@dataclass
class InventoryAllocation:
    stock_quantity: int = 0
    backorder_quantity: int = 0
    branch_quantity: int = 0
    warehouse_quantity: int = 0
    inventory_rows: list[dict] = field(default_factory=list)


def _lock_product_inventories(product):
    return []


def _consume_product_inventory(product, quantity):
    raise ValueError(f'Product-level stock commitment is disabled for {product.name}. Select a variant instead.')


def _release_product_inventory(product, *, branch_quantity=0, warehouse_quantity=0, backorder_quantity=0):
    raise ValueError(f'Product-level stock release is disabled for {product.name}. Use variant inventory instead.')


def _lock_variant_inventories(variant):
    return list(
        VariantInventory.objects.select_for_update(of=('self',))
        .select_related('store_listing__store')
        .filter(variant=variant)
        .filter(
            Q(store_listing__isnull=True)
            | Q(store_listing__is_active=True, store_listing__store__is_active=True)
        )
        .order_by('location', 'expiry_date', 'id')
    )


def _variant_stock_quantity(inventories):
    return sum(inventory.stock_quantity for inventory in inventories)


def _sale_inventory_rows(inventories):
    return sorted(
        [
            inventory for inventory in inventories
            if inventory.effective_status not in {
                VariantInventory.STATUS_DAMAGED,
                VariantInventory.STATUS_EXPIRED,
            }
        ],
        key=lambda inventory: (
            0 if inventory.location == Product.STOCK_BRANCH else 1,
            inventory.expiry_date is None,
            inventory.expiry_date or date.max,
            inventory.id or 0,
        ),
    )


def _create_stock_movement(inventory, *, movement_type, source, quantity_change, quantity_before, quantity_after, reason, reference=''):
    StockMovement.objects.create(
        variant_inventory=inventory,
        movement_type=movement_type,
        source=source,
        batch_number=inventory.batch_number,
        quantity_change=quantity_change,
        quantity_before=quantity_before,
        quantity_after=quantity_after,
        source_location=inventory.location,
        reason=reason,
        reference=reference,
    )


def _allocation_row(inventory, *, stock_quantity=0, backorder_quantity=0):
    store_listing = inventory.store_listing if inventory.store_listing_id else None
    return {
        'inventory_id': inventory.pk,
        'store_listing_id': inventory.store_listing_id,
        'store_code': store_listing.store.code if store_listing else '',
        'stock_quantity': stock_quantity,
        'backorder_quantity': backorder_quantity,
    }


def _consume_variant_inventory(variant, quantity, *, reference=''):
    remaining = quantity
    allocation = InventoryAllocation()
    inventories = _lock_variant_inventories(variant)

    for inventory in _sale_inventory_rows(inventories):
        if remaining <= 0:
            continue
        take = min(inventory.stock_quantity, remaining)
        if take:
            before = inventory.stock_quantity
            inventory.stock_quantity -= take
            inventory.save(update_fields=['stock_quantity', 'updated_at'])
            after = inventory.stock_quantity
            remaining -= take
            allocation.stock_quantity += take
            if inventory.location == Product.STOCK_BRANCH:
                allocation.branch_quantity += take
            else:
                allocation.warehouse_quantity += take
            allocation.inventory_rows.append(
                _allocation_row(inventory, stock_quantity=take)
            )
            _create_stock_movement(
                inventory,
                movement_type=StockMovement.TYPE_SALE,
                source=StockMovement.SOURCE_ORDER,
                quantity_change=-take,
                quantity_before=before,
                quantity_after=after,
                reason=f'Order stock commitment for variant {variant.sku}',
                reference=reference,
            )

    if remaining > 0:
        for location in (Product.STOCK_BRANCH, Product.STOCK_WAREHOUSE):
            inventory = next((item for item in inventories if item.location == location), None)
            if inventory is None or remaining <= 0 or not inventory.allow_backorder:
                continue
            take = min(inventory.max_backorder_quantity, remaining)
            if take:
                before = inventory.stock_quantity
                inventory.max_backorder_quantity -= take
                inventory.save(update_fields=['max_backorder_quantity', 'updated_at'])
                remaining -= take
                allocation.backorder_quantity += take
                allocation.inventory_rows.append(
                    _allocation_row(inventory, backorder_quantity=take)
                )
                _create_stock_movement(
                    inventory,
                    movement_type=StockMovement.TYPE_SALE,
                    source=StockMovement.SOURCE_ORDER,
                    quantity_change=-take,
                    quantity_before=before,
                    quantity_after=inventory.stock_quantity,
                    reason=f'Order backorder commitment for variant {variant.sku}',
                    reference=reference,
                )

    if remaining > 0:
        raise ValueError(f'Unable to allocate {quantity} units for {variant}.')

    variant._clear_inventory_cache()
    variant.save()
    return allocation


def _release_recorded_inventory(variant, allocations, *, reference=''):
    allocation_ids = {
        row.get('inventory_id') for row in allocations if row.get('inventory_id')
    }
    inventories = {
        inventory.pk: inventory
        for inventory in VariantInventory.objects.select_for_update().filter(
            variant=variant,
            pk__in=allocation_ids,
        )
    }
    missing_ids = allocation_ids.difference(inventories)
    if missing_ids:
        missing = ', '.join(str(value) for value in sorted(missing_ids))
        raise ValueError(
            f'Cannot release inventory for variant {variant.sku}; missing rows: {missing}.'
        )

    for row in allocations:
        inventory_id = row.get('inventory_id')
        if not inventory_id:
            continue
        inventory = inventories[inventory_id]
        stock_quantity = max(0, int(row.get('stock_quantity') or 0))
        backorder_quantity = max(0, int(row.get('backorder_quantity') or 0))
        if stock_quantity:
            before = inventory.stock_quantity
            inventory.stock_quantity += stock_quantity
            inventory.save(update_fields=['stock_quantity', 'updated_at'])
            _create_stock_movement(
                inventory,
                movement_type=StockMovement.TYPE_RELEASE,
                source=StockMovement.SOURCE_ORDER,
                quantity_change=stock_quantity,
                quantity_before=before,
                quantity_after=inventory.stock_quantity,
                reason=f'Order stock release for variant {variant.sku}',
                reference=reference,
            )
        if backorder_quantity:
            before = inventory.stock_quantity
            inventory.max_backorder_quantity += backorder_quantity
            inventory.save(update_fields=['max_backorder_quantity', 'updated_at'])
            _create_stock_movement(
                inventory,
                movement_type=StockMovement.TYPE_RELEASE,
                source=StockMovement.SOURCE_ORDER,
                quantity_change=backorder_quantity,
                quantity_before=before,
                quantity_after=inventory.stock_quantity,
                reason=f'Order backorder release for variant {variant.sku}',
                reference=reference,
            )


def _release_variant_inventory(
    variant,
    *,
    inventory_allocations=None,
    branch_quantity=0,
    warehouse_quantity=0,
    backorder_quantity=0,
    reference='',
):
    if inventory_allocations:
        _release_recorded_inventory(
            variant,
            inventory_allocations,
            reference=reference,
        )
        variant._clear_inventory_cache()
        variant.save()
        return

    # Compatibility path for orders committed before exact inventory-row
    # allocations were recorded.
    inventories = _lock_variant_inventories(variant)
    before = _variant_stock_quantity(inventories)
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
        before = inventory.stock_quantity
        inventory.stock_quantity += quantity
        inventory.save(update_fields=['stock_quantity', 'updated_at'])
        _create_stock_movement(
            inventory,
            movement_type=StockMovement.TYPE_RELEASE,
            source=StockMovement.SOURCE_ORDER,
            quantity_change=quantity,
            quantity_before=before,
            quantity_after=inventory.stock_quantity,
            reason=f'Order stock release for variant {variant.sku}',
            reference=reference,
        )

    if backorder_quantity > 0:
        inventory = next((item for item in inventories if item.allow_backorder), None)
        if inventory is not None:
            if movement_inventory is None:
                movement_inventory = inventory
            before = inventory.stock_quantity
            inventory.max_backorder_quantity += backorder_quantity
            inventory.save(update_fields=['max_backorder_quantity', 'updated_at'])
            _create_stock_movement(
                inventory,
                movement_type=StockMovement.TYPE_RELEASE,
                source=StockMovement.SOURCE_ORDER,
                quantity_change=backorder_quantity,
                quantity_before=before,
                quantity_after=inventory.stock_quantity,
                reason=f'Order backorder release for variant {variant.sku}',
                reference=reference,
            )

    variant._clear_inventory_cache()
    variant.save()


@transaction.atomic
def commit_order_inventory(order):
    locked_order = Order.objects.select_for_update().get(pk=order.pk)
    if locked_order.inventory_committed:
        order.inventory_committed = True
        return
    list(Variant.objects.select_for_update().filter(pk__in=order.items.values_list('variant_id', flat=True)).order_by('pk'))
    from apps.prescriptions.dispensing import dispensing_error
    from apps.prescriptions.models import PrescriptionItem
    for item in order.items.select_related('variant'):
        if item.prescription_item_id:
            authorization = PrescriptionItem.objects.select_for_update(of=('self',)).select_related('prescription', 'product').get(pk=item.prescription_item_id)
            error = dispensing_error(authorization, item.variant, item.quantity, exclude_order=order)
            if error:
                raise ValueError(error)
        elif item.variant and item.variant.requires_prescription:
            raise ValueError('Prescription authorization is missing from this order item.')
        if not item.variant_id:
            raise ValueError(f'Order item {item.product_name} is missing a variant. Product-level inventory is disabled.')
        variant = Variant.objects.select_for_update().get(pk=item.variant_id)
        allocation = _consume_variant_inventory(
            variant,
            item.quantity,
            reference=order.order_number,
        )
        item.allocated_branch_quantity = allocation.branch_quantity
        item.allocated_warehouse_quantity = allocation.warehouse_quantity
        item.allocated_backorder_quantity = allocation.backorder_quantity
        item.inventory_allocations = allocation.inventory_rows
        item.save(update_fields=[
            'allocated_branch_quantity',
            'allocated_warehouse_quantity',
            'allocated_backorder_quantity',
            'inventory_allocations',
        ])

    order.inventory_committed = True
    Order.objects.filter(pk=order.pk).update(inventory_committed=True)


@transaction.atomic
def release_order_inventory(order):
    locked_order = Order.objects.select_for_update().get(pk=order.pk)
    if not locked_order.inventory_committed:
        order.inventory_committed = False
        return
    for item in order.items.select_related('variant'):
        if not item.variant_id:
            raise ValueError(f'Order item {item.product_name} is missing a variant. Product-level inventory is disabled.')
        variant = Variant.objects.select_for_update().get(pk=item.variant_id)
        _release_variant_inventory(
            variant,
            inventory_allocations=item.inventory_allocations,
            branch_quantity=item.allocated_branch_quantity,
            warehouse_quantity=item.allocated_warehouse_quantity,
            backorder_quantity=item.allocated_backorder_quantity,
            reference=order.order_number,
        )
        item.allocated_branch_quantity = 0
        item.allocated_warehouse_quantity = 0
        item.allocated_backorder_quantity = 0
        item.inventory_allocations = []
        item.save(update_fields=[
            'allocated_branch_quantity',
            'allocated_warehouse_quantity',
            'allocated_backorder_quantity',
            'inventory_allocations',
        ])

    order.inventory_committed = False
    Order.objects.filter(pk=order.pk).update(inventory_committed=False)
