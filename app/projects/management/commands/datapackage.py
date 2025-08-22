from django.core.management.base import BaseCommand, CommandError
from projects.models import Asset, AssetType, TopologyNode, Timeseries, ConnectionLink, Bus
from projects.dtos import convert_to_dto


class Command(BaseCommand):
    help = "Convert the scenario to datapackage"

    # def add_arguments(self, parser):
    #     parser.add_argument("scen_id", nargs="+", type=int)

    def handle(self, *args, **options):
        scen_id = 9

        qs_assets = Asset.objects.filter(scenario__id=scen_id)

        for asset in qs_assets:
            for link in asset.to_datapackage():
                print(link)
        #
        # the asset_fields correspond only to the asset's fields, however oemof-tabular needs to have attributes of the facade for the connection to busses

        #TODO iterate through the asset_types maybe? As each asset_type gets a csv file

        cols = [] # columns


        # Materialize rows
        rows = [obj.to_datapackage(fields=cols, include_fk_labels=include_fk_labels) for obj in queryset]

        # Write CSV
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({c: r.get(c, None) for c in cols})


        # links = ConnectionLink.objects.filter(scenario__id=scen_id)
        #
        # # When you’ll use the related bus/scenario on each link:
        # links = asset.connectionlink_set.select_related("bus", "scenario")
        #
        # links_same_scenario = asset.connectionlink_set.filter(scenario=asset.scenario)
        #
        # # if FLOW_DIRECTION has values like "in", "out"
        # inbound = asset.connectionlink_set.filter(flow_direction="in")
        # outbound = asset.connectionlink_set.filter(flow_direction="out")

        # for scen_id in options["scen_id"]:
        #     try:
        #         scenario = Scenario.objects.get(pk=scen_id)
        #     except Scenario.DoesNotExist:
        #         raise CommandError('Scenario "%s" does not exist' % scen_id)
        #
        #     dto = convert_to_dto(scenario)
        #     import pdb
        #
        #     pdb.set_trace()
        #     self.stdout.write(
        #         self.style.SUCCESS('Successfully converted scenario "%s"' % scen_id)
        #     )
