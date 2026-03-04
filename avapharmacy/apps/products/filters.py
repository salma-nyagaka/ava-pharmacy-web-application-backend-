import django_filters
from django.db import models
from .models import Product


class ProductFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    category = django_filters.CharFilter(field_name='category__slug', lookup_expr='exact')
    brand = django_filters.CharFilter(field_name='brand__slug', lookup_expr='exact')
    stock_source = django_filters.CharFilter(field_name='stock_source', lookup_expr='exact')
    inventory_status = django_filters.CharFilter(method='filter_inventory_status')
    requires_prescription = django_filters.BooleanFilter()
    is_featured = django_filters.BooleanFilter()
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = Product
        fields = [
            'category', 'brand', 'stock_source', 'inventory_status', 'requires_prescription',
            'is_featured', 'is_active', 'min_price', 'max_price'
        ]

    def filter_inventory_status(self, queryset, name, value):
        if value == 'out_of_stock':
            return queryset.filter(stock_quantity=0, allow_backorder=False)
        if value == 'backorder':
            return queryset.filter(stock_quantity=0, allow_backorder=True)
        if value == 'low_stock':
            return queryset.filter(stock_quantity__gt=0, stock_quantity__lte=models.F('low_stock_threshold'))
        if value == 'in_stock':
            return queryset.filter(stock_quantity__gt=models.F('low_stock_threshold'))
        if value == 'inactive':
            return queryset.filter(is_active=False)
        return queryset
