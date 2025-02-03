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

            # Create new Timeseries instance
            timeseries = Timeseries.objects.using(db_alias).create(
                name=f"{asset.name}_migration",
                user=asset.scenario.project.user,
                scenario=asset.scenario,
                values=json.loads(asset.input_timeseries_old),
                ts_type=asset.asset_type.mvs_type,
                open_source=False,
                start_date=asset.scenario.start_date,
                time_step=asset.scenario.time_step,
                end_date=end_date,
            )

            # Update asset to point to new timeseries
            asset.input_timeseries = timeseries
            asset.save()

        except Exception as e:
            # print()
            raise ValueError(
                f"Error migrating asset {asset.id} timeseries: {str(e)}: input_timeseries_old is '{asset.input_timeseries_old}'"
            )


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
