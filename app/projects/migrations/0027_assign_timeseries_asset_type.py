from django.db import migrations
# This migration assigns timeseries asset types to existing timeseries in the database
ALLOWED = {
    "demand",
    "gas_demand",
    "h2_demand",
    "heat_demand",
    "pv_plant",
    "wind_plant",
    "biogas_plant",
    "geothermal_conversion",
    "solar_thermal_plant",
}

def forwards(apps, schema_editor):
    Asset = apps.get_model("projects", "Asset")
    Timeseries = apps.get_model("projects", "Timeseries")

    qs = (
        Asset.objects
        .select_related("asset_type", "input_timeseries")
        .only("id", "asset_type__asset_type", "input_timeseries_id")
    )
    to_update = []
    for asset in qs.iterator():
        ts_id = asset.input_timeseries_id
        # If the asset has no timeseries, continue
        if not ts_id:
            continue

        # Check that the asset type is in the allowed values
        asset_type = getattr(asset.asset_type, "asset_type", None)
        if asset_type not in ALLOWED:
            raise ValueError(f"Asset type {asset_type} not in allowed timeseries assets")

        # Add object to list to be updated
        to_update.append((ts_id, asset_type))

    # Batch update timeseries instances
    if to_update:
        from itertools import islice
        CHUNK = 1000
        it = iter(to_update)
        while True:
            chunk = list(islice(it, CHUNK))
            if not chunk:
                break
            objs = [Timeseries(id=ts_id, asset_type=value) for ts_id, value in chunk]
            Timeseries.objects.bulk_update(objs, ["asset_type"], batch_size=CHUNK)

def backwards(apps, schema_editor):
    Timeseries = apps.get_model("projects", "Timeseries")
    Timeseries.objects.update(asset_type=None)

class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0026_timeseries_asset_type"),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
