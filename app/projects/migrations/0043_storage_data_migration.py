from django.db import migrations


def forwards(apps, schema_editor):
    Asset = apps.get_model("projects", "Asset")

    ElectricalStorage = apps.get_model("projects", "ElectricalStorage")
    HydrogenStorage = apps.get_model("projects", "HydrogenStorage")
    FuelStorage = apps.get_model("projects", "FuelStorage")
    ThermalStorage = apps.get_model("projects", "ThermalStorage")

    storage_types = {"bess": ElectricalStorage,
                     "h2ess": HydrogenStorage,
                     "gess": FuelStorage,
                     "hess": ThermalStorage,
                     }
    for storage_type, StorageModel in storage_types.items():

        for asset in Asset.objects.filter(asset_type__asset_type=storage_type):
            children = Asset.objects.filter(parent_asset=asset)
            if children.exists():
                capacity = children.get(asset_type__asset_type="capacity")

            else:
                capacity = asset

            if storage_type == "hess":
                opt = {"thermal_loss_rate": capacity.thermal_loss_rate_asset,
                       "fixed_thermal_losses_relative": capacity.fixed_thermal_losses_relativeA,
                       "fixed_thermal_losses_absolute": capacity.fixed_thermal_losses_absoluteA,
                       }
            else:
                opt = {}

            if StorageModel.objects.filter(asset_ptr_id=asset.pk).exists():
                continue
            storage = StorageModel(
                asset_ptr_id=asset.pk,
                crate=capacity.crate_asset,
                soc_min=capacity.soc_min_asset,
                soc_max=capacity.soc_max_asset,
                **opt
            )
            # raw save writes only the child table row of the existing parent asset
            storage.save_base(raw=True)
            storage.name = asset.name
            storage.age_installed = capacity.age_installed
            storage.installed_capacity = capacity.installed_capacity
            storage.capex_fix = capacity.capex_fix
            storage.capex_var = capacity.capex_var
            storage.opex_fix = capacity.opex_fix
            storage.opex_var = capacity.opex_var
            storage.lifetime = capacity.lifetime
            storage.efficiency = capacity.efficiency
            storage.capacity_cap = capacity.optimize_cap
            storage.maximum_capacity = capacity.maximum_capacity
            fields_to_update = ["name", "age_installed", "installed_capacity", "capex_fix", "capex_var", "opex_fix", "opex_var","lifetime", "efficiency", "optimize_cap", "maximum_capacity"]
            storage.save(update_fields=fields_to_update)




def backwards(apps, schema_editor):
    schema_editor.execute("DELETE FROM projects_electricalstorage")
    schema_editor.execute("DELETE FROM projects_fuelstorage")
    schema_editor.execute("DELETE FROM projects_thermalstorage")
    schema_editor.execute("DELETE FROM projects_hydrogenstorage")


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0042_storages"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
