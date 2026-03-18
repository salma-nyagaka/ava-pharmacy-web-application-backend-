"""
django-filters FilterSet for the products app.

Provides the ProductFilter class used by product list views to support
price-range, category, brand, stock source, inventory status, and boolean
field filtering.
"""
import django_filters
from django.db import models
from .models import Product, annotate_product_inventory


class ProductFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    category = django_filters.CharFilter(field_name='category__slug', lookup_expr='exact')
    subcategory = django_filters.CharFilter(field_name='catalog_subcategory__slug', lookup_expr='exact')
    brand = django_filters.CharFilter(field_name='brand__slug', lookup_expr='exact')
    health_concern = django_filters.CharFilter(field_name='health_concerns__slug', lookup_expr='exact')
    stock_source = django_filters.CharFilter(method='filter_stock_source')
    inventory_status = django_filters.CharFilter(method='filter_inventory_status')
    requires_prescription = django_filters.BooleanFilter()
    is_featured = django_filters.BooleanFilter()
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = Product
        fields = [
            'category', 'subcategory', 'brand', 'health_concern', 'stock_source', 'inventory_status', 'requires_prescription',
            'is_featured', 'is_active', 'min_price', 'max_price'
        ]

    def filter_inventory_status(self, queryset, name, value):
        queryset = annotate_product_inventory(queryset)
        if value == 'out_of_stock':
            return queryset.filter(total_stock_quantity=0, has_backorder_inventory=False)
        if value == 'backorder':
            return queryset.filter(total_stock_quantity=0, has_backorder_inventory=True)
        if value == 'low_stock':
            return queryset.filter(total_stock_quantity__gt=0, total_stock_quantity__lte=models.F('total_low_stock_threshold'))
        if value == 'in_stock':
            return queryset.filter(total_stock_quantity__gt=models.F('total_low_stock_threshold'))
        if value == 'inactive':
            return queryset.filter(is_active=False)
        return queryset

    def filter_stock_source(self, queryset, name, value):
        queryset = annotate_product_inventory(queryset)
        if value == Product.STOCK_BRANCH:
            return queryset.filter(branch_stock_quantity__gt=0)
        if value == Product.STOCK_WAREHOUSE:
            return queryset.filter(branch_stock_quantity=0, warehouse_stock_quantity__gt=0)
        if value == Product.STOCK_OUT:
            return queryset.filter(total_stock_quantity=0)
        return queryset
