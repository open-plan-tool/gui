# Generated by Django 4.2.4 on 2024-10-14 15:19

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("projects", "0021_asset_input_timeseries")]

    operations = [
        migrations.RenameField(
            model_name="timeseries", old_name="end_time", new_name="end_date"
        ),
        migrations.RenameField(
            model_name="timeseries", old_name="start_time", new_name="start_date"
        ),
    ]
