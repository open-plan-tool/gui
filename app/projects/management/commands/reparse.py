from django.core.management.base import BaseCommand, CommandError
from projects.models import Simulation, Scenario
from django.db.models import CharField, F, Func, Q

import pprint
import json


pp = pprint.PrettyPrinter(indent=4)


def has_invalid_dp_results(scenario):
    qs = Simulation.objects.filter(scenario=scenario).annotate(
        dp_results_type=Func(
            F("dp_results"),
            function="jsonb_typeof",
            output_field=CharField(),
        )
    )
    if qs.filter(dp_results__isnull=True).exists():
        return "reset"
    if qs.filter(dp_results_type="string").exists():
        return "reparse"

    return "all good"


class Command(BaseCommand):
    help = "Find out which simulations are jsonified dicts"

    def handle(self, *args, **options):
        simulations = (
            Simulation.objects.exclude(dp_results__isnull=True)
            .annotate(
                dp_results_type=Func(
                    F("dp_results"),
                    function="jsonb_typeof",
                    output_field=CharField(),
                )
            )
            .filter(dp_results_type="string")
        )

        print(
            f"{simulations.count()} simulation have a str instead of a dict in 'dp_results'"
        )
        answer = input("Do you want to fix this [y]?: ")
        if answer == "y":
            for simulation in simulations:
                simulation.dp_results = json.loads(simulation.dp_results)
                if isinstance(simulation.graphs, str):
                    simulation.graphs = json.loads(simulation.graphs)
                if isinstance(simulation.tables, str):
                    simulation.tables = json.loads(simulation.tables)

                simulation.save(update_fields=["dp_results", "graphs", "tables"])
