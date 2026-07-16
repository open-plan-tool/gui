import json

from django.db import migrations


def _to_float(value):
    """Map an MVS text parameter (scalar or json list) to a float, None if impossible"""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None
    if isinstance(parsed, list) and parsed and all(v == parsed[0] for v in parsed):
        return float(parsed[0])
    return None


def forwards(apps, schema_editor):
    Asset = apps.get_model("projects", "Asset")
    CHP = apps.get_model("projects", "CHP")

    unmapped = []
    for asset in Asset.objects.filter(asset_type__asset_type="chp"):
        if CHP.objects.filter(asset_ptr_id=asset.pk).exists():
            continue
        chp = CHP(
            asset_ptr_id=asset.pk,
            conversion_factor_to_electricity=_to_float(asset.efficiency),
            conversion_factor_to_heat=_to_float(asset.efficiency_multiple),
            beta=asset.thermal_loss_rate,
        )
        # raw save writes only the child table row of the existing parent asset
        chp.save_base(raw=True)
        if (
            _to_float(asset.efficiency) is None
            and asset.efficiency not in (None, "")
            or _to_float(asset.efficiency_multiple) is None
            and asset.efficiency_multiple not in (None, "")
        ):
            unmapped.append(asset.pk)

    if unmapped:
        print(
            f"WARNING: chp assets {unmapped} had non-scalar efficiency values "
            "which could not be mapped to eesyplan conversion factors"
        )


def backwards(apps, schema_editor):
    schema_editor.execute("DELETE FROM projects_chp")


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0030_chp"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
