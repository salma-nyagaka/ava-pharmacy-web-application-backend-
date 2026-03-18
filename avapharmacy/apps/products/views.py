"""
API views for the products app.

Provides public catalog endpoints (categories, brands, products, reviews,
wishlist, banners, CMS blocks, promotions) and admin-only endpoints for full
CRUD on all catalog entities, inventory adjustment, and CMS management.
"""
from django.db import models
from django.db.models import Avg, Count, Q
from django.db.models import Prefetch
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, permissions, status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminOrInventoryStaff, IsAdminUser
from apps.accounts.utils import log_admin_action

from .filters import ProductFilter
from .models import Banner, Brand, Category, CMSBlock, HealthConcern, Product, ProductBadge, ProductImage, ProductInventory, ProductReview, ProductVariant, Promotion, StockMovement, Wishlist, annotate_product_inventory
from .serializers import (
    AdminProductSerializer,
    BannerSerializer,
    BrandSerializer,
    CMSBlockSerializer,
    CategorySerializer,
    HealthConcernSerializer,
    ProductBadgeSerializer,
    ProductCategorySerializer,
    ProductSubcategorySerializer,
    ProductDetailSerializer,
    ProductImageSerializer,
    ProductListSerializer,
    ProductReviewSerializer,
    ProductVariantSerializer,
    PromotionSerializer,
    StockMovementSerializer,
    WishlistSerializer,
)
from .services import get_active_promotions_queryset


def _coerce_non_negative_int(value):
    return max(0, int(value))


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'true', '1', 'yes', 'on'}


def annotate_product_reviews(queryset):
    return queryset.annotate(
        approved_average_rating=models.Avg('reviews__rating', filter=models.Q(reviews__is_approved=True)),
        approved_review_count=models.Count('reviews', filter=models.Q(reviews__is_approved=True), distinct=True),
    )


def _product_availability_error(product, requested_quantity):
    if not product.is_active:
        return f'{product.name} is no longer active.'
    if requested_quantity <= product.stock_quantity:
        return None
    if product.allow_backorder and requested_quantity <= product.available_quantity:
        return None
    if product.stock_quantity == 0 and not product.allow_backorder:
        return f'{product.name} is out of stock.'
    return f'{product.name} only has {product.available_quantity} unit(s) available.'


class PromotionContextMixin:
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['active_promotions'] = list(get_active_promotions_queryset())
        return context


class CategoryListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CategorySerializer

    def get_queryset(self):
        return Category.objects.filter(parent=None, is_active=True).prefetch_related(
            Prefetch('subcategories', queryset=Category.objects.filter(is_active=True).order_by('name'))
        )


class BrandListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = BrandSerializer
    queryset = Brand.objects.filter(is_active=True)


class HealthConcernListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = HealthConcernSerializer
    queryset = HealthConcern.objects.filter(is_active=True)


class ProductCategoryListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductCategorySerializer

    def get_queryset(self):
        return Category.objects.filter(parent__isnull=True, is_active=True).prefetch_related(
            Prefetch('subcategories', queryset=Category.objects.filter(is_active=True).order_by('name'))
        )


class ProductListView(PromotionContextMixin, generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductListSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'brand__name', 'category__name', 'sku']
    ordering_fields = ['price', 'created_at', 'name']
    ordering = ['-created_at']

    def get_queryset(self):
        return annotate_product_reviews(Product.objects.filter(
            Q(category__isnull=True) | Q(category__is_active=True),
            is_active=True,
        ).select_related('brand', 'category', 'catalog_subcategory').prefetch_related('variants', 'inventories'))


