import warnings

from django.db import migrations
from django.db.models import Q
import json
from datetime import timedelta


def convert_timeseries_to_model(apps, schema_editor):
    """
    Forward migration: Convert timeseries_old to Timeseries instance
    """
    # Get historical models
    Asset = apps.get_model("projects", "Asset")
    Timeseries = apps.get_model("projects", "Timeseries")
    db_alias = schema_editor.connection.alias

    # Iterate through all assets with timeseries_old data
    for asset in Asset.objects.using(db_alias).exclude(
        Q(input_timeseries_old__isnull=True) | Q(input_timeseries_old=[])
    ):
        try:
            # Calculate end time from asset start date and duration
            duration = asset.scenario.evaluated_period
            total_duration = timedelta(hours=asset.scenario.time_step) * duration
            end_date = asset.scenario.start_date + total_duration
            timeseries_values = json.loads(asset.input_timeseries_old)
            user = asset.scenario.project.user
            updated_assets = []
            timeseries_cache = {}  # Cache existing timeseries by (values, user) tuple


            # Check cache before hitting DB
            ts_key = (tuple(timeseries_values), user)
            if ts_key in timeseries_cache:
                timeseries = timeseries_cache[ts_key]
            else:
                # Check if ts with values and user already exists
                timeseries, created = Timeseries.objects.using(db_alias).get_or_create(
                    values=timeseries_values,
                    user=user,
                    defaults={
                        "name": f"{asset.name}_migration",
                        "scenario": asset.scenario,
                        "ts_type": asset.asset_type.mvs_type,
                        "open_source": False,
                        "start_date": asset.scenario.start_date,
                        "time_step": asset.scenario.time_step,
                        "end_date": end_date,
                    },
                )
                timeseries_cache[ts_key] = timeseries  # Store in cache

            # Append to updated assets for batch processing later
            asset.input_timeseries = timeseries
            updated_assets.append(asset)

        except json.JSONDecodeError:
            print(f"Error migrating asset {asset.id} timeseries")
            continue

        # Batch update all assets in one query
        if updated_assets:
            Asset.objects.using(db_alias).bulk_update(updated_assets, ["input_timeseries"])


def reverse_timeseries_conversion(apps, schema_editor):
    """
    Reverse migration: Delete created Timeseries instances and restore old data
    """
    Asset = apps.get_model("projects", "Asset")
    Timeseries = apps.get_model("projects", "Timeseries")
    db_alias = schema_editor.connection.alias

    try:
        # Find all timeseries created by this migration
        migration_timeseries = Timeseries.objects.using(db_alias).filter(
            name__contains="_migration"
        )

        # Update assets to remove reference to timeseries
        Asset.objects.using(db_alias).filter(
            input_timeseries__in=migration_timeseries
        ).update(input_timeseries=None)

        # Delete the timeseries instances
        migration_timeseries.delete()

    except Exception as e:
        print(f"Error deleting migrated timeseries: {str(e)}")
        raise e


class Migration(migrations.Migration):

    dependencies = [("projects", "0022_rename_end_time_timeseries_end_date_and_more")]

    operations = [
        # Run the timeseries migration
        migrations.RunPython(
            convert_timeseries_to_model, reverse_timeseries_conversion
        ),
    ]
