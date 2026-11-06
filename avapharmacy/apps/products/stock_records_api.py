"""Store/batch stock records belonging to one exact sellable product."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.accounts.permissions import IsAdminOrInventoryStaff
from .models import Product, Variant, Store, StoreVariantListing, VariantInventory, StockMovement
from .admin_cache import invalidate_admin_catalog


class StockInput(serializers.Serializer):
    store_id = serializers.PrimaryKeyRelatedField(queryset=Store.objects.filter(is_active=True), required=False, source='store')
    batch_number = serializers.CharField(max_length=80, required=False, allow_blank=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=0)
    low_stock_threshold = serializers.IntegerField(min_value=0, required=False)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


def row_data(row):
    return {'id': row.pk, 'store_id': row.store_listing.store_id if row.store_listing_id else None,
        'store': row.store_listing.store.name if row.store_listing_id else row.source_name or row.location,
        'batch_number': row.batch_number, 'expiry_date': row.expiry_date, 'quantity': row.stock_quantity,
        'low_stock_threshold': row.low_stock_threshold, 'status': row.effective_status,
        'product_id': row.variant.product_id, 'product_name': row.variant.product.name, 'sku': row.variant.sku,
        'strength': row.variant.strength, 'pack_size': row.variant.pack_size,
        'created_at': row.created_at, 'updated_at': row.updated_at,
        'added_by': (row.created_by.full_name or row.created_by.email) if row.created_by_id else None,
        'updated_by': (row.updated_by.full_name or row.updated_by.email) if row.updated_by_id else None,
        'read_only': row.location == Product.STOCK_WAREHOUSE or row.is_pos_synced}



class ProductStockRecordsView(APIView):
    permission_classes = [IsAdminOrInventoryStaff]

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        rows = VariantInventory.objects.filter(variant__product=product).select_related('store_listing__store', 'variant__product', 'created_by', 'updated_by').order_by('-created_at', '-pk')
        data = [row_data(row) for row in rows]
        return Response({'product_id': product.pk, 'name': product.name, 'sku': product.sku,
            'total_quantity': sum(row['quantity'] for row in data), 'records': data})

    @transaction.atomic
    def post(self, request, pk):
        # Lock the item before resolving a store/batch, so concurrent receipts
        # cannot create duplicate rows or overwrite each other's quantities.
        variant = get_object_or_404(Variant.objects.select_for_update(), product_id=pk)
        serializer = StockInput(data=request.data); serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if 'store' not in data:
            raise serializers.ValidationError({'store_id': 'Select a store.'})
        if data['quantity'] <= 0:
            raise serializers.ValidationError({'quantity': 'Enter a received quantity greater than zero.'})
        listing, _ = StoreVariantListing.objects.get_or_create(variant=variant, store=data['store'], defaults={'price':variant.price})
        batch = data.get('batch_number', '').strip()
        row = VariantInventory.objects.select_for_update().filter(variant=variant, store_listing=listing, batch_number=batch).first()
        if row and row.location == Product.STOCK_WAREHOUSE:
            raise serializers.ValidationError({'quantity': 'This record is POS-synced. Receive stock through the POS.'})
        before = row.stock_quantity if row else 0
        if row and data.get('expiry_date') and row.expiry_date and row.expiry_date != data['expiry_date']:
            raise serializers.ValidationError({'expiry_date': 'This store/batch already has a different expiry. Correct that record or use the correct batch number.'})
        if not row:
            row = VariantInventory(variant=variant, store_listing=listing, location=Product.STOCK_BRANCH, batch_number=batch, created_by=request.user)
        row.stock_quantity = before + data['quantity']
        if 'low_stock_threshold' in data: row.low_stock_threshold = data['low_stock_threshold']
        if data.get('expiry_date') is not None: row.expiry_date = data['expiry_date']
        row.updated_by = request.user
        row.save()
        self.movement(request, row, before, data.get('reason') or 'Stock received', StockMovement.TYPE_STOCK_IN)
        return Response(row_data(row), status=201)

    @staticmethod
    def movement(request, row, before, reason, movement_type=StockMovement.TYPE_ADJUSTMENT):
        delta = row.stock_quantity - before
        if delta:
            StockMovement.objects.create(variant_inventory=row, movement_type=movement_type,
                source=StockMovement.SOURCE_MANUAL, batch_number=row.batch_number, quantity_change=delta,
                quantity_before=before, quantity_after=row.stock_quantity, reason=reason, created_by=request.user,
                destination_location=row.location if delta > 0 else '', source_location=row.location if delta < 0 else '')
        invalidate_admin_catalog()


class ProductStockRecordDetailView(ProductStockRecordsView):
    http_method_names = ['patch', 'options']

    @transaction.atomic
    def patch(self, request, pk, stock_pk):
        get_object_or_404(Variant.objects.select_for_update(), product_id=pk)
        row = get_object_or_404(VariantInventory.objects.select_for_update(of=('self',)).select_related('store_listing__store', 'variant__product', 'created_by', 'updated_by'), pk=stock_pk, variant__product_id=pk)
        if row.location == Product.STOCK_WAREHOUSE:
            raise serializers.ValidationError({'quantity': 'This record is POS-synced and cannot be changed here.'})
        serializer = StockInput(data=request.data); serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if 'store' in data or ('batch_number' in data and data['batch_number'].strip() != row.batch_number):
            raise serializers.ValidationError({'batch_number': 'Create a separate stock record for another store or batch.'})
        before = row.stock_quantity; row.stock_quantity = data['quantity']
        if 'expiry_date' in data: row.expiry_date = data['expiry_date']
        if 'low_stock_threshold' in data: row.low_stock_threshold = data['low_stock_threshold']
        row.updated_by = request.user
        row.save(); self.movement(request, row, before, data.get('reason') or 'Stock count corrected')
        return Response(row_data(row))


class AllStockRecordsView(ProductStockRecordsView):
    http_method_names = ['get', 'options']

    def get(self, request):
        from django.db.models import Q, F, Sum, Count
        from django.core.paginator import Paginator, EmptyPage
        rows = VariantInventory.objects.select_related('store_listing__store', 'variant__product', 'created_by', 'updated_by')
        stats = rows.aggregate(total=Count('pk'), units=Sum('stock_quantity'), products=Count('variant__product', distinct=True), stores=Count('store_listing__store', distinct=True))
        search = request.query_params.get('search', '').strip()
        if search:
            rows = rows.filter(Q(variant__product__name__icontains=search)|Q(variant__sku__icontains=search)|Q(batch_number__icontains=search)|Q(store_listing__store__name__icontains=search))
        store = request.query_params.get('store')
        if store:
            if not store.isdecimal(): raise serializers.ValidationError({'store':'Select a valid store.'})
            rows=rows.filter(store_listing__store_id=store)
        rx=request.query_params.get('requires_prescription')
        if rx in ['true','false']: rows=rows.filter(variant__requires_prescription=rx=='true')
        status=request.query_params.get('status')
        if status=='in_stock': rows=rows.filter(stock_quantity__gt=F('low_stock_threshold'))
        elif status=='low_stock': rows=rows.filter(stock_quantity__gt=0,stock_quantity__lte=F('low_stock_threshold'))
        elif status=='out_of_stock': rows=rows.filter(stock_quantity=0)
        try: page_number=max(1,int(request.query_params.get('page',1)))
        except ValueError: raise serializers.ValidationError({'page':'Enter a valid page.'})
        paginator=Paginator(rows.order_by('-created_at','-pk'),20)
        page=paginator.get_page(page_number)
        return Response({'name':'Stock by store & batch','sku':'','total_quantity':stats['units'] or 0,
            'total_records':paginator.count,'page':page.number,'pages':paginator.num_pages,'stats':stats,
            'records':[row_data(row) for row in page.object_list]})