class FeaturedProductListView(PromotionContextMixin, generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductListSerializer

    def get_queryset(self):
        return annotate_product_reviews(Product.objects.filter(is_active=True, is_featured=True).select_related('brand', 'category', 'catalog_subcategory').prefetch_related('variants', 'inventories'))


class ProductDetailView(PromotionContextMixin, generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductDetailSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return annotate_product_reviews(Product.objects.filter(is_active=True).select_related('brand', 'category', 'catalog_subcategory').prefetch_related('gallery', 'variants', 'inventories'))


class AdminCategoryListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = ProductCategorySerializer
    queryset = Category.objects.filter(parent__isnull=True).prefetch_related(
        Prefetch('subcategories', queryset=Category.objects.order_by('name'))
    )
    filterset_fields = ['is_active', 'parent']
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
    serializer_class = ProductCategorySerializer
    queryset = Category.objects.filter(parent__isnull=True).prefetch_related(
        Prefetch('subcategories', queryset=Category.objects.order_by('name'))
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


class AdminProductCategoryListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = ProductCategorySerializer
    queryset = Category.objects.filter(parent__isnull=True).prefetch_related(
        Prefetch('subcategories', queryset=Category.objects.order_by('name'))
    )
    search_fields = ['name', 'slug']
    filterset_fields = ['is_active']

    def perform_create(self, serializer):
        cat = serializer.save(created_by=self.request.user, updated_by=self.request.user)
        log_admin_action(self.request.user, action='product_category_created', entity_type='product_category', entity_id=cat.id, message=f'Created product category {cat.name}')


class AdminProductCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = ProductCategorySerializer
    queryset = Category.objects.filter(parent__isnull=True).prefetch_related(
        Prefetch('subcategories', queryset=Category.objects.order_by('name'))
    )

    def perform_update(self, serializer):
        cat = serializer.save(updated_by=self.request.user)
        log_admin_action(self.request.user, action='product_category_updated', entity_type='product_category', entity_id=cat.id, message=f'Updated product category {cat.name}')


class AdminProductSubcategoryListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = ProductSubcategorySerializer
    search_fields = ['name', 'slug', 'parent__name']
    filterset_fields = ['is_active', 'parent']

    def get_queryset(self):
        return Category.objects.filter(parent__isnull=False).select_related('parent')

    def perform_create(self, serializer):
        sub = serializer.save(created_by=self.request.user, updated_by=self.request.user)
        log_admin_action(self.request.user, action='product_subcategory_created', entity_type='product_subcategory', entity_id=sub.id, message=f'Created subcategory {sub.name} under {sub.parent.name}')


class AdminProductSubcategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = ProductSubcategorySerializer
    queryset = Category.objects.filter(parent__isnull=False).select_related('parent')

    def perform_update(self, serializer):
        sub = serializer.save(updated_by=self.request.user)
        log_admin_action(self.request.user, action='product_subcategory_updated', entity_type='product_subcategory', entity_id=sub.id, message=f'Updated subcategory {sub.name}')


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


class AdminProductListCreateView(PromotionContextMixin, generics.ListCreateAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = AdminProductSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'sku']
    ordering_fields = ['created_at', 'price', 'name']
    ordering = ['-created_at']

    def get_queryset(self):
        return annotate_product_reviews(Product.objects.all().select_related('brand', 'category', 'catalog_subcategory').prefetch_related('variants', 'health_concerns', 'inventories'))

    def perform_create(self, serializer):
        product = serializer.save(created_by=self.request.user, updated_by=self.request.user)
        log_admin_action(
            self.request.user,
            action='product_created',
            entity_type='product',
            entity_id=product.id,
            message=f'Created product {product.name}',
            metadata={'sku': product.sku},
        )


class AdminProductDetailView(PromotionContextMixin, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = AdminProductSerializer
    queryset = annotate_product_reviews(Product.objects.all().select_related('brand', 'category', 'catalog_subcategory').prefetch_related('gallery', 'variants', 'health_concerns', 'inventories'))

    def perform_update(self, serializer):
        product = serializer.save(updated_by=self.request.user)
        log_admin_action(
            self.request.user,
            action='product_updated',
            entity_type='product',
            entity_id=product.id,
            message=f'Updated product {product.name}',
            metadata={'sku': product.sku},
        )


class ProductReviewListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductReviewSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        return ProductReview.objects.filter(
            product_id=self.kwargs['pk'], is_approved=True
        ).select_related('user')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, product_id=self.kwargs['pk'])


class WishlistView(generics.ListCreateAPIView):
    serializer_class = WishlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user).select_related(
            'product__brand',
            'product__category',
            'product__catalog_subcategory',
        ).prefetch_related('product__inventories')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        product_id = request.data.get('product_id')
        if Wishlist.objects.filter(user=request.user, product_id=product_id).exists():
            return Response({'detail': 'Already in wishlist.'}, status=status.HTTP_400_BAD_REQUEST)
        return super().create(request, *args, **kwargs)


class WishlistItemDeleteView(generics.DestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user)


class WishlistItemMoveToCartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            wishlist_item = Wishlist.objects.select_related('product').get(pk=pk, user=request.user)
        except Wishlist.DoesNotExist:
            return Response({'detail': 'Wishlist item not found.'}, status=status.HTTP_404_NOT_FOUND)

        product = wishlist_item.product
        if product.requires_prescription:
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
            product=product,
            product_variant__isnull=True,
            prescription_reference__isnull=True,
            prescription__isnull=True,
            prescription_item__isnull=True,
        ).first()
        requested_total = quantity + (existing_item.quantity if existing_item else 0)
        error = _product_availability_error(product, requested_total)
        if error:
            return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)

        if existing_item:
            existing_item.quantity = requested_total
            existing_item.save(update_fields=['quantity'])
        else:
            CartItem.objects.create(cart=cart, product=product, quantity=quantity)
        wishlist_item.delete()
        return Response({'detail': 'Item moved to cart.'}, status=status.HTTP_200_OK)


