import json

from django.db import migrations


def forwards(apps, schema_editor):
    Asset = apps.get_model("projects", "Asset")
    DSO = apps.get_model("projects", "DSO")
    dso_types = {"electricity":"dso", "gas":"gas_dso", "h2":"h2_dso", "heat":"heat_dso"}
    for carrier, dso_type in dso_types.items():
        for asset in Asset.objects.filter(asset_type__asset_type=dso_type):
            if DSO.objects.filter(asset_ptr_id=asset.pk).exists():
                continue
            dso = DSO(
                asset_ptr_id=asset.pk,
                energy_price=asset.energy_price_asset,
                feedin_tariff=asset.feedin_tariff_asset,
                feedin_cap=asset.feedin_cap_asset,
                peak_demand_pricing=asset.peak_demand_pricing_asset,
                peak_demand_pricing_period=asset.peak_demand_pricing_period_asset,
                renewable_share=asset.renewable_share_asset,
                energy_vector=carrier,
                        )
            # raw save writes only the child table row of the existing parent asset
            dso.save_base(raw=True)


def backwards(apps, schema_editor):
    schema_editor.execute("DELETE FROM projects_dso")


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0039_dso"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
