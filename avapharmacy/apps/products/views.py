"""
API views for the products app.

Provides public catalog endpoints (categories, brands, products, reviews,
wishlist, banners, CMS blocks, promotions) and admin-only endpoints for full
CRUD on all catalog entities, inventory adjustment, and CMS management.
"""
from django.conf import settings
from django.http import Http404
from django.db import models
from django.db.models import Avg, Count, Exists, F, OuterRef, Q, Sum, Window
from django.db.models import Prefetch
from django.db.models.functions import Coalesce
from django.db.models.functions.window import RowNumber
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, permissions, serializers as drf_serializers, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminOrInventoryStaff, IsAdminUser
from apps.accounts.utils import log_admin_action
from avapharmacy.security import verify_hmac_signature

from .filters import ProductFilter, VariantInventoryFilter
from .inventory_sync import (
    InventoryTargetError,
    apply_inventory_sync,
    normalize_inventory_payload,
    resolve_variant_inventory_target,
)
from .models import Banner, Brand, Category, CMSBlock, FAQ, HealthConcern, Product, ProductImage, Promotion, StockMovement, Store, StoreVariantListing, Subcategory, Variant, VariantInventory, VariantReview, Wishlist, annotate_product_inventory, annotate_variant_inventory
from .pos import refresh_pos_inventory_for_products, refresh_pos_inventory_for_variants
from .serializers import (
    AdminProductSerializer,
    BannerSerializer,
    BrandSerializer,
    CMSBlockSerializer,
    FAQSerializer,
    CategorySerializer,
    HealthConcernSerializer,
    CatalogCategorySerializer,
    ProductDetailSerializer,
    ProductImageSerializer,
    ProductListSerializer,
    AdminInventoryItemSerializer,
    AdminStoreVariantListingSerializer,
    AdminStoreSerializer,
    PublicInventoryItemSerializer,
    VariantReviewSerializer,
    AdminVariantSerializer,
    VariantSerializer,
    PromotionSerializer,
    StockMovementSerializer,
    StoreSerializer,
    SubcategorySerializer,
    WishlistSerializer,
)
from .services import get_active_promotions_queryset


def _coerce_non_negative_int(value):
    if isinstance(value, bool) or value is None:
        raise ValueError('Quantity must be a non-negative integer.')
    parsed = int(value)
    if parsed < 0 or str(parsed) != str(value).strip():
        raise ValueError('Quantity must be a non-negative integer.')
    return parsed


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'true', '1', 'yes', 'on'}


def _inventory_prefetch(lookup='inventories', *, public=False):
    queryset = VariantInventory.objects.select_related('store_listing__store')
    if public:
        queryset = queryset.filter(
            Q(store_listing__isnull=True)
            | Q(store_listing__is_active=True, store_listing__store__is_active=True)
        )
    return Prefetch(lookup, queryset=queryset)


def _inventory_selector(item, *, prefix=''):
    listing_key = f'{prefix}store_listing_id' if prefix else 'store_listing_id'
    store_key = f'{prefix}store_code' if prefix else 'store_code'
    batch_key = f'{prefix}batch_number' if prefix else 'batch_number'
    return {
        'store_listing_id': item.get(listing_key, item.get('store_listing_id')),
        'store_code': item.get(store_key, item.get('store_code', '')),
        'batch_number': item.get(batch_key, item.get('batch_number', '')),
    }


def _invalid_inventory_result(item, exc):
    return {
        'sku': item.get('sku'),
        'product_id': item.get('product_id'),
        'variant_id': item.get('variant_id'),
        'code': getattr(exc, 'code', 'invalid_inventory_target'),
        'message': str(exc),
    }


def _resolve_or_create_inventory(variant, location, item, *, prefix=''):
    selector = _inventory_selector(item, prefix=prefix)
    inventory, listing = resolve_variant_inventory_target(
        variant,
        location=location,
        **selector,
    )
    if inventory is None:
        inventory = VariantInventory.objects.create(
            variant=variant,
            store_listing=listing,
            location=location,
            batch_number=selector['batch_number'],
        )
    return inventory


def annotate_product_reviews(queryset):
    return queryset.annotate(
        approved_average_rating=models.Avg('variants__reviews__rating', filter=models.Q(variants__reviews__is_approved=True, variants__is_active=True)),
        approved_review_count=models.Count('variants__reviews', filter=models.Q(variants__reviews__is_approved=True, variants__is_active=True), distinct=True),
    )


def annotate_product_units_sold(queryset):
    return queryset.annotate(
        units_sold=Sum(
            'variants__order_items__quantity',
            filter=Q(
                variants__order_items__order__payment_status='paid',
            ) & ~Q(
                variants__order_items__order__status__in=['draft', 'cancelled', 'refunded']
            ),
        )
    )


def annotate_variant_reviews(queryset):
    # A separate aggregation avoids multiplying stock rows by the review count.
    approved = VariantReview.objects.filter(variant_id=OuterRef('pk'), is_approved=True).order_by().values('variant_id')
    return queryset.annotate(
        approved_average_rating=Coalesce(
            models.Subquery(approved.annotate(value=Avg('rating')).values('value')[:1], output_field=models.FloatField()),
            models.Value(0.0),
        ),
        approved_review_count=Coalesce(
            models.Subquery(approved.annotate(value=Count('pk')).values('value')[:1]),
            models.Value(0),
        ),
    )


def public_product_queryset():
    return Product.objects.filter(is_active=True).filter(
        Q(brand__isnull=True) | Q(brand__is_active=True)
    )


def public_variant_queryset():
    return Variant.objects.filter(
        is_active=True,
        product__is_active=True,
    ).filter(
        Q(product__brand__isnull=True) | Q(product__brand__is_active=True)
    ).prefetch_related(_inventory_prefetch(public=True))


def annotate_product_variant_catalog(queryset):
    return queryset.annotate(
        price=Coalesce(
            models.Min('variants__price', filter=models.Q(variants__is_active=True)),
            models.Value(0),
            output_field=models.DecimalField(max_digits=10, decimal_places=2),
        )
    )


def _product_availability_error(product, requested_quantity):
    if not product.is_active:
        return f'{product.name} is no longer active.'
    parent_product = getattr(product, 'product', None)
    if parent_product is not None and not parent_product.is_active:
        return f'{parent_product.name} is no longer active.'
    if isinstance(product, Product) and product.uses_variant_inventory:
        return f'Select a product variant for {product.name} before adding it to cart.'
    inventory_values_getter = getattr(product, '_get_inventory_values', None)
    if callable(inventory_values_getter):
        inventory_values = inventory_values_getter()
        stock_quantity = inventory_values.get('stock_quantity', 0)
        allow_backorder = inventory_values.get('allow_backorder', False)
    else:
        stock_quantity = getattr(product, 'stock_quantity', 0)
        allow_backorder = getattr(product, 'allow_backorder', False)
    available_quantity = getattr(product, 'available_quantity', stock_quantity)
    if requested_quantity <= stock_quantity:
        return None
    if allow_backorder and requested_quantity <= available_quantity:
        return None
    if stock_quantity == 0 and not allow_backorder:
        return f'{product.name} is out of stock.'
    return f'{product.name} only has {available_quantity} unit(s) available.'


