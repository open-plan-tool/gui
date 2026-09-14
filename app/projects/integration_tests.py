import os
import django
import traceback

import json

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse


def check_all_asset_forms(project_id, client, verbose=False):
    response = client.get(
        reverse(
            "project_asset_info",
            kwargs={"proj_id": project_id},
        )
    )
    project_data = response.json()

    if verbose is True:
        print(f"Checking project {project_data['project_name']} (ID {project_id})")

        print(f"Assets: {len(project_data['assets'])}")

    failures = []

    for asset in project_data["assets"]:
        try:
            form_url = reverse(
                "get_asset_create_form",
                kwargs={
                    "scen_id": asset["scenario_id"],
                    "asset_type_name": asset["asset_type"],
                    "asset_uuid": asset["uuid"],
                },
            )
        except Exception as e:
            failures.append(
                {
                    **asset,
                    "status_code": "get_asset_create_form cannot be reversed",
                    "response": traceback.format_exc(),
                }
            )

        try:
            response = client.get(
                form_url,
                {
                    "inputs": json.dumps([]),
                    "outputs": json.dumps([]),
                },
            )
        except Exception as e:
            failures.append(
                {
                    **asset,
                    "status_code": "the form url cannot be get",
                    "response": traceback.format_exc(),
                }
            )

        if response.status_code == 200:
            if verbose is True:
                print(f"✓ {asset['name']} [{asset['asset_type']}]")

        else:
            if verbose is True:
                print(
                    f"✗ {asset['name']} "
                    f"[{asset['asset_type']}] "
                    f"-> HTTP {response.status_code}"
                )

            failures.append(
                {
                    **asset,
                    "status_code": response.status_code,
                    "response": response.content.decode(),
                }
            )

    if verbose is True:
        if failures:
            print(
                f"{len(failures)} / {len(project_data['assets'])} asset forms failed."
            )
        else:
            print(f"All {len(project_data['assets'])} asset forms are callable.")

    return failures


if __name__ == "__main__":
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        "openplan.settings",
    )

    django.setup()
    username = "testUser"
    client = Client()

    User = get_user_model()
    user = User.objects.get(username=username)

    client.force_login(user)

    # write here the id of the projects for which you would like to test the form of all assets
    project_ids = [
        69,
        # 70,
        # 40,
    ]

    all_failures = {}

    for project_id in project_ids:
        print("\n" + "=" * 80)

        failures = check_all_asset_forms(project_id, client, verbose=True)

        if failures:
            all_failures[project_id] = failures

    if all_failures:
        print("\n" + "=" * 80)
        print("FAILURES SUMMARY")
        print("=" * 80)
        print(json.dumps(all_failures, indent=2, ensure_ascii=False))
