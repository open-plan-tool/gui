from django.core.management.base import BaseCommand, CommandError
from projects.models import Scenario
from pathlib import Path
import shutil
from oemof.tabular.datapackage import building
import datapackage as dp


class Command(BaseCommand):
    help = "Convert the given scenarios to datapackages"

    def add_arguments(self, parser):
        parser.add_argument("scen_id", nargs="+", type=int)

    def handle(self, *args, **options):

        for scen_id in options["scen_id"]:
            try:
                scenario = Scenario.objects.get(pk=scen_id)
            except Scenario.DoesNotExist:
                raise CommandError('Scenario "%s" does not exist' % scen_id)
            destination_path = Path(__file__).resolve().parents[4]

            scenario_folder = destination_path / f"scenario_{scen_id}"
            if scenario_folder.exists():
                shutil.rmtree(scenario_folder)
            scenario.to_datapackage(destination_path)

            dp_json = scenario_folder / "datapackage.json"

            if dp_json.exists():
                print("Only inferring metadata")
                p = dp.Package(dp_json)
                building.infer_package_foreign_keys(p)
                p.descriptor["resources"].sort(key=lambda x: (x["path"], x["name"]))
                p.commit()
                p.save(dp_json)

            else:
                print("Creating datapackage.json")
                building.infer_metadata_from_data(
                    package_name=f"scenario_{scen_id}",
                    path=scenario_folder,
                )
