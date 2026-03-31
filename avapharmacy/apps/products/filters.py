"""
django-filters FilterSet for the products app.

Provides the ProductFilter class used by product list views to support
price-range, category, brand, stock source, inventory status, and boolean
field filtering.
"""
import django_filters
from django.db import models

from .models import Product, Variant, annotate_product_inventory


class ProductFilter(django_filters.FilterSet):
    product_id = django_filters.NumberFilter(field_name='id', lookup_expr='exact')
    min_price = django_filters.NumberFilter(method='filter_min_price')
    max_price = django_filters.NumberFilter(method='filter_max_price')
    category = django_filters.CharFilter(method='filter_category')
    subcategory = django_filters.CharFilter(method='filter_subcategory')
    brand = django_filters.CharFilter(method='filter_brand')
    health_concern = django_filters.CharFilter(method='filter_health_concern')
    stock_source = django_filters.CharFilter(method='filter_stock_source')
    inventory_status = django_filters.CharFilter(method='filter_inventory_status')
    requires_prescription = django_filters.BooleanFilter(method='filter_requires_prescription')
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = Product
        fields = [
            'product_id', 'category', 'subcategory', 'brand', 'health_concern', 'stock_source', 'inventory_status', 'requires_prescription',
            'is_active', 'min_price', 'max_price'
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

    def filter_requires_prescription(self, queryset, name, value):
        if value is True:
            return queryset.filter(variants__is_active=True, variants__requires_prescription=True).distinct()
        if value is False:
            return queryset.exclude(variants__is_active=True, variants__requires_prescription=True).distinct()
        return queryset

    def filter_min_price(self, queryset, name, value):
        return queryset.filter(variants__is_active=True, variants__price__gte=value).distinct()

    def filter_max_price(self, queryset, name, value):
        return queryset.filter(variants__is_active=True, variants__price__lte=value).distinct()

    def filter_category(self, queryset, name, value):
        return queryset.filter(variants__is_active=True, variants__category__slug=value).distinct()

    def filter_subcategory(self, queryset, name, value):
        return queryset.filter(variants__is_active=True, variants__catalog_subcategory__slug=value).distinct()

    def filter_brand(self, queryset, name, value):
        return queryset.filter(variants__is_active=True, variants__brand__slug=value).distinct()

    def filter_health_concern(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(variants__health_concerns__slug=value).distinct()


class VariantInventoryFilter(django_filters.FilterSet):
    product_id = django_filters.NumberFilter(field_name='product__id', lookup_expr='exact')
    min_price = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    category = django_filters.CharFilter(field_name='category__slug', lookup_expr='exact')
    subcategory = django_filters.CharFilter(field_name='catalog_subcategory__slug', lookup_expr='exact')
    brand = django_filters.CharFilter(field_name='brand__slug', lookup_expr='exact')
    health_concern = django_filters.CharFilter(field_name='health_concerns__slug', lookup_expr='exact')
    stock_source = django_filters.CharFilter(field_name='stock_source', lookup_expr='exact')
    inventory_status = django_filters.CharFilter(method='filter_inventory_status')
    requires_prescription = django_filters.BooleanFilter(field_name='requires_prescription')
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = Variant
        fields = [
            'product_id', 'category', 'subcategory', 'brand', 'health_concern',
            'stock_source', 'inventory_status', 'requires_prescription',
            'is_active', 'min_price', 'max_price'
        ]

    def filter_inventory_status(self, queryset, name, value):
        if value == 'out_of_stock':
            return queryset.filter(is_active=True, stock_quantity=0, allow_backorder=False)
        if value == 'backorder':
            return queryset.filter(is_active=True, stock_quantity=0, allow_backorder=True)
        if value == 'low_stock':
            return queryset.filter(is_active=True, stock_quantity__gt=0, stock_quantity__lte=models.F('low_stock_threshold'))
        if value == 'in_stock':
            return queryset.filter(is_active=True, stock_quantity__gt=models.F('low_stock_threshold'))
        if value == 'inactive':
            return queryset.filter(is_active=False)
        return queryset
