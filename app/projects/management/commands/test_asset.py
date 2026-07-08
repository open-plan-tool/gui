from django.core.management.base import BaseCommand, CommandError
from projects.models import Scenario

from projects.models import *
from dashboard.models import *
from projects.helpers import *


import pdb


class Command(BaseCommand):
    help = "Debug models"

    def handle(self, *args, **options):
        scen = Scenario.objects.last()
        at = AssetType.objects.get(
            asset_type="commodity"
        )  # should be performed under the hood
        com = Commodity(asset_type=at, scenario=scen, full_load_hours_max=30)
        com.save()
        print(com.to_datapackage())
        pdb.set_trace()
