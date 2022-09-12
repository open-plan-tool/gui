from django.core.management.base import BaseCommand, CommandError
import pandas as pd
from projects.models import *


class Command(BaseCommand):
    help = "Update the assettype objects from /static/assettypes_list.csv"

    def add_arguments(self, parser):
        parser.add_argument(
            "--update", action="store_true", help="Update existing assets"
        )

    def handle(self, *args, **options):

        update_assets = options["update"]

        df = pd.read_csv("static/assettypes_list.csv")
        assets = df.to_dict(orient="records")
        for asset_params in assets:
            qs = AssetType.objects.filter(asset_type=asset_params["asset_type"])

            if qs.exists() is False:

                new_asset = AssetType(**asset_params)
                new_asset.save()
            else:
                if update_assets is True:
                    qs.update(**asset_params)
