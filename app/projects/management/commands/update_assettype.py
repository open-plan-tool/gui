from django.core.management.base import BaseCommand, CommandError
import pandas as pd
import json
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
            asset_ports = asset_params.pop("ports", None)

            if qs.exists() is False:
                new_asset = AssetType(**asset_params)
                new_asset.save()
            else:
                if update_assets is True:
                    qs.update(**asset_params)

            asset_type = AssetType.objects.get(asset_type=asset_params["asset_type"])

            if asset_ports is not None:

                # TODO delete potential existing connexion ports
                print()
                asset_type.ports.all().delete()

                asset_ports = json.loads(asset_ports.replace("'", '"'))
                for key, label in asset_ports.items():
                    direction, num = key.split("_")
                    port, created = ConnectionPort.objects.get_or_create(
                        direction=direction,
                        num=int(num),
                        label=label,
                        asset_type=asset_type,
                    )
