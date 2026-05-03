from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.db.models.functions import Lower


def copy_child_categories_to_catalog_subcategories(apps, schema_editor):
    Category = apps.get_model('products', 'Category')
    CatalogSubcategory = apps.get_model('products', 'CatalogSubcategory')

    child_categories = list(Category.objects.filter(parent__isnull=False).iterator())
    if not child_categories:
        return

    existing_ids = set(CatalogSubcategory.objects.values_list('id', flat=True))
    to_create = []
    for child in child_categories:
        if child.id in existing_ids:
            continue
        to_create.append(
            CatalogSubcategory(
                id=child.id,
                category_id=child.parent_id,
                name=child.name,
                slug=child.slug,
                image=child.image,
                description=child.description,
                is_active=child.is_active,
                created_at=child.created_at,
                updated_at=child.updated_at,
                created_by_id=child.created_by_id,
                updated_by_id=child.updated_by_id,
            )
        )
    if to_create:
        CatalogSubcategory.objects.bulk_create(to_create)
        table = CatalogSubcategory._meta.db_table
        sequence = f"{table}_id_seq"
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT setval(%s, GREATEST(COALESCE((SELECT MAX(id) FROM {table}), 1), 1), true)",
                [sequence],
            )


def delete_child_category_rows(apps, schema_editor):
    Category = apps.get_model('products', 'Category')
    Category.objects.filter(parent__isnull=False).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0046_delete_legacy_category_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='CatalogSubcategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(max_length=200, unique=True)),
                ('image', models.ImageField(blank=True, upload_to='categories/')),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='catalog_subcategories', to='products.category')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_catalog_subcategories', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_catalog_subcategories', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'catalog subcategories',
                'ordering': ['category__name', 'name'],
            },
        ),
        migrations.AddIndex(
            model_name='catalogsubcategory',
            index=models.Index(fields=['category', 'is_active'], name='products_ca_categor_6a9cdd_idx'),
        ),
        migrations.AddConstraint(
            model_name='catalogsubcategory',
            constraint=models.UniqueConstraint(Lower('name'), models.F('category'), name='unique_catalog_subcategory_name_per_category_ci'),
        ),
        migrations.RunPython(copy_child_categories_to_catalog_subcategories, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='variant',
            name='catalog_subcategory',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='variants_as_subcategory', to='products.catalogsubcategory'),
        ),
        migrations.RunPython(delete_child_category_rows, migrations.RunPython.noop),
    ]