class CartItemMoveToWishlistView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        from apps.orders.models import CartItem

        try:
            cart_item = CartItem.objects.select_related('cart', 'product').get(
                pk=pk,
                cart__user=request.user,
            )
        except CartItem.DoesNotExist:
            return Response({'detail': 'Cart item not found.'}, status=status.HTTP_404_NOT_FOUND)

        Wishlist.objects.get_or_create(user=request.user, product=cart_item.product)
        cart_item.delete()
        return Response({'detail': 'Item moved to wishlist.'}, status=status.HTTP_200_OK)


class BannerListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = BannerSerializer

    def get_queryset(self):
        queryset = Banner.objects.filter(status='active')
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


class AdminProductBadgeListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = ProductBadgeSerializer
    queryset = ProductBadge.objects.all()


class AdminProductBadgeDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = ProductBadgeSerializer
    queryset = ProductBadge.objects.all()

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
    serializer_class = ProductVariantSerializer

    def get_queryset(self):
        return ProductVariant.objects.filter(product_id=self.kwargs['product_pk']).order_by('sort_order', 'name')

    def perform_create(self, serializer):
        product = generics.get_object_or_404(Product, pk=self.kwargs['product_pk'])
        variant = serializer.save(product=product)
        log_admin_action(
            self.request.user,
            action='product_variant_created',
            entity_type='product_variant',
            entity_id=variant.id,
            message=f'Created variant {variant.name} for {product.name}',
            metadata={'sku': variant.sku},
        )


class AdminProductVariantDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = ProductVariantSerializer

    def get_queryset(self):
        return ProductVariant.objects.filter(product_id=self.kwargs['product_pk'])


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


class AdminInventoryListView(generics.ListAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = ProductDetailSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'sku']
    ordering_fields = ['updated_at', 'name', 'total_stock_quantity']
    ordering = ['total_stock_quantity', 'name']

    def get_queryset(self):
        queryset = annotate_product_inventory(
            annotate_product_reviews(
                Product.objects.all().select_related('brand', 'category', 'created_by', 'catalog_subcategory').prefetch_related('inventories')
            )
        )
        stock_bucket = self.request.query_params.get('stock_bucket')
        if stock_bucket == 'low':
            queryset = queryset.filter(total_stock_quantity__gt=0, total_stock_quantity__lte=models.F('total_low_stock_threshold'))
        elif stock_bucket == 'out':
            queryset = queryset.filter(total_stock_quantity=0, has_backorder_inventory=False)
        elif stock_bucket == 'backorder':
            queryset = queryset.filter(total_stock_quantity=0, has_backorder_inventory=True)
        return queryset