class PromotionContextMixin:
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['active_promotions'] = list(get_active_promotions_queryset())
        return context


class ProductListPagination(PageNumberPagination):
    page_size_query_param = 'page_size'
    max_page_size = 200


class CategoryListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CategorySerializer
    pagination_class = None

    def get_queryset(self):
        public_stock = VariantInventory.objects.filter(
            variant_id=OuterRef('pk'),
            stock_quantity__gt=0,
        ).filter(
            Q(store_listing__isnull=True)
            | Q(store_listing__is_active=True, store_listing__store__is_active=True)
        )
        navigation_variants = (
            Variant.objects.filter(
                is_active=True,
                product__is_active=True,
            )
            .filter(Q(product__brand__isnull=True) | Q(product__brand__is_active=True))
            .annotate(has_public_stock=Exists(public_stock))
            .filter(has_public_stock=True)
            .annotate(
                navigation_rank=Window(
                    expression=RowNumber(),
                    partition_by=[F('category_id')],
                    order_by=[F('requires_prescription').asc(), F('name').asc(), F('pk').asc()],
                )
            )
            .filter(navigation_rank__lte=48)
            .select_related('product')
            .order_by('category_id', 'requires_prescription', 'name', 'pk')
        )
        return Category.objects.filter(is_active=True).prefetch_related(
            Prefetch('subcategories', queryset=Subcategory.objects.filter(is_active=True).order_by('name')),
            Prefetch('variants', queryset=navigation_variants, to_attr='navigation_variants'),
        )


class BrandListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = BrandSerializer
    queryset = Brand.objects.filter(is_active=True)


class StoreListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = StoreSerializer
    queryset = Store.objects.filter(is_active=True)


class HealthConcernListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = HealthConcernSerializer
    queryset = HealthConcern.objects.filter(is_active=True)


class CatalogCategoryListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CatalogCategorySerializer

    def get_queryset(self):

        return Category.objects.filter(is_active=True).prefetch_related(
            Prefetch('subcategories', queryset=Subcategory.objects.filter(is_active=True).order_by('name'))
        )


