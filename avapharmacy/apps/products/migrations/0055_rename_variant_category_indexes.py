from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0054_rename_variant_category_tables'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='category',
            old_name='products_ca_parent__1cafc9_idx',
            new_name='prodcut_var_parent__29a9b7_idx',
        ),
        migrations.RenameIndex(
            model_name='category',
            old_name='products_ca_is_acti_5a5180_idx',
            new_name='prodcut_var_is_acti_12e3f7_idx',
        ),
        migrations.RenameIndex(
            model_name='subcategory',
            old_name='products_su_categor_86a9be_idx',
            new_name='product_var_categor_11086c_idx',
        ),
    ]
