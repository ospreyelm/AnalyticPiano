from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0023_auto_20231221_1537'),
    ]

    operations = [
        migrations.AddField(
            model_name='group',
            name='join_code',
            field=models.CharField(
                blank=True,
                help_text='Short code students enter to self-enrol in this group.',
                max_length=16,
                null=True,
                unique=True,
                verbose_name='Join code',
            ),
        ),
    ]
