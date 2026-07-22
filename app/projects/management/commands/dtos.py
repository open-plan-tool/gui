import json

from django.core.management.base import BaseCommand, CommandError
from projects.models import Scenario
from projects.dtos import convert_to_dto


class Command(BaseCommand):
    help = "Convert the scenario to dtos to send to mvs"

    def add_arguments(self, parser):
        parser.add_argument("scen_id", nargs="+", type=int)
        parser.add_argument(
            "--reduced", action="store_true", help="Update existing assets"
        )

    def handle(self, *args, **options):
        testing = options["reduced"]

        for scen_id in options["scen_id"]:
            try:
                scenario = Scenario.objects.get(pk=scen_id)
            except Scenario.DoesNotExist:
                raise CommandError('Scenario "%s" does not exist' % scen_id)

            dto = convert_to_dto(scenario, testing=testing)
            dumped_data = json.loads(
                json.dumps(dto.__dict__, default=lambda o: o.__dict__)
            )
            fname = f"scenario_{scen_id}_dtos.json"
            with open(fname, "w") as fp:
                json.dump(dumped_data, fp)

            print(dumped_data)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully converted scenario '{scen_id}' into {fname}"
                )
            )
