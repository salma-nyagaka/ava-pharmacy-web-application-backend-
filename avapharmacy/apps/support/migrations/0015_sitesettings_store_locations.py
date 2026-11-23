from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('support', '0014_alter_complianceevidence_evidence_type')]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='store_locations',
            field=models.JSONField(blank=True, default=list, help_text='Store addresses displayed in the website footer, in order.'),
        ),
    ]
