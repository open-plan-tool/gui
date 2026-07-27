import json

from django.db import migrations


def forwards(apps, schema_editor):
    Asset = apps.get_model("projects", "Asset")
    HeatPump = apps.get_model("projects", "HeatPump")

    unmapped = []
    for asset in Asset.objects.filter(asset_type__asset_type="heat_pump"):
        if HeatPump.objects.filter(asset_ptr_id=asset.pk).exists():
            continue
        hp = HeatPump(
            asset_ptr_id=asset.pk,
            cop=asset.efficiency,
        )
        # raw save writes only the child table row of the existing parent asset
        hp.save_base(raw=True)
        if (
            asset.efficiency is None
            and asset.efficiency not in (None, "")
        ):
            unmapped.append(asset.pk)

    if unmapped:
        print(
            f"WARNING: hp assets {unmapped} had non-scalar efficiency values "
            "which could not be mapped to eesyplan conversion factors"
        )


def backwards(apps, schema_editor):
    schema_editor.execute("DELETE FROM projects_heatpump")


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0034_heatpump"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
