# Generated by Django 5.1.5 on 2025-04-08 04:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "admin_panel",
            "0013_admin_approved_for_admin_panel_admin_foodbank_email_and_more",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="admin",
            name="foodbank_email",
            field=models.EmailField(
                blank=True, max_length=254, verbose_name="foodbank email"
            ),
        ),
    ]
