from django.core.management.base import BaseCommand, CommandError
from projects.models import Scenario
from projects.dtos import convert_to_dto


class Command(BaseCommand):
    help = "Convert the scenario to dtos to send to mvs"

    def add_arguments(self, parser):
        parser.add_argument("scen_id", nargs="+", type=int)

    def handle(self, *args, **options):
        for scen_id in options["scen_id"]:
            try:
                scenario = Scenario.objects.get(pk=scen_id)
            except Scenario.DoesNotExist:
                raise CommandError('Scenario "%s" does not exist' % scen_id)

            dto = convert_to_dto(scenario)
            self.stdout.write(
                self.style.SUCCESS('Successfully converted scenario "%s"' % scen_id)
            )