class ProductListView(PromotionContextMixin, generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PublicInventoryItemSerializer
    pagination_class = ProductListPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = VariantInventoryFilter
    search_fields = ['name', 'product__name', 'product__brand__name', 'category__name', 'sku']
    ordering_fields = ['price', 'created_at', 'name', 'approved_average_rating']
    ordering = ['-created_at']

    def get_queryset(self):
        return annotate_variant_reviews(
            public_variant_queryset().filter(
                Q(category__isnull=True) | Q(category__is_active=True)
            ).select_related(
                'product',
                'product__brand',
                'category',
                'subcategory',
            ).prefetch_related(
                'health_concerns',
            )
        ).distinct()


class InventoryItemListView(PromotionContextMixin, generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PublicInventoryItemSerializer

    def get_queryset(self):
        queryset = annotate_variant_reviews(
            public_variant_queryset().filter(
                Q(category__isnull=True) | Q(category__is_active=True)
            ).select_related(
                'product',
                'product__brand',
                'category',
                'subcategory',
            ).prefetch_related(
                'health_concerns',
            )
        )

        params = self.request.query_params
        category = (params.get('category') or '').strip()
        subcategory = (params.get('subcategory') or '').strip()
        brand = (params.get('brand') or '').strip()
        health_concern = (params.get('health_concern') or '').strip()
        store = (params.get('store') or '').strip()
        query = (params.get('search') or params.get('q') or '').strip()
        requires_prescription = params.get('requires_prescription')
        min_price = params.get('min_price')
        max_price = params.get('max_price')
        ordering = (params.get('ordering') or '-created_at').strip()

        if category:
            queryset = queryset.filter(category__slug=category)
        if subcategory:
            queryset = queryset.filter(subcategory__slug=subcategory)
        if brand:
            queryset = queryset.filter(product__brand__slug=brand)
        if health_concern:
            queryset = queryset.filter(health_concerns__slug=health_concern)
        if store:
            queryset = queryset.filter(
                inventories__store_listing__store__code=store,
                inventories__store_listing__store__is_active=True,
                inventories__store_listing__is_active=True,
            )
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(product__name__icontains=query)
                | Q(sku__icontains=query)
                | Q(short_description__icontains=query)
                | Q(product__brand__name__icontains=query)
            )
        if requires_prescription is not None and str(requires_prescription).strip() != '':
            wants_prescription = str(requires_prescription).strip().lower() in {'1', 'true', 'yes', 'on'}
            queryset = queryset.filter(requires_prescription=wants_prescription)
        if min_price not in (None, ''):
            try:
                queryset = queryset.filter(price__gte=min_price)
            except (TypeError, ValueError):
                pass
        if max_price not in (None, ''):
            try:
                queryset = queryset.filter(price__lte=max_price)
            except (TypeError, ValueError):
                pass

        ordering_map = {
            'price': 'price',
            '-price': '-price',
            'name': 'name',
            '-name': '-name',
            'created_at': 'created_at',
            '-created_at': '-created_at',
        }
        queryset = queryset.order_by(ordering_map.get(ordering, '-created_at'), 'pk')
        return queryset.distinct()


class FeaturedProductListView(PromotionContextMixin, generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductListSerializer

    def get_queryset(self):
        queryset = annotate_product_variant_catalog(public_product_queryset().prefetch_related(
            Prefetch(
                'variants',
                queryset=Variant.objects.select_related('product__brand', 'category', 'subcategory').prefetch_related(_inventory_prefetch(public=True), 'health_concerns').order_by('sort_order', 'name', 'pk'),
            )
        )).exclude(
            variants__is_active=True,
            variants__requires_prescription=True,
        ).distinct()
        queryset = annotate_product_units_sold(queryset)
        queryset = annotate_product_reviews(queryset)
        minimum_rating = getattr(settings, 'FEATURED_PRODUCT_MIN_RATING', 4)
        highly_rated_queryset = queryset.filter(
            approved_review_count__gt=0,
            approved_average_rating__gte=minimum_rating,
        )
        if highly_rated_queryset.exists():
            return highly_rated_queryset.order_by(
                models.F('approved_average_rating').desc(nulls_last=True),
                models.F('approved_review_count').desc(nulls_last=True),
                models.F('units_sold').desc(nulls_last=True),
                '-created_at',
            )
        return queryset.order_by(
            models.F('units_sold').desc(nulls_last=True),
            models.F('approved_average_rating').desc(nulls_last=True),
            models.F('approved_review_count').desc(nulls_last=True),
            '-created_at',
        )


class ProductDetailView(PromotionContextMixin, generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductDetailSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return annotate_product_variant_catalog(
            annotate_product_reviews(
                public_product_queryset().prefetch_related(
                    'gallery',
                    Prefetch(
                        'variants',
                        queryset=annotate_variant_reviews(Variant.objects.select_related('product__brand', 'category', 'subcategory').prefetch_related(_inventory_prefetch(public=True), 'health_concerns').order_by('sort_order', 'name', 'pk')),
                    ),
                )
            )
        )


class AdminCategoryListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = CatalogCategorySerializer
    queryset = Category.objects.prefetch_related(
        Prefetch('subcategories', queryset=Subcategory.objects.order_by('name'))
    )
    filterset_fields = ['is_active']
    search_fields = ['name', 'slug']


    def perform_create(self, serializer):
        category = serializer.save(created_by=self.request.user, updated_by=self.request.user)
        log_admin_action(
            self.request.user,
            action='category_created',
            entity_type='category',
            entity_id=category.id,
            message=f'Created category {category.name}',
        )


class AdminCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = CatalogCategorySerializer
    queryset = Category.objects.prefetch_related(
        Prefetch('subcategories', queryset=Subcategory.objects.order_by('name'))
    )

    def perform_update(self, serializer):
        category = serializer.save(updated_by=self.request.user)
        log_admin_action(
            self.request.user,
            action='category_updated',
            entity_type='category',
            entity_id=category.id,
            message=f'Updated category {category.name}',
        )


class AdminSubCategoryListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = SubcategorySerializer
    search_fields = ['name', 'slug', 'category__name']
    filterset_fields = ['is_active', 'category']

    def get_queryset(self):
        return Subcategory.objects.select_related('category')

    def perform_create(self, serializer):
        sub = serializer.save(created_by=self.request.user, updated_by=self.request.user)
        log_admin_action(self.request.user, action='subcategory_created', entity_type='subcategory', entity_id=sub.id, message=f'Created subcategory {sub.name} under {sub.category.name}')


class AdminSubCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = SubcategorySerializer
    queryset = Subcategory.objects.select_related('category')

    def perform_update(self, serializer):
        sub = serializer.save(updated_by=self.request.user)
        log_admin_action(self.request.user, action='subcategory_updated', entity_type='subcategory', entity_id=sub.id, message=f'Updated subcategory {sub.name}')


class AdminBrandListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = BrandSerializer
    queryset = Brand.objects.all()
    filterset_fields = ['is_active']
    search_fields = ['name', 'slug']

    def perform_create(self, serializer):
        brand = serializer.save(created_by=self.request.user, updated_by=self.request.user)
        log_admin_action(
            self.request.user,
            action='brand_created',
            entity_type='brand',
            entity_id=brand.id,
            message=f'Created brand {brand.name}',
        )


class AdminBrandDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = BrandSerializer
    queryset = Brand.objects.all()

    def perform_update(self, serializer):
        brand = serializer.save(updated_by=self.request.user)
        log_admin_action(
            self.request.user,
            action='brand_updated',
            entity_type='brand',
            entity_id=brand.id,
            message=f'Updated brand {brand.name}',
        )


class AdminStoreListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = AdminStoreSerializer
    queryset = Store.objects.all()
    filterset_fields = ['is_active', 'city']
    search_fields = ['name', 'code', 'city']


class AdminStoreDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = AdminStoreSerializer
    queryset = Store.objects.all()


class AdminStoreVariantListingListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = AdminStoreVariantListingSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['store', 'variant', 'is_active', 'status', 'review_status']
    search_fields = [
        'store__name', 'store__code', 'variant__name', 'variant__sku',
        'variant__product__name', 'external_product_id',
    ]
    ordering_fields = ['updated_at', 'price', 'store__name', 'variant__name']
    ordering = ['store__name', 'variant__name']
    queryset = StoreVariantListing.objects.select_related(
        'store', 'variant', 'variant__product'
    )


class AdminStoreVariantListingDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = AdminStoreVariantListingSerializer
    queryset = StoreVariantListing.objects.select_related(
        'store', 'variant', 'variant__product'
    )


class AdminProductListCreateView(PromotionContextMixin, generics.ListCreateAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = AdminProductSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'variants__sku']
    ordering_fields = ['created_at', 'price', 'name']
    ordering = ['-created_at']

    def get_queryset(self):
        return annotate_product_variant_catalog(
            annotate_product_reviews(
                Product.objects.all().prefetch_related(
                    Prefetch(
                        'variants',
                        queryset=Variant.objects.select_related('product__brand', 'category', 'subcategory').prefetch_related(_inventory_prefetch(), 'health_concerns').order_by('sort_order', 'name', 'pk'),
                    ),
                )
            )
        )

    def perform_create(self, serializer):
        product = serializer.save(created_by=self.request.user, updated_by=self.request.user)
        log_admin_action(
            self.request.user,
            action='product_created',
            entity_type='product',
            entity_id=product.id,
            message=f'Created product {product.name}',
            metadata={'sku': product.get_display_sku()},
        )


class AdminProductFormMetaView(APIView):
    permission_classes = [IsAdminOrInventoryStaff]

    def get(self, request):
        strategy = str(getattr(settings, 'POS_LINK_STRATEGY', 'sku_or_pos_id') or 'sku_or_pos_id').strip().lower()
        return Response({
            'pos_link_strategy': strategy,
            'requires_pos_product_id': strategy in {'pos_product_id', 'barcode_and_pos_id'},
            'requires_barcode': False,
            'accepts_sku': False,
            'accepts_barcode': False,
        })


class AdminPosProductOptionListView(APIView):
    permission_classes = [IsAdminOrInventoryStaff]

    def get(self, request):
        options = []
        seen = set()

        variants = Variant.objects.exclude(pos_product_id='').select_related('product').order_by('product__name', 'name')
        for variant in variants:
            pos_product_id = (variant.pos_product_id or '').strip()
            if not pos_product_id or pos_product_id in seen:
                continue
            seen.add(pos_product_id)
            options.append({
                'pos_product_id': pos_product_id,
                'label': f'{variant.product.name} · {variant.name}',
                'product_name': variant.product.name,
                'variant_name': variant.name,
                'sku': variant.sku,
                'source': 'variant',
            })

        products = Product.objects.exclude(pos_product_id='').order_by('name')
        for product in products:
            pos_product_id = (product.pos_product_id or '').strip()
            if not pos_product_id or pos_product_id in seen:
                continue
            seen.add(pos_product_id)
            options.append({
                'pos_product_id': pos_product_id,
                'label': product.name,
                'product_name': product.name,
                'variant_name': '',
                'sku': product.get_display_sku(),
                'source': 'product',
            })

        return Response(options)


class AdminProductDetailView(PromotionContextMixin, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = AdminProductSerializer
    queryset = annotate_product_reviews(
        annotate_product_variant_catalog(Product.objects.all()).prefetch_related(
            'gallery',
            Prefetch(
                'variants',
                queryset=Variant.objects.select_related('product__brand', 'category', 'subcategory').prefetch_related(_inventory_prefetch(), 'health_concerns').order_by('sort_order', 'name', 'pk'),
            ),
        )
    )

    def perform_update(self, serializer):
        product = serializer.save(updated_by=self.request.user)
        log_admin_action(
            self.request.user,
            action='product_updated',
            entity_type='product',
            entity_id=product.id,
            message=f'Updated product {product.name}',
            metadata={'sku': product.get_display_sku()},
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {'detail': 'Products cannot be deleted. Deactivate the product instead.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class ProductReviewListCreateView(generics.ListCreateAPIView):
    serializer_class = VariantReviewSerializer

    def _resolve_target_variant(self):
        if 'variant_pk' in self.kwargs:
            return public_variant_queryset().filter(pk=self.kwargs['variant_pk']).select_related('product').first()
        raw_pk = self.kwargs['pk']
        product = public_product_queryset().filter(pk=raw_pk).prefetch_related('variants').first()
        if product is not None:
            variant = product.get_representative_variant()
            if variant is not None:
                return variant
        return public_variant_queryset().filter(pk=raw_pk).select_related('product').first()

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        variant = self._resolve_target_variant()
        if variant is None:
            return VariantReview.objects.none()
        return VariantReview.objects.filter(
            variant_id=variant.id, is_approved=True
        ).select_related('user', 'variant')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from apps.orders.models import Order

        target_variant = self._resolve_target_variant()
        if target_variant is None:
            return Response({'detail': 'Variant not found.'}, status=status.HTTP_404_NOT_FOUND)
        variant_id = target_variant.id
        has_delivered_order = Order.objects.filter(
            customer=request.user,
            status=Order.STATUS_DELIVERED,
            items__variant_id=variant_id,
        ).exists()
        if not has_delivered_order:
            return Response(
                {'detail': 'You can review this variant after it has been delivered to you.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        review, created = VariantReview.objects.update_or_create(
            variant_id=variant_id,
            user=request.user,
            defaults={
                'rating': serializer.validated_data['rating'],
                'comment': serializer.validated_data.get('comment', ''),
                'is_approved': True,
            },
        )
        output = self.get_serializer(review)
        return Response(output.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class WishlistView(generics.ListCreateAPIView):
    serializer_class = WishlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Wishlist.objects.filter(
            user=self.request.user,
            variant__is_active=True,
            variant__product__is_active=True,
        ).filter(
            Q(variant__product__brand__isnull=True) | Q(variant__product__brand__is_active=True)
        ).select_related(
            'variant',
            'variant__product__brand',
            'variant__category',
            'variant__subcategory',
            'variant__product',
        ).prefetch_related(
            _inventory_prefetch('variant__inventories'),
            _inventory_prefetch('variant__product__variants__inventories'),
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        payload = request.data.copy()
        variant_id = payload.get('variant_id')
        if not variant_id:
            product_id = payload.get('product_id')
            if product_id:
                product = public_product_queryset().filter(pk=product_id).prefetch_related('variants').first()
                variant = product.get_representative_variant() if product else None
                variant_id = variant.id if variant else None
        if not variant_id:
            return Response({'detail': 'variant_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not public_variant_queryset().filter(pk=variant_id).exists():
            return Response({'detail': 'Variant not found.'}, status=status.HTTP_404_NOT_FOUND)
        payload['variant_id'] = variant_id
        if Wishlist.objects.filter(user=request.user, variant_id=variant_id).exists():
            return Response({'detail': 'Already in wishlist.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class WishlistItemDeleteView(generics.DestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user)


class WishlistItemMoveToCartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            wishlist_item = Wishlist.objects.select_related('variant', 'variant__product').get(pk=pk, user=request.user)
        except Wishlist.DoesNotExist:
            return Response({'detail': 'Wishlist item not found.'}, status=status.HTTP_404_NOT_FOUND)

        variant = wishlist_item.variant
        if variant.requires_prescription:
            return Response(
                {'detail': 'This product requires an approved prescription before it can be moved to cart.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        quantity = request.data.get('quantity', 1)
        try:
            quantity = int(quantity)
            if quantity < 1:
                return Response({'quantity': 'Must be at least 1.'}, status=status.HTTP_400_BAD_REQUEST)
        except (TypeError, ValueError):
            return Response({'quantity': 'Invalid quantity.'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.orders.models import Cart, CartItem
        cart, _ = Cart.objects.get_or_create(user=request.user)
        existing_item = CartItem.objects.filter(
            cart=cart,
            variant=variant,
            prescription_reference__isnull=True,
            prescription__isnull=True,
            prescription_item__isnull=True,
        ).first()
        requested_total = quantity + (existing_item.quantity if existing_item else 0)
        error = _product_availability_error(variant, requested_total)
        if error:
            return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)

        if existing_item:
            existing_item.quantity = requested_total
            existing_item.save(update_fields=['quantity'])
        else:
            CartItem.objects.create(cart=cart, variant=variant, quantity=quantity)
        wishlist_item.delete()
        return Response({'detail': 'Item moved to cart.'}, status=status.HTTP_200_OK)


class CartItemMoveToWishlistView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        from apps.orders.models import CartItem

        try:
            cart_item = CartItem.objects.select_related('cart', 'variant', 'variant__product').get(
                pk=pk,
                cart__user=request.user,
            )
        except CartItem.DoesNotExist:
            return Response({'detail': 'Cart item not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not public_variant_queryset().filter(pk=cart_item.variant_id).exists():
            return Response({'detail': 'Variant not found.'}, status=status.HTTP_404_NOT_FOUND)
        Wishlist.objects.get_or_create(user=request.user, variant=cart_item.variant)
        cart_item.delete()
        return Response({'detail': 'Item moved to wishlist.'}, status=status.HTTP_200_OK)


class BannerListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = BannerSerializer

    def get_queryset(self):
        queryset = Banner.objects.filter(status='active').order_by('sort_order', '-created_at', 'pk')
        placement = self.request.query_params.get('placement')
        if placement:
            queryset = queryset.filter(placement=placement)
        return queryset


class CMSBlockListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CMSBlockSerializer

    def get_queryset(self):
        queryset = CMSBlock.objects.filter(is_active=True)
        placement = self.request.query_params.get('placement')
        if placement:
            queryset = queryset.filter(placement=placement)
        return queryset


class FAQListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = FAQSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = FAQ.objects.filter(is_published=True)
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__iexact=category.strip())
        return queryset


class AdminBannerListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = BannerSerializer
    queryset = Banner.objects.all()

    def perform_create(self, serializer):
        banner = serializer.save()
        log_admin_action(
            self.request.user,
            action='banner_created',
            entity_type='banner',
            entity_id=banner.id,
            message=f'Created banner {banner.title or banner.message[:40]}',
        )


class AdminBannerDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = BannerSerializer
    queryset = Banner.objects.all()

    def perform_update(self, serializer):
        banner = serializer.save()
        log_admin_action(
            self.request.user,
            action='banner_updated',
            entity_type='banner',
            entity_id=banner.id,
            message=f'Updated banner {banner.title or banner.message[:40]}',
        )


class PromotionListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PromotionSerializer

    def get_queryset(self):
        return get_active_promotions_queryset()


class AdminPromotionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = PromotionSerializer
    filterset_fields = ['status', 'scope', 'type', 'is_stackable']
    queryset = Promotion.objects.all()

    def perform_create(self, serializer):
        promotion = serializer.save()
        log_admin_action(
            self.request.user,
            action='promotion_created',
            entity_type='promotion',
            entity_id=promotion.id,
            message=f'Created promotion {promotion.title}',
        )


class AdminPromotionDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = PromotionSerializer
    queryset = Promotion.objects.all()

    def perform_update(self, serializer):
        promotion = serializer.save()
        log_admin_action(
            self.request.user,
            action='promotion_updated',
            entity_type='promotion',
            entity_id=promotion.id,
            message=f'Updated promotion {promotion.title}',
        )


class AdminHealthConcernListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = HealthConcernSerializer
    queryset = HealthConcern.objects.all()
    filter_backends = [SearchFilter]
    search_fields = ['name']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class AdminHealthConcernDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = HealthConcernSerializer
    queryset = HealthConcern.objects.all()

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class AdminProductImageListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = ProductImageSerializer

    def get_queryset(self):
        return ProductImage.objects.filter(product_id=self.kwargs['product_pk']).order_by('order', 'id')

    def perform_create(self, serializer):
        product = generics.get_object_or_404(Product, pk=self.kwargs['product_pk'])
        image = serializer.save(product=product)
        log_admin_action(
            self.request.user,
            action='product_image_created',
            entity_type='product_image',
            entity_id=image.id,
            message=f'Added image to {product.name}',
        )


class AdminProductImageDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = ProductImageSerializer

    def get_queryset(self):
        return ProductImage.objects.filter(product_id=self.kwargs['product_pk'])


class AdminProductVariantListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = AdminVariantSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['product'] = generics.get_object_or_404(Product, pk=self.kwargs['product_pk'])
        return context

    def get_queryset(self):
        return Variant.objects.filter(product_id=self.kwargs['product_pk']).prefetch_related(_inventory_prefetch()).order_by('sort_order', 'name')

    def perform_create(self, serializer):
        product = generics.get_object_or_404(Product, pk=self.kwargs['product_pk'])
        variant = serializer.save(product=product)
        log_admin_action(
            self.request.user,
            action='variant_created',
            entity_type='variant',
            entity_id=variant.id,
            message=f'Created variant {variant.name} for {product.name}',
            metadata={'sku': variant.sku},
        )


class AdminProductVariantDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = AdminVariantSerializer

    def get_queryset(self):
        return Variant.objects.filter(product_id=self.kwargs['product_pk']).prefetch_related(_inventory_prefetch())


class AdminCMSBlockListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = CMSBlockSerializer
    queryset = CMSBlock.objects.all()
    filterset_fields = ['placement', 'is_active']
    search_fields = ['key', 'title', 'placement']

    def perform_create(self, serializer):
        block = serializer.save()
        log_admin_action(
            self.request.user,
            action='cms_block_created',
            entity_type='cms_block',
            entity_id=block.id,
            message=f'Created CMS block {block.key}',
        )


class AdminCMSBlockDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = CMSBlockSerializer
    queryset = CMSBlock.objects.all()

    def perform_update(self, serializer):
        block = serializer.save()
        log_admin_action(
            self.request.user,
            action='cms_block_updated',
            entity_type='cms_block',
            entity_id=block.id,
            message=f'Updated CMS block {block.key}',
        )


class AdminFAQListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = FAQSerializer
    queryset = FAQ.objects.all()
    filterset_fields = ['category', 'is_published']
    search_fields = ['category', 'question', 'answer']
    ordering_fields = ['category', 'sort_order', 'question', 'created_at', 'updated_at']

    def perform_create(self, serializer):
        faq = serializer.save()
        log_admin_action(
            self.request.user,
            action='faq_created',
            entity_type='faq',
            entity_id=faq.id,
            message=f'Created FAQ {faq.question}',
        )


class AdminFAQDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = FAQSerializer
    queryset = FAQ.objects.all()

    def perform_update(self, serializer):
        faq = serializer.save()
        log_admin_action(
            self.request.user,
            action='faq_updated',
            entity_type='faq',
            entity_id=faq.id,
            message=f'Updated FAQ {faq.question}',
        )

    def perform_destroy(self, instance):
        faq_id = instance.id
        question = instance.question
        instance.delete()
        log_admin_action(
            self.request.user,
            action='faq_deleted',
            entity_type='faq',
            entity_id=faq_id,
            message=f'Deleted FAQ {question}',
        )

class AdminInventoryListView(generics.ListAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = AdminInventoryItemSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = VariantInventoryFilter
    search_fields = ['name', 'sku', 'product__name', 'product__brand__name']
    pagination_class = ProductListPagination
    ordering_fields = ['updated_at', 'name', 'stock_quantity', 'branch_stock_quantity', 'warehouse_stock_quantity', 'price']
    ordering = ['name', 'pk']

    def get_queryset(self):
        queryset = annotate_variant_inventory(annotate_variant_reviews(
            Variant.objects.select_related(
                'product',
                'product__brand',
                'category',
                'subcategory',
            ).prefetch_related(
                _inventory_prefetch(),
                'health_concerns',
            )
        ))
        stock_bucket = self.request.query_params.get('stock_bucket')
        if stock_bucket == 'low':
            queryset = queryset.filter(is_active=True, stock_quantity__gt=0, stock_quantity__lte=models.F('low_stock_threshold'))
        elif stock_bucket == 'out':
            queryset = queryset.filter(is_active=True, stock_quantity=0, allow_backorder=False)
        elif stock_bucket == 'backorder':
            queryset = queryset.filter(is_active=True, stock_quantity=0, allow_backorder=True)
        return queryset.distinct()


class AdminInventoryPosRefreshView(APIView):
    """Manually refresh POS store stock for selected products."""

    permission_classes = [IsAdminOrInventoryStaff]

    def post(self, request):
        if not settings.POS_INVENTORY_LOOKUP_URL:
            return Response(
                {'error': {'code': 'pos_not_configured', 'message': 'POS inventory lookup is not configured.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_ids = request.data.get('product_ids', [])
        if not isinstance(raw_ids, list) or not raw_ids:
            return Response(
                {'error': {'code': 'validation_error', 'message': 'product_ids array is required.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            ids = [int(value) for value in raw_ids]
        except (TypeError, ValueError):
            return Response(
                {'error': {'code': 'validation_error', 'message': 'product_ids must be integers.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        products = list(Product.objects.filter(pk__in=ids).prefetch_related(
            Prefetch('variants', queryset=Variant.objects.prefetch_related(_inventory_prefetch(), 'health_concerns').order_by('sort_order', 'name', 'pk'))
        ))
        if not products:
            return Response({'updated': [], 'refreshed_ids': []})

        force = bool(request.data.get('force', True))
        refreshed = refresh_pos_inventory_for_products(products, force=force)

        serializer = ProductDetailSerializer(
            products,
            many=True,
            context={'request': request, 'active_promotions': []},
        )
        return Response({
            'updated': serializer.data,
            'refreshed_ids': [key for key, value in refreshed.items() if not value.get('error')],
            'invalid': [
                {'product_id': key, **value['error']}
                for key, value in refreshed.items() if value.get('error')
            ],
        })


class AdminInventoryVariantPosRefreshView(APIView):
    """Manually refresh POS-backed stock for selected variants."""

    permission_classes = [IsAdminOrInventoryStaff]

    def post(self, request):
        if not settings.POS_INVENTORY_LOOKUP_URL:
            return Response(
                {'error': {'code': 'pos_not_configured', 'message': 'POS inventory lookup is not configured.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_ids = request.data.get('variant_ids', [])
        if not isinstance(raw_ids, list) or not raw_ids:
            return Response(
                {'error': {'code': 'validation_error', 'message': 'variant_ids array is required.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            ids = [int(value) for value in raw_ids]
        except (TypeError, ValueError):
            return Response(
                {'error': {'code': 'validation_error', 'message': 'variant_ids must be integers.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        variants = list(Variant.objects.filter(pk__in=ids).select_related('product').prefetch_related(_inventory_prefetch()))
        if not variants:
            return Response({'updated': [], 'refreshed_ids': []})

        force = bool(request.data.get('force', True))
        refreshed = refresh_pos_inventory_for_variants(variants, force=force)
        serializer = AdminVariantSerializer(
            variants,
            many=True,
            context={'request': request},
        )
        return Response({
            'updated': serializer.data,
            'refreshed_ids': [key for key, value in refreshed.items() if not value.get('error')],
            'invalid': [
                {'variant_id': key, **value['error']}
                for key, value in refreshed.items() if value.get('error')
            ],
        })


class AdminInventoryAdjustView(APIView):
    permission_classes = [IsAdminOrInventoryStaff]

    def patch(self, request, pk):
        try:
            product = Product.objects.prefetch_related(
                Prefetch('variants', queryset=Variant.objects.prefetch_related(_inventory_prefetch()).order_by('sort_order', 'name', 'pk'))
            ).get(pk=pk)
        except Product.DoesNotExist:
            return Response({'detail': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {'detail': 'Product-level inventory is disabled. Adjust stock on variants instead.'},
            status=status.HTTP_400_BAD_REQUEST,
        )


class CatalogSummaryView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        featured_count = (
            annotate_product_units_sold(public_product_queryset())
            .filter(units_sold__gt=0)
            .count()
        )
        return Response({
            'products': public_product_queryset().count(),
            'featured_products': featured_count,
            'categories': Category.objects.filter(is_active=True).count(),
            'brands': Brand.objects.filter(is_active=True).count(),
            'low_stock_products': annotate_product_inventory(public_product_queryset()).filter(
                total_stock_quantity__gt=0,
                total_stock_quantity__lte=models.F('total_low_stock_threshold'),
            ).count(),
            'active_promotions': get_active_promotions_queryset().count(),
            'top_categories': list(
                Category.objects.filter(is_active=True)
                .annotate(product_count=Count(
                    'variants__product',
                    filter=Q(variants__product__is_active=True) & (
                        Q(variants__product__brand__isnull=True) | Q(variants__product__brand__is_active=True)
                    ),
                    distinct=True,
                ))
                .values('id', 'name', 'slug', 'product_count')[:6]
            ),
        })


class ProductDetailByIdView(PromotionContextMixin, generics.RetrieveAPIView):
    """Retrieve a product by its numeric primary key."""

    permission_classes = [permissions.AllowAny]
    serializer_class = ProductDetailSerializer

    def get_queryset(self):
        return annotate_product_variant_catalog(
            annotate_product_reviews(
                public_product_queryset().prefetch_related(
                    'gallery',
                    Prefetch(
                        'variants',
                        queryset=annotate_variant_reviews(Variant.objects.select_related('product__brand', 'category', 'subcategory').prefetch_related(_inventory_prefetch(public=True)).order_by('sort_order', 'name', 'pk')),
                    ),
                )
            )
        )

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        pk = self.kwargs.get(self.lookup_url_kwarg or self.lookup_field)
        product = queryset.filter(pk=pk).first()
        if product:
            self.check_object_permissions(self.request, product)
            return product

        variant = public_variant_queryset().filter(pk=pk).values('product_id').first()
        if variant:
            product = queryset.filter(pk=variant['product_id']).first()
            if product:
                self.check_object_permissions(self.request, product)
                return product

        raise Http404


class ProductSearchView(PromotionContextMixin, generics.ListAPIView):
    """Full-text product search with facets."""

    permission_classes = [permissions.AllowAny]
    serializer_class = ProductListSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'brand__name', 'sku', 'variants__short_description']
    ordering_fields = ['price', 'created_at', 'name']
    ordering = ['-created_at']

    def get_queryset(self):
        q = self.request.query_params.get('q', '').strip()
        qs = annotate_product_variant_catalog(
            annotate_product_reviews(
                public_product_queryset().prefetch_related(
                    Prefetch(
                        'variants',
                        queryset=Variant.objects.select_related('product__brand', 'category', 'subcategory').prefetch_related(_inventory_prefetch(public=True)).order_by('sort_order', 'name', 'pk'),
                    )
                )
            )
        )
        if q and len(q) >= 2:
            qs = qs.filter(
                Q(name__icontains=q) | Q(brand__name__icontains=q) | Q(sku__icontains=q) | Q(variants__short_description__icontains=q)
            )
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
        else:
            serializer = self.get_serializer(queryset, many=True)

        q = request.query_params.get('q', '')
        products_data = serializer.data

        # Build facets
        all_qs = self.get_queryset()
        category_facets = list(
            all_qs.values('variants__category__slug', 'variants__category__name')
            .annotate(count=Count('id'))
            .exclude(variants__category__isnull=True)
            .values('variants__category__slug', 'variants__category__name', 'count')[:10]
        )
        brand_facets = list(
            Brand.objects.filter(is_active=True, products__in=all_qs)
            .annotate(count=Count('products', filter=Q(products__in=all_qs), distinct=True))
            .filter(count__gt=0)
            .order_by('-count', 'name')[:10]
        )
        brand_facets_data = BrandSerializer(
            brand_facets,
            many=True,
            context=self.get_serializer_context(),
        ).data
        prices = list(all_qs.values_list('price', flat=True))
        price_range = {
            'min': min(prices, default=0),
            'max': max(prices, default=0),
        }

        response_data = {
            'query': q,
            'products': products_data,
            'facets': {
                'categories': [{'slug': f['variants__category__slug'], 'name': f['variants__category__name'], 'count': f['count']} for f in category_facets],
                'brands': [{**item, 'count': brand.count} for brand, item in zip(brand_facets, brand_facets_data)],
                'price_range': price_range,
            },
        }

        if page is not None:
            return self.get_paginated_response(response_data)
        return Response(response_data)


class ProductSuggestionsView(APIView):
    """Autocomplete suggestions for the search input."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if len(q) < 2:
            return Response({'suggestions': []})

        products = public_product_queryset().filter(
            Q(name__icontains=q) | Q(brand__name__icontains=q),
        ).prefetch_related(
            Prefetch(
                'variants',
                queryset=Variant.objects.select_related('product__brand', 'category', 'subcategory').prefetch_related(_inventory_prefetch(public=True)).order_by('sort_order', 'name', 'pk'),
            )
        ).distinct()[:5]

        categories = Category.objects.filter(
            Q(name__icontains=q),
            is_active=True,
        )[:3]

        suggestions = [
            {'text': p.name, 'type': 'product', 'id': p.id, 'slug': p.slug}
            for p in products
        ] + [
            {'text': c.name, 'type': 'category', 'slug': c.slug}
            for c in categories
        ]
        return Response({'suggestions': suggestions})


class ProductAvailabilityView(APIView):
    """Return real-time stock availability for a list of product IDs."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        raw = request.query_params.get('product_ids', '')
        try:
            ids = [int(x) for x in raw.split(',') if x.strip()]
        except (ValueError, TypeError):
            return Response({'error': {'code': 'validation_error', 'message': 'product_ids must be comma-separated integers.'}}, status=400)

        products = list(public_product_queryset().filter(pk__in=ids).prefetch_related(Prefetch(
            'variants',
            queryset=Variant.objects.prefetch_related(_inventory_prefetch(public=True)).order_by('sort_order', 'name', 'pk'),
        )))
        pos_refresh = refresh_pos_inventory_for_products(products)
        availability = []
        for product in products:
            pos_info = pos_refresh.get(product.id)
            if pos_info and pos_info.get('error'):
                pos_info = None
            pos_quantity = pos_info.get('quantity') if pos_info else None
            pos_stores = pos_info.get('stores', []) if pos_info else []
            availability.append({
                'product_id': product.id,
                'is_available': product.stock_quantity > 0 or product.allow_backorder,
                'stock_source': product.stock_source,
                'quantity': product.stock_quantity,
                'is_low_stock': 0 < product.stock_quantity <= product.low_stock_threshold,
                'pos_checked': bool(pos_info),
                'pos_quantity': pos_quantity,
                'pos_store_count': len(pos_stores) if isinstance(pos_stores, list) else 0,
            })
        return Response({'availability': availability})


class ProductAvailabilityDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        try:
            product = public_product_queryset().prefetch_related(Prefetch(
                'variants',
                queryset=Variant.objects.prefetch_related(
                    _inventory_prefetch(public=True)
                ).order_by('sort_order', 'name', 'pk'),
            )).get(pk=pk)
        except Product.DoesNotExist:
            return Response({'detail': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

        location_totals = {
            Product.STOCK_BRANCH: {'location': Product.STOCK_BRANCH, 'quantity': 0, 'allow_backorder': False, 'max_backorder_quantity': 0, 'next_restock_date': None},
            Product.STOCK_WAREHOUSE: {'location': Product.STOCK_WAREHOUSE, 'quantity': 0, 'allow_backorder': False, 'max_backorder_quantity': 0, 'next_restock_date': None},
        }
        store_totals = {}
        if product.uses_variant_inventory:
            for variant in product.get_active_variants():
                for inventory in variant.inventories.all():
                    row = location_totals[inventory.location]
                    row['quantity'] += inventory.stock_quantity
                    row['allow_backorder'] = row['allow_backorder'] or inventory.allow_backorder
                    row['max_backorder_quantity'] += inventory.max_backorder_quantity
                    if inventory.next_restock_date and (row['next_restock_date'] is None or inventory.next_restock_date < row['next_restock_date']):
                        row['next_restock_date'] = inventory.next_restock_date
                    if inventory.store_listing_id:
                        store = inventory.store_listing.store
                        store_row = store_totals.setdefault(store.code, {
                            'id': store.id,
                            'code': store.code,
                            'name': store.name,
                            'city': store.city,
                            'quantity': 0,
                        })
                        store_row['quantity'] += inventory.stock_quantity
        location_stock = [value for value in location_totals.values()]
        next_restock_date = next((item['next_restock_date'] for item in location_stock if item['next_restock_date']), None)
        return Response({
            'in_stock': product.stock_quantity > 0 or product.allow_backorder,
            'quantity': product.available_quantity,
            'location_stock': location_stock,
            'store_stock': sorted(store_totals.values(), key=lambda item: item['name']),
            'next_restock_date': next_restock_date,
        })


class InventoryWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        signature = request.headers.get('X-Sync-Signature', '')
        if not verify_hmac_signature(request.body, signature, settings.INVENTORY_SYNC_SECRET):
            return Response({'detail': 'Invalid inventory sync signature.'}, status=status.HTTP_403_FORBIDDEN)

        rows = normalize_inventory_payload(request.data)
        results = apply_inventory_sync(rows, source=StockMovement.SOURCE_WEBHOOK)
        return Response({'updated': results})


class AdminInventoryBulkUpdateView(APIView):
    """Batch update stock levels from ERP import or bulk adjustment."""

    permission_classes = [IsAdminOrInventoryStaff]

    def post(self, request):
        updates = request.data.get('updates', [])
        if not isinstance(updates, list) or not updates:
            return Response({'error': {'code': 'validation_error', 'message': 'updates array is required.'}}, status=400)

        results = {'updated': [], 'not_found': [], 'invalid': []}
        for item in updates:
            sku = item.get('sku')
            if not sku:
                continue
            try:
                variant = Variant.objects.select_related('product').prefetch_related(_inventory_prefetch()).get(sku=sku)
                pos_quantity = item.get('pos_quantity', item.get('warehouse_quantity'))
                if pos_quantity is not None:
                    try:
                        pos_quantity = _coerce_non_negative_int(pos_quantity)
                    except (TypeError, ValueError):
                        results['invalid'].append({'sku': sku, 'warehouse_quantity': item.get('warehouse_quantity'), 'pos_quantity': item.get('pos_quantity')})
                        continue
                    selector = _inventory_selector(item)
                    warehouse_payload = {
                        'stock_quantity': pos_quantity,
                        'source_name': item.get('source_name', ''),
                        **selector,
                    }
                    try:
                        serializer = AdminVariantSerializer(
                            variant,
                            data={'warehouse_inventory': warehouse_payload},
                            partial=True,
                            context={'request': request},
                        )
                        serializer.is_valid(raise_exception=True)
                        serializer.save()
                        warehouse_inventory, _ = resolve_variant_inventory_target(
                            variant,
                            location=Product.STOCK_WAREHOUSE,
                            **selector,
                        )
                    except (InventoryTargetError, drf_serializers.ValidationError) as exc:
                        results['invalid'].append(_invalid_inventory_result(item, exc))
                        continue
                    warehouse_inventory.source_name = item.get('source_name', warehouse_inventory.source_name or 'POS Store')
                    warehouse_inventory.is_pos_synced = True
                    warehouse_inventory.last_synced_at = timezone.now()
                    warehouse_inventory.save(update_fields=['source_name', 'is_pos_synced', 'last_synced_at', 'updated_at'])
                results['updated'].append(sku)
                log_admin_action(
                    request.user, action='inventory_bulk_updated', entity_type='variant',
                    entity_id=variant.id, message=f'Bulk updated inventory for {sku}', metadata=item,
                )
            except Variant.DoesNotExist:
                results['not_found'].append(sku)

        return Response({
            'updated_count': len(results['updated']),
            'invalid': results['invalid'],
            'not_found': results['not_found'],
            'source': request.data.get('source', 'manual'),
        })


class AdminInventoryPosSyncView(APIView):
    """Sync fallback stock from the POS-backed store."""

    permission_classes = [IsAdminOrInventoryStaff]

    def post(self, request):
        updates = request.data.get('updates', [])
        if not isinstance(updates, list) or not updates:
            return Response(
                {'error': {'code': 'validation_error', 'message': 'updates array is required.'}},
                status=400,
            )

        synced_at = timezone.now()
        results = {'updated': [], 'not_found': [], 'invalid': []}
        for item in updates:
            sku = item.get('sku')
            product_id = item.get('product_id')
            variant_id = item.get('variant_id')
            quantity = item.get('pos_quantity', item.get('stock_quantity'))
            if quantity is None or (not sku and not product_id and not variant_id):
                results['invalid'].append({'sku': sku, 'product_id': product_id, 'variant_id': variant_id})
                continue

            try:
                if variant_id:
                    variant = Variant.objects.select_related('product').prefetch_related(_inventory_prefetch()).get(pk=variant_id)
                elif sku:
                    variant = Variant.objects.select_related('product').prefetch_related(_inventory_prefetch()).get(sku=sku)
                else:
                    product = Product.objects.prefetch_related(
                        Prefetch('variants', queryset=Variant.objects.prefetch_related(_inventory_prefetch()))
                    ).get(pk=product_id)
                    variant = product.get_representative_variant()
                    if variant is None:
                        raise Variant.DoesNotExist
            except (Product.DoesNotExist, Variant.DoesNotExist):
                results['not_found'].append(variant_id or product_id or sku)
                continue

            try:
                warehouse_payload = {
                    'stock_quantity': _coerce_non_negative_int(quantity),
                    **_inventory_selector(item),
                }
                if 'low_stock_threshold' in item:
                    warehouse_payload['low_stock_threshold'] = _coerce_non_negative_int(item.get('low_stock_threshold'))
                if 'allow_backorder' in item:
                    warehouse_payload['allow_backorder'] = _coerce_bool(item.get('allow_backorder'))
                if 'max_backorder_quantity' in item:
                    warehouse_payload['max_backorder_quantity'] = _coerce_non_negative_int(item.get('max_backorder_quantity'))
            except (TypeError, ValueError):
                results['invalid'].append({'sku': sku, 'product_id': product_id, 'variant_id': variant_id})
                continue

            try:
                serializer = AdminVariantSerializer(
                    variant,
                    data={'warehouse_inventory': warehouse_payload},
                    partial=True,
                    context={'request': request},
                )
                serializer.is_valid(raise_exception=True)
                serializer.save()
                warehouse_inventory, _ = resolve_variant_inventory_target(
                    variant,
                    location=Product.STOCK_WAREHOUSE,
                    **_inventory_selector(item),
                )
            except (InventoryTargetError, drf_serializers.ValidationError) as exc:
                results['invalid'].append(_invalid_inventory_result(item, exc))
                continue
            warehouse_inventory.source_name = item.get('source_name', warehouse_inventory.source_name or 'POS Store')
            warehouse_inventory.is_pos_synced = True
            warehouse_inventory.last_synced_at = synced_at
            warehouse_inventory.save(update_fields=['source_name', 'is_pos_synced', 'last_synced_at', 'updated_at'])

            results['updated'].append(variant.sku)
            log_admin_action(
                request.user,
                action='inventory_pos_synced',
                entity_type='variant',
                entity_id=variant.id,
                message=f'Synced POS fallback stock for {variant.sku}',
                metadata={
                    'pos_quantity': warehouse_inventory.stock_quantity,
                    'source_name': warehouse_inventory.source_name,
                    'synced_at': synced_at.isoformat(),
                },
            )

        return Response({
            'updated_count': len(results['updated']),
            'updated': results['updated'],
            'not_found': results['not_found'],
            'invalid': results['invalid'],
            'synced_at': synced_at.isoformat(),
        })


class AdminInventoryMovementsView(APIView):
    """Return stock movement history for a product."""

    permission_classes = [IsAdminOrInventoryStaff]

    def get(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({'error': {'code': 'not_found', 'message': 'Product not found.'}}, status=404)

        movements_qs = StockMovement.objects.filter(variant_inventory__variant__product_id=pk).select_related('created_by', 'variant_inventory', 'variant_inventory__variant')[:100]
        serializer = StockMovementSerializer(movements_qs, many=True)
        return Response({'product_id': pk, 'product_name': product.name, 'movements': serializer.data})


class AdminInventoryReserveView(APIView):
    """Validate availability; stock is committed atomically during checkout."""

    permission_classes = [IsAdminOrInventoryStaff]

    def post(self, request):
        items = request.data.get('items')
        if not isinstance(items, list) or not items:
            return Response({'detail': 'A non-empty items array is required.'}, status=400)
        checked = []
        quantities = {}
        for item in items:
            try:
                if not isinstance(item, dict):
                    raise ValueError
                if isinstance(item.get('quantity'), bool):
                    raise ValueError
                quantity = _coerce_non_negative_int(item.get('quantity', 1))
                if quantity <= 0:
                    raise ValueError
                variant = public_variant_queryset().get(pk=item['variant_id'])
                quantities[variant.pk] = quantities.get(variant.pk, 0) + quantity
                if variant.available_quantity < quantities[variant.pk]:
                    return Response({'detail': f'{variant.name} has insufficient stock.'}, status=400)
                checked.append({'product_id': variant.product_id, 'variant_id': variant.pk, 'quantity': quantity})
            except (Variant.DoesNotExist, KeyError, TypeError, ValueError):
                return Response({'detail': 'Every item must specify an active variant and a positive integer quantity.'}, status=400)
        return Response({'order_id': request.data.get('order_id'), 'available': checked, 'reserved': [],
                         'message': 'Availability checked. Stock is committed when checkout is finalized.'})


class AdminInventoryReleaseView(APIView):
    """Restore only allocations recorded for a cancelled or refunded order."""

    permission_classes = [IsAdminOrInventoryStaff]

    def post(self, request):
        from apps.orders.models import Order
        from apps.orders.stock import release_order_inventory
        from django.db import transaction
        try:
            with transaction.atomic():
                order = Order.objects.select_for_update().get(pk=request.data.get('order_id'))
                if order.status not in [Order.STATUS_CANCELLED, Order.STATUS_REFUNDED]:
                    return Response({'detail': 'Cancel or refund the order before releasing its stock.'}, status=400)
                was_committed = order.inventory_committed
                release_order_inventory(order)
                return Response({'order_id': order.pk, 'released': was_committed,
                                 'message': 'Recorded order stock released.' if was_committed else 'No committed stock to release.'})
        except (Order.DoesNotExist, TypeError, ValueError):
            return Response({'detail': 'A valid order_id is required.'}, status=400)


class AdminInventoryDeductView(APIView):
    """Checkout owns deduction; this endpoint reports recorded commitment."""

    permission_classes = [IsAdminOrInventoryStaff]

    def post(self, request):
        from apps.orders.models import Order
        try:
            order = Order.objects.get(pk=request.data.get('order_id'))
        except (Order.DoesNotExist, TypeError, ValueError):
            return Response({'detail': 'A valid order_id is required.'}, status=400)
        if not order.inventory_committed:
            return Response({'detail': 'Finalize the order through checkout to validate payment and commit stock.'}, status=409)
        return Response({'order_id': order.pk, 'deducted': [], 'message': 'Stock was already committed by checkout; no additional deduction performed.'})
