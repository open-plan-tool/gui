import json

from django.db import migrations


def forwards(apps, schema_editor):
    Asset = apps.get_model("projects", "Asset")
    CHP = apps.get_model("projects", "CHPFixedRatio")

    unmapped = []
    for asset in Asset.objects.filter(asset_type__asset_type="chp_fixed_ratio"):
        if CHP.objects.filter(asset_ptr_id=asset.pk).exists():
            continue
        chp = CHP(
            asset_ptr_id=asset.pk,
            conversion_factor_to_electricity=asset.efficiency,
            conversion_factor_to_heat=asset.efficiency_multiple,
        )
        # raw save writes only the child table row of the existing parent asset
        chp.save_base(raw=True)
        if (
            asset.efficiency is None
            and asset.efficiency not in (None, "")
            or asset.efficiency_multiple is None
            and asset.efficiency_multiple not in (None, "")
        ):
            unmapped.append(asset.pk)

    if unmapped:
        print(
            f"WARNING: chp fixed ratio assets {unmapped} had non-scalar efficiency values "
            "which could not be mapped to eesyplan conversion factors"
        )


def backwards(apps, schema_editor):
    schema_editor.execute("DELETE FROM projects_chpfixedratio")


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0032_chpfixedratio"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