class AdminInventoryAdjustView(APIView):
    permission_classes = [IsAdminOrInventoryStaff]

    def patch(self, request, pk):
        try:
            product = Product.objects.prefetch_related('inventories').get(pk=pk)
        except Product.DoesNotExist:
            return Response({'detail': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

        quantity_before = product.stock_quantity
        payload = request.data.copy()
        payload.pop('reason', None)
        serializer = ProductDetailSerializer(
            product,
            data=payload,
            partial=True,
            context={'request': request, 'active_promotions': []},
        )
        serializer.is_valid(raise_exception=True)
        product = serializer.save(updated_by=request.user)

        if product.stock_quantity != quantity_before:
            StockMovement.objects.create(
                product=product,
                movement_type=StockMovement.TYPE_ADJUSTMENT,
                quantity_change=product.stock_quantity - quantity_before,
                quantity_before=quantity_before,
                quantity_after=product.stock_quantity,
                reason=request.data.get('reason', 'Manual adjustment'),
                created_by=request.user,
                updated_by=request.user,
            )
        log_admin_action(
            request.user,
            action='inventory_adjusted',
            entity_type='product',
            entity_id=product.id,
            message=f'Adjusted inventory for {product.name}',
            metadata={
                'stock_quantity': product.stock_quantity,
                'stock_source': product.stock_source,
                'branch_stock_quantity': next((item.stock_quantity for item in product.inventories.all() if item.location == Product.STOCK_BRANCH), 0),
                'warehouse_stock_quantity': next((item.stock_quantity for item in product.inventories.all() if item.location == Product.STOCK_WAREHOUSE), 0),
                'allow_backorder': product.allow_backorder,
            },
        )
        serializer = ProductDetailSerializer(product, context={'request': request, 'active_promotions': []})
        return Response(serializer.data)


class CatalogSummaryView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({
            'products': Product.objects.filter(is_active=True).count(),
            'featured_products': Product.objects.filter(is_active=True, is_featured=True).count(),
            'categories': Category.objects.filter(parent__isnull=True, is_active=True).count(),
            'brands': Brand.objects.filter(is_active=True).count(),
            'low_stock_products': annotate_product_inventory(Product.objects.filter(is_active=True)).filter(
                total_stock_quantity__gt=0,
                total_stock_quantity__lte=models.F('total_low_stock_threshold'),
            ).count(),
            'active_promotions': get_active_promotions_queryset().count(),
            'top_categories': list(
                Category.objects.filter(parent__isnull=True, is_active=True)
                .annotate(product_count=Count('products', filter=Q(products__is_active=True)))
                .values('id', 'name', 'slug', 'product_count')[:6]
            ),
        })


class ProductDetailByIdView(PromotionContextMixin, generics.RetrieveAPIView):
    """Retrieve a product by its numeric primary key."""

    permission_classes = [permissions.AllowAny]
    serializer_class = ProductDetailSerializer

    def get_queryset(self):
        return annotate_product_reviews(Product.objects.filter(is_active=True).select_related('brand', 'category', 'catalog_subcategory').prefetch_related('gallery', 'variants', 'inventories'))


class ProductSearchView(PromotionContextMixin, generics.ListAPIView):
    """Full-text product search with facets."""

    permission_classes = [permissions.AllowAny]
    serializer_class = ProductListSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'brand__name', 'sku', 'short_description']
    ordering_fields = ['price', 'created_at', 'name']
    ordering = ['-created_at']

    def get_queryset(self):
        q = self.request.query_params.get('q', '').strip()
        qs = annotate_product_reviews(Product.objects.filter(is_active=True).select_related('brand', 'category', 'catalog_subcategory').prefetch_related('variants', 'inventories'))
        if q and len(q) >= 2:
            qs = qs.filter(
                Q(name__icontains=q) | Q(brand__name__icontains=q) | Q(sku__icontains=q) | Q(short_description__icontains=q)
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
            all_qs.values('category__slug', 'category__name')
            .annotate(count=Count('id'))
            .exclude(category__isnull=True)
            .values('category__slug', 'category__name', 'count')[:10]
        )
        brand_facets = list(
            all_qs.values('brand__name')
            .annotate(count=Count('id'))
            .exclude(brand__isnull=True)
            .values('brand__name', 'count')[:10]
        )
        prices = list(all_qs.values_list('price', flat=True))
        price_range = {
            'min': min(prices, default=0),
            'max': max(prices, default=0),
        }

        response_data = {
            'query': q,
            'products': products_data,
            'facets': {
                'categories': [{'slug': f['category__slug'], 'name': f['category__name'], 'count': f['count']} for f in category_facets],
                'brands': [{'name': f['brand__name'], 'count': f['count']} for f in brand_facets],
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

        products = Product.objects.filter(
            Q(name__icontains=q) | Q(brand__name__icontains=q),
            is_active=True,
        ).select_related('brand').prefetch_related('inventories')[:5]

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

        products = Product.objects.filter(pk__in=ids).prefetch_related('inventories')
        availability = [
            {
                'product_id': p.id,
                'is_available': p.stock_quantity > 0 or p.allow_backorder,
                'stock_source': p.stock_source,
                'quantity': p.stock_quantity,
                'is_low_stock': 0 < p.stock_quantity <= p.low_stock_threshold,
            }
            for p in products
        ]
        return Response({'availability': availability})


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
                product = Product.objects.get(sku=sku)
                pos_quantity = item.get('pos_quantity', item.get('warehouse_quantity'))
                if pos_quantity is not None:
                    try:
                        pos_quantity = _coerce_non_negative_int(pos_quantity)
                    except (TypeError, ValueError):
                        results['invalid'].append({'sku': sku, 'warehouse_quantity': item.get('warehouse_quantity'), 'pos_quantity': item.get('pos_quantity')})
                        continue
                    serializer = ProductDetailSerializer(
                        product,
                        data={'warehouse_inventory': {'stock_quantity': pos_quantity}},
                        partial=True,
                        context={'request': request, 'active_promotions': []},
                    )
                    serializer.is_valid(raise_exception=True)
                    serializer.save(updated_by=request.user)
                    warehouse_inventory = ProductInventory.objects.get(
                        product=product,
                        location=Product.STOCK_WAREHOUSE,
                    )
                    warehouse_inventory.source_name = item.get('source_name', warehouse_inventory.source_name or 'POS Store')
                    warehouse_inventory.is_pos_synced = True
                    warehouse_inventory.last_synced_at = timezone.now()
                    warehouse_inventory.save(update_fields=['source_name', 'is_pos_synced', 'last_synced_at', 'updated_at'])
                results['updated'].append(sku)
                log_admin_action(
                    request.user, action='inventory_bulk_updated', entity_type='product',
                    entity_id=product.id, message=f'Bulk updated inventory for {sku}', metadata=item,
                )
            except Product.DoesNotExist:
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
            quantity = item.get('pos_quantity', item.get('stock_quantity'))
            if quantity is None or (not sku and not product_id):
                results['invalid'].append({'sku': sku, 'product_id': product_id})
                continue

            try:
                product = Product.objects.get(pk=product_id) if product_id else Product.objects.get(sku=sku)
            except Product.DoesNotExist:
                results['not_found'].append(product_id or sku)
                continue

            try:
                warehouse_payload = {
                    'stock_quantity': _coerce_non_negative_int(quantity),
                }
                if 'low_stock_threshold' in item:
                    warehouse_payload['low_stock_threshold'] = _coerce_non_negative_int(item.get('low_stock_threshold'))
                if 'allow_backorder' in item:
                    warehouse_payload['allow_backorder'] = _coerce_bool(item.get('allow_backorder'))
                if 'max_backorder_quantity' in item:
                    warehouse_payload['max_backorder_quantity'] = _coerce_non_negative_int(item.get('max_backorder_quantity'))
            except (TypeError, ValueError):
                results['invalid'].append({'sku': sku, 'product_id': product_id})
                continue

            serializer = ProductDetailSerializer(
                product,
                data={'warehouse_inventory': warehouse_payload},
                partial=True,
                context={'request': request, 'active_promotions': []},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(updated_by=request.user)

            warehouse_inventory = ProductInventory.objects.get(
                product=product,
                location=Product.STOCK_WAREHOUSE,
            )
            warehouse_inventory.source_name = item.get('source_name', warehouse_inventory.source_name or 'POS Store')
            warehouse_inventory.is_pos_synced = True
            warehouse_inventory.last_synced_at = synced_at
            warehouse_inventory.save(update_fields=['source_name', 'is_pos_synced', 'last_synced_at', 'updated_at'])

            results['updated'].append(product.sku)
            log_admin_action(
                request.user,
                action='inventory_pos_synced',
                entity_type='product',
                entity_id=product.id,
                message=f'Synced POS fallback stock for {product.sku}',
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
            product = Product.objects.prefetch_related('inventories').get(pk=pk)
        except Product.DoesNotExist:
            return Response({'error': {'code': 'not_found', 'message': 'Product not found.'}}, status=404)

        movements_qs = StockMovement.objects.filter(product_id=pk).select_related('created_by')[:100]
        serializer = StockMovementSerializer(movements_qs, many=True)
        return Response({'product_id': pk, 'product_name': product.name, 'sku': product.sku, 'movements': serializer.data})


class AdminInventoryReserveView(APIView):
    """Reserve stock for a pending order (informational — actual deduction on finalize)."""

    permission_classes = [IsAdminOrInventoryStaff]

    def post(self, request):
        order_id = request.data.get('order_id')
        items = request.data.get('items', [])
        if not items:
            return Response({'error': {'code': 'validation_error', 'message': 'items array is required.'}}, status=400)
        reserved = []
        for item in items:
            try:
                product = Product.objects.get(pk=item['product_id'])
                quantity = int(item.get('quantity', 1))
                if product.stock_quantity >= quantity:
                    reserved.append({'product_id': product.id, 'quantity': quantity})
            except (Product.DoesNotExist, KeyError, ValueError):
                pass
        return Response({'order_id': order_id, 'reserved': reserved, 'message': 'Stock reserved.'})


class AdminInventoryReleaseView(APIView):
    """Release reserved stock when an order is cancelled."""

    permission_classes = [IsAdminOrInventoryStaff]

    def post(self, request):
        order_id = request.data.get('order_id')
        items = request.data.get('items', [])
        released = []
        for item in items:
            try:
                product = Product.objects.get(pk=item['product_id'])
                quantity = int(item.get('quantity', 1))
                qty_before = product.stock_quantity
                product.stock_quantity += quantity
                product.updated_by = request.user
                product.save(update_fields=['stock_quantity', 'stock_source', 'updated_at', 'updated_by'])
                StockMovement.objects.create(
                    product=product,
                    movement_type=StockMovement.TYPE_RELEASE,
                    quantity_change=quantity,
                    quantity_before=qty_before,
                    quantity_after=product.stock_quantity,
                    reason=f'Stock released for order {order_id}',
                    reference=str(order_id) if order_id else '',
                    created_by=request.user,
                    updated_by=request.user,
                )
                released.append({'product_id': product.id, 'quantity': quantity})
                log_admin_action(
                    request.user, action='inventory_released', entity_type='product',
                    entity_id=product.id, message=f'Released {quantity} units for order {order_id}',
                )
            except (Product.DoesNotExist, KeyError, ValueError):
                pass
        return Response({'order_id': order_id, 'released': released, 'message': 'Stock released.'})


class AdminInventoryDeductView(APIView):
    """Permanently deduct reserved stock when an order is dispatched."""

    permission_classes = [IsAdminOrInventoryStaff]

    def post(self, request):
        order_id = request.data.get('order_id')
        items = request.data.get('items', [])
        deducted = []
        for item in items:
            try:
                product = Product.objects.get(pk=item['product_id'])
                quantity = int(item.get('quantity', 1))
                qty_before = product.stock_quantity
                product.stock_quantity = max(0, product.stock_quantity - quantity)
                product.updated_by = request.user
                product.save(update_fields=['stock_quantity', 'stock_source', 'updated_at', 'updated_by'])
                StockMovement.objects.create(
                    product=product,
                    movement_type=StockMovement.TYPE_SALE,
                    quantity_change=-(qty_before - product.stock_quantity),
                    quantity_before=qty_before,
                    quantity_after=product.stock_quantity,
                    reason=f'Stock deducted for order {order_id}',
                    reference=str(order_id) if order_id else '',
                    created_by=request.user,
                    updated_by=request.user,
                )
                deducted.append({'product_id': product.id, 'quantity': quantity})
                log_admin_action(
                    request.user, action='inventory_deducted', entity_type='product',
                    entity_id=product.id, message=f'Deducted {quantity} units for order {order_id}',
                )
            except (Product.DoesNotExist, KeyError, ValueError):
                pass
        return Response({'order_id': order_id, 'deducted': deducted, 'message': 'Stock deducted.'})
