import json

from django.core.management.base import BaseCommand, CommandError
from django.test import Client
from projects.tests import check_all_asset_forms


class Command(BaseCommand):
    help = "Check that the form to modify asset's parameter return 200 for all assets within a given project"

    def add_arguments(self, parser):
        parser.add_argument("proj_id", nargs="+", type=int)

    def handle(self, *args, **options):
        client = Client()
        client.login(username="testUser", password="ASas12,.")

        all_failures = {}

        for project_id in options["proj_id"]:
            print("\n" + "=" * 80)

            failures = check_all_asset_forms(project_id, client, verbose=True)

            if failures:
                all_failures[project_id] = failures

        if all_failures:
            print("\n" + "=" * 80)
            print("FAILURES SUMMARY")
            print("=" * 80)
            print(json.dumps(all_failures, indent=2, ensure_ascii=False))
