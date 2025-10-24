from django.core.management.base import BaseCommand, CommandError
from projects.models import (
    Asset,
    AssetType,
    TopologyNode,
    Scenario,
    Timeseries,
    ConnectionLink,
    Bus,
)
import pandas as pd
from pathlib import Path
import numpy as np
import shutil


class Command(BaseCommand):
    help = "Convert the given scenarios to datapackages"

    def add_arguments(self, parser):
        parser.add_argument("scen_id", nargs="+", type=int)

        parser.add_argument(
            "--overwrite", action="store_true", help="Overwrite the datapackage"
        )

    def handle(self, *args, **options):
        overwrite = options["overwrite"]

        for scen_id in options["scen_id"]:
            try:
                scenario = Scenario.objects.get(pk=scen_id)
            except Scenario.DoesNotExist:
                raise CommandError('Scenario "%s" does not exist' % scen_id)

            destination_path = Path(__file__).resolve().parents[4]

            # Create a folder with a datapackage structure
            scenario_folder = destination_path / f"scenario_{scen_id}"
            create_folder = True

            if scenario_folder.exists():
                if not overwrite:
                    create_folder = False
                else:
                    shutil.rmtree(scenario_folder)

            elements_folder = scenario_folder / "data" / "elements"
            sequences_folder = scenario_folder / "data" / "sequences"

            if create_folder:
                # create subfolders
                (scenario_folder / "scripts").mkdir(parents=True)
                elements_folder.mkdir(parents=True)
                sequences_folder.mkdir(parents=True)

            # List all components of the scenario (except the busses)
            qs_assets = Asset.objects.filter(scenario=scenario)
            # List all distinct components' assettypes (or facade name)
            facade_names = qs_assets.distinct().values_list(
                "asset_type__asset_type", flat=True
            )

            bus_resource_records = []
            profile_resource_records = {}
            for facade_name in facade_names:
                resource_records = []
                for i, asset in enumerate(
                    qs_assets.filter(asset_type__asset_type=facade_name)
                ):
                    resource_rec, bus_resource_rec, profile_resource_rec = (
                        asset.to_datapackage()
                    )
                    resource_records.append(resource_rec)
                    # those constitute the busses and sequences used by this asset
                    bus_resource_records.extend(bus_resource_rec)
                    profile_resource_records.update(profile_resource_rec)

                if resource_records:
                    out_path = elements_folder / f"{facade_name}.csv"
                    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
                    df = pd.DataFrame(resource_records)
                    df.to_csv(out_path, index=False)

            # Save all unique busses to a elements resource
            if bus_resource_records:
                out_path = elements_folder / f"bus.csv"
                Path(out_path).parent.mkdir(parents=True, exist_ok=True)
                df = pd.DataFrame(bus_resource_records)
                df.drop_duplicates("name").to_csv(out_path, index=False)

            # Save all profiles to a sequences resource
            if profile_resource_records:
                out_path = sequences_folder / f"profiles.csv"
                Path(out_path).parent.mkdir(parents=True, exist_ok=True)
                # add timestamps to the profiles
                profile_resource_records["timeindex"] = scenario.get_timestamps()
                try:
                    df = pd.DataFrame(profile_resource_records)
                except ValueError as e:
                    # If not all profiles have the same length we pad the shorter profiles with np.nan
                    max_len = max(len(v) for v in profile_resource_records.values())
                    profile_resource_records = {
                        k: v + [np.nan] * (max_len - len(v))
                        for k, v in profile_resource_records.items()
                    }
                    df = pd.DataFrame(profile_resource_records)
                    print(
                        f"Some profiles have more timesteps that other profiles in scenario {scenario.name}({scen_id}) --> the shorter profiles will be expanded with NaN values"
                    )
                # TODO check if there are column duplicates
                df.set_index("timeindex").to_csv(out_path, index=True)
