# Generated by Django 5.1.5 on 2025-03-07 02:07

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("admin_panel", "0005_alter_log_phone_number"),
    ]

    operations = [
        migrations.AlterField(
            model_name="log",
            name="length_of_call",
            field=models.DurationField(default=datetime.timedelta(0)),
        ),
    ]
