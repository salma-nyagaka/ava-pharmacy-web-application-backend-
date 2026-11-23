from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('lab', '0015_labrequest_collection_fee_amount')]
    operations = [migrations.AddField(model_name='labrequest', name='rider_dispatched_at', field=models.DateTimeField(blank=True, null=True))]
