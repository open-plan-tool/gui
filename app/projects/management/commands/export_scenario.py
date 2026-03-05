from django.core.management.base import BaseCommand, CommandError
from projects.models import Scenario
from projects.dtos import convert_to_dto

from django.forms.models import model_to_dict
from django.db import models
from projects.models import *


from projects.scenario_topology_helpers import load_scenario_from_dict


class Command(BaseCommand):
    help = "Convert the scenario export format"

    def add_arguments(self, parser):
        parser.add_argument("scen_id", nargs="+", type=int)

    def handle(self, *args, **options):
        for scen_id in options["scen_id"]:
            try:
                scenario = Scenario.objects.get(pk=scen_id)
            except Scenario.DoesNotExist:
                raise CommandError('Scenario "%s" does not exist' % scen_id)

            # arguments
            user = scenario.project.user  # otherwise provided by request.user
            # https://stackoverflow.com/questions/21925671/convert-django-model-object-to-dict-with-all-of-the-fields-intact
            dm = scenario.export(bind_project_data=True)
            # fks = [at for at in dm.keys() if issubclass(type(getattr(scenario, at)), models.Model) is True]
            assets = scenario.asset_set.all()
            asset1 = assets[0]
            dm_a = asset1.export()
            clinks = scenario.connectionlink_set.all()
            cl1 = clinks[0]
            bus_ids = list(set(clinks.values_list("bus", flat=True)))
            busses = {}
            for bus_id in bus_ids:
                bus = Bus.objects.get(id=bus_id)
                busses[bus_id] = model_to_dict(bus, exclude=["id"])
                conlinks = bus.connectionlink_set.all()

            # dm = model_to_dict(self, exclude=["id"])
            # if bind_project_data is True:
            #     dm["project"] = self.project.export()
            # else:
            #     dm.pop("project")
            #
            # energy_model_assets = self.asset_set.all()
            # dm["assets"] = []
            # for asset in energy_model_assets:
            #     dm["assets"].append(asset.export())
            #
            # clinks = self.connectionlink_set.all()
            # bus_ids = list(set(clinks.values_list("bus", flat=True)))
            # busses = {}
            # for bus_id in bus_ids:
            #     bus = Bus.objects.get(id=bus_id)
            #     busses[bus_id] = model_to_dict(bus, exclude=["id", "parent_asset"])
            #     busses[bus_id]["inputs"] = []
            #     busses[bus_id]["outputs"] = []
            #     for connection in bus.connectionlink_set.all():
            #         if connection.flow_direction == "A2B":
            #             busses[bus_id]["inputs"].append(connection.export())
            #         elif connection.flow_direction == "B2A":
            #             busses[bus_id]["outputs"].append(connection.export())
            # dm["busses"] = busses
            # return dm

            # load_scenario_from_dict(dm, user=user, project=Project.objects.get(id=20))

            # myscenario.asset_set.all().delete()
            # myscenario.connectionlink_set.all().delete()
            # Project.objects.get(id=proj_id).delete()
            # EconomicData.objects.last().delete()

            self.stdout.write(
                self.style.SUCCESS('Successfully converted scenario "%s"' % scen_id)
            )
