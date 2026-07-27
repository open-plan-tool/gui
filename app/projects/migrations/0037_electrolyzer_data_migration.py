import json

from django.db import migrations


def forwards(apps, schema_editor):
    Asset = apps.get_model("projects", "Asset")
    Electrolyzer = apps.get_model("projects", "Electrolyzer")

    unmapped = []
    for asset in Asset.objects.filter(asset_type__asset_type="electrolyzer"):
        if Electrolyzer.objects.filter(asset_ptr_id=asset.pk).exists():
            continue
        elzer = Electrolyzer(
            asset_ptr_id=asset.pk,
            efficiency_heat=float(asset.efficiency_multiple) if asset.efficiency_multiple is not None else None,
        )
        # raw save writes only the child table row of the existing parent asset
        elzer.save_base(raw=True)
        if (
            asset.efficiency is None
            and asset.efficiency not in (None, "")
        ):
            unmapped.append(asset.pk)

    if unmapped:
        print(
            f"WARNING: electrolyzer assets {unmapped} had non-scalar efficiency values "
            "which could not be mapped to eesyplan conversion factors"
        )


def backwards(apps, schema_editor):
    schema_editor.execute("DELETE FROM projects_electrolyzer")


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0036_electrolyzer"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
