from django.core.management.base import BaseCommand, CommandError
import pandas as pd
from projects.models import *


class Command(BaseCommand):
    help = "Update the valuetype objects from /static/valuetypes_list.csv"

    def add_arguments(self, parser):
        parser.add_argument(
            "--update", action="store_true", help="Update existing assets"
        )

    def handle(self, *args, **options):

        update_valuetypes = options["update"]

        df = pd.read_csv("static/valuetypes_list.csv")
        valuetypes = df.to_dict(orient="records")
        for vt_params in valuetypes:
            qs = ValueType.objects.filter(type=vt_params["type"])

            if qs.exists() is False:
                new_valuetype = ValueType(**vt_params)
                new_valuetype.save()
            else:
                if update_valuetypes is True:
                    qs.update(**vt_params)
