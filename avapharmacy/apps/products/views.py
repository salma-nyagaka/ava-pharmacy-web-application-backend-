from django.db import models
from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, permissions, status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminOrInventoryStaff, IsAdminUser
from apps.accounts.utils import log_admin_action

from .filters import ProductFilter
from .models import Banner, Brand, Category, Product, ProductReview, Promotion, Wishlist
from .serializers import (
    BannerSerializer,
    BrandSerializer,
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ProductReviewSerializer,
    PromotionSerializer,
    WishlistSerializer,
)
from .services import get_active_promotions_queryset


class PromotionContextMixin:
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['active_promotions'] = list(get_active_promotions_queryset())
        return context


class CategoryListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CategorySerializer

    def get_queryset(self):
        return Category.objects.filter(parent=None, is_active=True).prefetch_related('subcategories')


class BrandListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = BrandSerializer
    queryset = Brand.objects.filter(is_active=True)


class ProductListView(PromotionContextMixin, generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductListSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'brand__name', 'category__name', 'sku']
    ordering_fields = ['price', 'created_at', 'name']
    ordering = ['-created_at']

    def get_queryset(self):
        return Product.objects.filter(
            Q(category__isnull=True) | Q(category__is_active=True),
            is_active=True,
        ).select_related('brand', 'category')


class FeaturedProductListView(PromotionContextMixin, generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductListSerializer

    def get_queryset(self):
        return Product.objects.filter(is_active=True, is_featured=True).select_related('brand', 'category')


class ProductDetailView(PromotionContextMixin, generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductDetailSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return Product.objects.filter(is_active=True).select_related('brand', 'category').prefetch_related('gallery')


class AdminCategoryListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = CategorySerializer
    queryset = Category.objects.all().prefetch_related('subcategories')
    filterset_fields = ['is_active', 'parent']
    search_fields = ['name', 'slug']

    def perform_create(self, serializer):
        category = serializer.save()
        log_admin_action(
            self.request.user,
            action='category_created',
            entity_type='category',
            entity_id=category.id,
            message=f'Created category {category.name}',
        )


class AdminCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = CategorySerializer
    queryset = Category.objects.all().prefetch_related('subcategories')

    def perform_update(self, serializer):
        category = serializer.save()
        log_admin_action(
            self.request.user,
            action='category_updated',
            entity_type='category',
            entity_id=category.id,
            message=f'Updated category {category.name}',
        )


class AdminBrandListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = BrandSerializer
    queryset = Brand.objects.all()
    filterset_fields = ['is_active']
    search_fields = ['name', 'slug']

    def perform_create(self, serializer):
        brand = serializer.save()
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
        brand = serializer.save()
        log_admin_action(
            self.request.user,
            action='brand_updated',
            entity_type='brand',
            entity_id=brand.id,
            message=f'Updated brand {brand.name}',
        )


class AdminProductListCreateView(PromotionContextMixin, generics.ListCreateAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = ProductDetailSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'sku']
    ordering_fields = ['created_at', 'price', 'stock_quantity', 'name']
    ordering = ['-created_at']

    def get_queryset(self):
        return Product.objects.all().select_related('brand', 'category')

    def perform_create(self, serializer):
        product = serializer.save()
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
    serializer_class = ProductDetailSerializer
    queryset = Product.objects.all().select_related('brand', 'category').prefetch_related('gallery')

    def perform_update(self, serializer):
        product = serializer.save()
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
        return Wishlist.objects.filter(user=self.request.user).select_related('product__brand', 'product__category')

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


class BannerListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = BannerSerializer

    def get_queryset(self):
        queryset = Banner.objects.filter(status='active')
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


class AdminInventoryListView(generics.ListAPIView):
    permission_classes = [IsAdminOrInventoryStaff]
    serializer_class = ProductDetailSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'sku']
    ordering_fields = ['stock_quantity', 'updated_at', 'name']
    ordering = ['stock_quantity', 'name']

    def get_queryset(self):
        queryset = Product.objects.all().select_related('brand', 'category')
        stock_bucket = self.request.query_params.get('stock_bucket')
        if stock_bucket == 'low':
            queryset = queryset.filter(stock_quantity__gt=0, stock_quantity__lte=models.F('low_stock_threshold'))
        elif stock_bucket == 'out':
            queryset = queryset.filter(stock_quantity=0, allow_backorder=False)
        elif stock_bucket == 'backorder':
            queryset = queryset.filter(stock_quantity=0, allow_backorder=True)
        return queryset


class AdminInventoryAdjustView(APIView):
    permission_classes = [IsAdminOrInventoryStaff]

    def patch(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({'detail': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

        quantity = request.data.get('stock_quantity')
        if quantity is not None:
            try:
                product.stock_quantity = max(0, int(quantity))
            except (TypeError, ValueError):
                return Response({'stock_quantity': 'Invalid stock quantity.'}, status=status.HTTP_400_BAD_REQUEST)

        if 'stock_source' in request.data:
            product.stock_source = request.data.get('stock_source')
        if 'low_stock_threshold' in request.data:
            try:
                product.low_stock_threshold = max(0, int(request.data.get('low_stock_threshold')))
            except (TypeError, ValueError):
                return Response({'low_stock_threshold': 'Invalid threshold.'}, status=status.HTTP_400_BAD_REQUEST)
        if 'max_backorder_quantity' in request.data:
            try:
                product.max_backorder_quantity = max(0, int(request.data.get('max_backorder_quantity')))
            except (TypeError, ValueError):
                return Response({'max_backorder_quantity': 'Invalid backorder quantity.'}, status=status.HTTP_400_BAD_REQUEST)
        if 'allow_backorder' in request.data:
            raw_allow_backorder = request.data.get('allow_backorder')
            if isinstance(raw_allow_backorder, bool):
                product.allow_backorder = raw_allow_backorder
            else:
                product.allow_backorder = str(raw_allow_backorder).lower() in ['true', '1', 'yes']

        product.save()
        log_admin_action(
            request.user,
            action='inventory_adjusted',
            entity_type='product',
            entity_id=product.id,
            message=f'Adjusted inventory for {product.name}',
            metadata={
                'stock_quantity': product.stock_quantity,
                'stock_source': product.stock_source,
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
            'categories': Category.objects.filter(is_active=True).count(),
            'brands': Brand.objects.filter(is_active=True).count(),
            'low_stock_products': Product.objects.filter(
                is_active=True,
                stock_quantity__gt=0,
                stock_quantity__lte=models.F('low_stock_threshold'),
            ).count(),
            'active_promotions': get_active_promotions_queryset().count(),
            'top_categories': list(
                Category.objects.filter(is_active=True)
                .annotate(product_count=Count('products', filter=Q(products__is_active=True)))
                .values('id', 'name', 'slug', 'product_count')[:6]
            ),
        })
