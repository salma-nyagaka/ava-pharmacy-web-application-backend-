from django.db import migrations


def sync_product_category_from_subcategory(apps, schema_editor):
    Category = apps.get_model('products', 'Category')
    Product = apps.get_model('products', 'Product')

    for product in Product.objects.select_related('subcategory__category', 'category').exclude(subcategory__isnull=True):
        source_category = product.subcategory.category
        category, _ = Category.objects.get_or_create(
            slug=source_category.slug,
            defaults={
                'name': source_category.name,
                'description': source_category.description,
                'icon': source_category.icon,
                'is_active': source_category.is_active,
            },
        )

        updated_fields = []
        for field_name in ('name', 'description', 'icon', 'is_active'):
            source_value = getattr(source_category, field_name)
            if getattr(category, field_name) != source_value:
                setattr(category, field_name, source_value)
                updated_fields.append(field_name)
        if updated_fields:
            category.save(update_fields=updated_fields)

        if product.category_id != category.id:
            product.category = category
            product.save(update_fields=['category'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0017_product_cost_price_product_discount_price'),
    ]

    operations = [
        migrations.RunPython(sync_product_category_from_subcategory, migrations.RunPython.noop),
    ]
