# Generated by Django 5.1.5 on 2025-04-09 21:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("admin_panel", "0015_merge_20250408_1904"),
    ]

    operations = [
        migrations.AlterField(
            model_name="admin",
            name="approved_for_admin_panel",
            field=models.BooleanField(
                default=None, null=True, verbose_name="approved for admin panel"
            ),
        ),
    ]
