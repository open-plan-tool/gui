from django.core.management.base import BaseCommand, CommandError
from projects.models import (
    Asset,
    AssetType,
    TopologyNode,
    Timeseries,
    ConnectionLink,
    Bus,
)
import pandas as pd
from pathlib import Path
import csv
import shutil
from projects.dtos import convert_to_dto


class Command(BaseCommand):
    help = "Convert the scenario to datapackage"

    # def add_arguments(self, parser):
    #     parser.add_argument("scen_id", nargs="+", type=int)

    def handle(self, *args, **options):
        scen_id = 70

        overwrite = True

        destination_path = Path(__file__).resolve().parents[4]

        """Create a folder with the datapackage structure, the components and timeseries will be filled later on"""
        scenario_folder = destination_path / f"scenario_{scen_id}"
        create_folder = True

        if scenario_folder.exists():
            if not overwrite:
                create_folder = False
            else:
                shutil.rmtree(scenario_folder)

        if create_folder:
            # create subfolders
            (scenario_folder / "scripts").mkdir(parents=True)
            elements_folder = (scenario_folder / "data" / "elements")
            elements_folder.mkdir(parents=True)
            sequences_folder = (scenario_folder / "data" / "sequences")
            sequences_folder.mkdir(parents=True)

        print(elements_folder)



        AssetType.objects.filter(id__in=[1,2])
        qs_assets = Asset.objects.filter(scenario__id=scen_id)
        facade_names = qs_assets.distinct().values_list("asset_type__asset_type",flat=True)

        # TODO busses



        for facade_name in facade_names:
            resource_records = []
            for i, asset in enumerate(qs_assets.filter(asset_type__asset_type=facade_name)):
                resource_records.append(asset.to_datapackage())
                if i == 0:
                    cols = [c for c in resource_records[i].keys()]
                    print("columns", cols)
                # for link in asset.to_datapackage():
                #     print(link)
                # TODO check the timeseries (by field or by type of field (this cannot be done currently as some timeseries field are json strings like efficiency, efficiency_multiple, energy_price, feedin_tariff) and move them to sequences
            import pdb

            pdb.set_trace()
            if resource_records:
                out_path = elements_folder / f"{facade_name}.csv"
                Path(out_path).parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, "w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
                    w.writeheader()
                    for r in resource_records:
                        w.writerow({c: r.get(c, None) for c in cols})
        # the asset_fields correspond only to the asset's fields, however oemof-tabular needs to have attributes of the facade for the connection to busses

        # TODO iterate through the asset_types maybe? As each asset_type gets a csv file

        # cols = []  # columns
        #
        # # Materialize rows
        # rows = [
        #     obj.to_datapackage(fields=cols, include_fk_labels=include_fk_labels)
        #     for obj in queryset
        # ]
        #
        # # Write CSV
        # Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        # with open(out_path, "w", newline="", encoding="utf-8") as f:
        #     w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        #     w.writeheader()
        #     for r in rows:
        #         w.writerow({c: r.get(c, None) for c in cols})
        #
        # # links = ConnectionLink.objects.filter(scenario__id=scen_id)
        # #
        # # # When you’ll use the related bus/scenario on each link:
        # # links = asset.connectionlink_set.select_related("bus", "scenario")
        # #
        # # links_same_scenario = asset.connectionlink_set.filter(scenario=asset.scenario)
        # #
        # # # if FLOW_DIRECTION has values like "in", "out"
        # # inbound = asset.connectionlink_set.filter(flow_direction="in")
        # # outbound = asset.connectionlink_set.filter(flow_direction="out")
        #
        # # for scen_id in options["scen_id"]:
        # #     try:
        # #         scenario = Scenario.objects.get(pk=scen_id)
        # #     except Scenario.DoesNotExist:
        # #         raise CommandError('Scenario "%s" does not exist' % scen_id)
        # #
        # #     dto = convert_to_dto(scenario)
        # #     import pdb
        # #
        # #     pdb.set_trace()
        # #     self.stdout.write(
        # #         self.style.SUCCESS('Successfully converted scenario "%s"' % scen_id)
        # #     )
