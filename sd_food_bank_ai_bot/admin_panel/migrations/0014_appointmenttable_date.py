# Generated by Django 5.1.5 on 2025-04-08 01:54

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("admin_panel", "0013_remove_appointmenttable_date_alter_log_time_ended"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointmenttable",
            name="date",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
