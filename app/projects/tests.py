import datetime
import json

import pytest
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse
from projects.models import Project, Scenario, Asset, AssetType
from projects.scenario_topology_helpers import (
    load_scenario_from_dict,
    load_project_from_dict,
)
from users.models import CustomUser


class BasicOperationsTest(TestCase):
    fixtures = ["fixtures/benchmarks_fixture.json", "fixtures/test_users.json"]

    @classmethod
    def setUpTestData(cls):
        pass

    def setUp(self):
        self.factory = RequestFactory()
        self.client.login(username="testUser", password="ASas12,.")
        self.project = Project.objects.get(id=1)

    def test_delete_project_redirects(self):
        """Make sure we are redirected to project page once deleting a project"""
        response = self.client.post(reverse("project_delete", args=[self.project.id]))
        self.assertRedirects(response, reverse("project_search"))
        response = self.client.get(response.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Project.objects.all().count(), 0)

    def test_delete_project_as_owner_removes_project(self):
        """Make sure when you are the owner of a project, it gets deleted from the database."""
        response = self.client.post(reverse("project_delete", args=[self.project.id]))
        self.assertRedirects(response, reverse("project_search"))
        response = self.client.get(response.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Project.objects.filter(id=self.project.id).count(), 0)

    def test_delete_project_as_read_viewer_removes_access_only(self):
        """Make sure when you have read rights, project stays in database and you lose rights."""
        read_user = CustomUser.objects.last()
        success, _ = self.project.add_viewer_if_not_exist(
            email=read_user.email, share_rights="read"
        )
        self.assertTrue(success)

        self.client.logout()
        self.client.force_login(read_user)

        response = self.client.post(reverse("project_delete", args=[self.project.id]))
        self.assertRedirects(response, reverse("project_search"))
        response = self.client.get(response.url)
        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(
            Project.objects.filter(id=self.project.id).count(), 1
        )  # project still in database
        self.assertFalse(self.project.viewers.filter(user=read_user).exists())

    def test_delete_project_as_edit_viewer_removes_access_only(self):
        """Make sure when you have edit rights, project stays in database and you lose rights."""
        edit_user = CustomUser.objects.last()
        success, _ = self.project.add_viewer_if_not_exist(
            email=edit_user.email, share_rights="edit"
        )
        self.assertTrue(success)

        self.client.logout()
        self.client.force_login(edit_user)

        response = self.client.post(reverse("project_delete", args=[self.project.id]))
        self.assertRedirects(response, reverse("project_search"))
        response = self.client.get(response.url)
        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(
            Project.objects.filter(id=self.project.id).count(), 1
        )  # project still in database
        self.assertFalse(self.project.viewers.filter(user=edit_user).exists())

    def test_duplicate_project_redirects(self):
        """Make sure we are redirected to project page once duplicating a project"""
        response = self.client.post(
            reverse("project_duplicate", args=[self.project.id])
        )
        self.assertRedirects(
            response, reverse("project_search", args=[self.project.id + 1])
        )
        response = self.client.get(response.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Project.objects.all().count(), 2)

    def test_add_new_viewer_to_project(self):
        test_email = CustomUser.objects.last().email
        success, _ = self.project.add_viewer_if_not_exist(
            email=test_email, share_rights="edit"
        )
        self.assertTrue(success)
        self.assertTrue(self.project.viewers.filter(user__email=test_email).exists())

    def test_add_existing_viewer_to_project(self):
        test_email = CustomUser.objects.last().email
        self.project.add_viewer_if_not_exist(email=test_email, share_rights="edit")

        success, _ = self.project.add_viewer_if_not_exist(
            email=test_email, share_rights="edit"
        )
        self.assertFalse(success)
        self.assertEqual(self.project.viewers.filter(user__email=test_email).count(), 1)

    def test_update_viewer_rights_to_project(self):
        test_email = CustomUser.objects.last().email
        self.project.add_viewer_if_not_exist(email=test_email, share_rights="edit")

        success, _ = self.project.add_viewer_if_not_exist(
            email=test_email, share_rights="read"
        )
        self.assertTrue(success)
        self.assertEqual(
            self.project.viewers.filter(
                user__email=test_email, share_rights="read"
            ).count(),
            1,
        )

    def test_add_project_user_as_viewer(self):
        test_email = CustomUser.objects.first().email
        success, _ = self.project.add_viewer_if_not_exist(
            email=test_email, share_rights="edit"
        )
        self.assertFalse(success)
        self.assertFalse(self.project.viewers.filter(user__email=test_email).exists())

    def test_add_project_viewer_via_post(self):
        test_email = CustomUser.objects.last().email
        response = self.client.post(
            reverse("project_share", args=[self.project.id]),
            dict(email=test_email, share_rights="read"),
        )
        self.assertRedirects(response, reverse("project_search", args=[1]))
        response = self.client.get(response.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.project.viewers.filter(user__email=test_email).count(), 1)

    def test_remove_existing_viewer_from_project(self):
        test_email = CustomUser.objects.last().email
        # add a viewer
        success, _ = self.project.add_viewer_if_not_exist(
            email=test_email, share_rights="edit"
        )
        self.assertTrue(success)

        # remove the viewer
        viewer = self.project.viewers.filter(user__email=test_email)
        success, _ = self.project.revoke_access(viewers=viewer)
        self.assertTrue(success)

        self.assertFalse(self.project.viewers.filter(user__email=test_email).exists())

    def test_remove_existing_viewer_from_project_via_post(self):
        test_email = CustomUser.objects.last().email
        # add a viewer
        success, _ = self.project.add_viewer_if_not_exist(
            email=test_email, share_rights="edit"
        )

        # remove the viewer
        viewer = self.project.viewers.filter(user__email=test_email).values_list(
            "id", flat=True
        )
        response = self.client.post(
            reverse("project_revoke_access", args=[self.project.id]),
            dict(viewers=viewer),
        )
        self.assertRedirects(
            response, reverse("project_search", args=[self.project.id])
        )
        response = self.client.get(response.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.project.viewers.filter(user__email=test_email).count(), 0)

    def test_remove_project_viewer_via_post_raises_permission_error_if_not_project_owner(
        self,
    ):
        pass

    # user not owner cannot share or revoke share rights

    def test_visit_create_scenario_link_from_landing_page_links_to_right_view(self):
        """Make sure a user clicking on create project link from does not experience errors"""
        response = self.client.get(
            reverse("scenario_steps", args=[self.project.id]), follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "scenario/scenario_step1.html")

    def test_duplicate_scenario_as_edit_viewer(self):
        self.scenario = self.project.scenario_set.first()
        edit_user = CustomUser.objects.last()
        success, _ = self.project.add_viewer_if_not_exist(
            email=edit_user.email, share_rights="edit"
        )
        self.assertTrue(success)

        scenario_count = Scenario.objects.count()
        self.client.logout()
        self.client.force_login(edit_user)

        response = self.client.get(
            reverse("scenario_duplicate", args=[self.scenario.id])
        )
        self.assertRedirects(
            response, reverse("project_search", args=[self.project.id])
        )
        self.assertEqual(Scenario.objects.count(), scenario_count + 1)

    def test_duplicate_scenario_as_read_viewer_raises_permission_error(self):
        self.scenario = self.project.scenario_set.first()
        read_user = CustomUser.objects.last()
        success, _ = self.project.add_viewer_if_not_exist(
            email=read_user.email, share_rights="read"
        )
        self.assertTrue(success)

        scenario_count = Scenario.objects.count()
        self.client.logout()
        self.client.force_login(read_user)

        response = self.client.get(
            reverse("scenario_duplicate", args=[self.scenario.id])
        )
        self.assertTemplateUsed(response, "error_403.html")
        self.assertEqual(Scenario.objects.count(), scenario_count)

    def test_logout(self):
        response = self.client.post(reverse("logout"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "index.html")


class ExportLoadTest(TestCase):
    fixtures = ["fixtures/benchmarks_fixture.json"]

    @classmethod
    def setUpTestData(cls):
        pass

    def setUp(self):
        self.factory = RequestFactory()
        self.client.login(username="testUser", password="ASas12,.")
        self.project = Project.objects.get(id=1)
        self.scenario = self.project.scenario_set.first()

    def test_export_and_load_scenario(self):
        user = self.project.user

        dm = self.scenario.export()
        json_dm = json.dumps(dm)

        self.assertNotIn("project", dm)
        load_scenario_from_dict(json.loads(json_dm), user, project=self.project)

        self.assertEqual(Project.objects.all().count(), 1)
        self.assertEqual(Scenario.objects.all().count(), 2)

    def test_export_and_load_scenario_with_project_info(self):
        user = self.project.user

        dm = self.scenario.export(bind_project_data=True)
        json_dm = json.dumps(dm)

        self.assertIn("project", dm)
        self.assertNotIn("scenario_set_data", dm["project"])

        # A new project should be created
        load_scenario_from_dict(json.loads(json_dm), user)
        self.assertEqual(Project.objects.all().count(), 2)
        self.assertEqual(Scenario.objects.all().count(), 2)

    def test_load_scenario_without_project_raises_error(self):
        user = self.project.user

        dm = self.scenario.export()
        json_dm = json.dumps(dm)
        with pytest.raises(ValueError):
            load_scenario_from_dict(json.loads(json_dm), user)

    def test_export_and_load_project_without_scenarios(self):
        user = self.project.user

        dm = self.project.export()
        json_dm = json.dumps(dm)
        load_project_from_dict(json.loads(json_dm), user)

        self.assertEqual(Project.objects.all().count(), 2)

    def test_export_and_load_project_with_scenario(self):
        user = self.project.user

        dm = self.project.export(bind_scenario_data=True)
        json_dm = json.dumps(dm)
        load_project_from_dict(json.loads(json_dm), user)

        self.assertEqual(Project.objects.all().count(), 2)
        self.assertEqual(
            Project.objects.last().scenario_set.count(),
            self.project.scenario_set.count(),
        )

    def test_export_project_via_post_without_scenarios(self):
        response = self.client.post(
            reverse("project_export", args=[self.project.id]),
            dict(bind_scenario_data=False),
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("scenario_set_data", response.json())

    def test_export_project_via_post_with_scenarios(self):
        response = self.client.post(
            reverse("project_export", args=[self.project.id]),
            dict(bind_scenario_data=True),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("scenario_set_data", response.json())

    def test_export_project_via_get_with_scenarios(self):
        response = self.client.get(reverse("project_export", args=[self.project.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("scenario_set_data", response.json())


class UploadTimeseriesTest(TestCase):
    fixtures = ["fixtures/benchmarks_fixture.json"]

    @classmethod
    def setUpTestData(cls):
        pass

    def setUp(self):
        self.factory = RequestFactory()
        self.client.login(username="testUser", password="ASas12,.")
        self.project = Project.objects.get(id=1)

        # set up scenario for timeseries lengths of 4
        self.scenario = self.project.scenario_set.first()
        self.scenario.time_step = 360  # 6 hours
        self.scenario.evaluated_period = 1
        self.scenario.start_date = datetime.datetime(2020, 1, 1)
        self.scenario.save()

        self.post_url = reverse("asset_create_or_update", args=[2, "demand"])

    def test_load_demand_csv_timestamp_format(self):
        with open("./test_files/test_ts_timestamp_format.csv") as fp:
            data = {
                "name": "Test_input_timeseries",
                "pos_x": 0,
                "pos_y": 0,
                "input_timeseries_scalar": "",
                "input_timeseries_select": "",
                "input_timeseries_file": fp,
            }
            response = self.client.post(self.post_url, data, format="multipart")
            self.assertEqual(response.status_code, 200)
            asset = Asset.objects.last()
        self.assertEqual(asset.input_timeseries_values, [1, 2, 3, 4])

    def test_load_demand_csv_timestamp_format_reverse_raises_error(self):
        with open("./test_files/test_ts_timestamp_format_reverse.csv") as fp:
            data = {
                "name": "Test_input_timeseries",
                "pos_x": 0,
                "pos_y": 0,
                "input_timeseries_scalar": "",
                "input_timeseries_select": "",
                "input_timeseries_file": fp,
            }
            response = self.client.post(self.post_url, data, format="multipart")
            form = response.context["form"]
            self.assertIn("input_timeseries", form.errors)
            self.assertIn("invalid format", str(form.errors["input_timeseries"]))
            self.assertEqual(response.status_code, 422)

    def test_load_demand_csv_semicolon_format_decimal_comma(self):
        with open("./test_files/test_ts_semicolon_format_decimal_comma.csv") as fp:
            data = {
                "name": "Test_input_timeseries",
                "pos_x": 0,
                "pos_y": 0,
                "input_timeseries_scalar": "",
                "input_timeseries_select": "",
                "input_timeseries_file": fp,
            }
            response = self.client.post(self.post_url, data, format="multipart")
            self.assertEqual(response.status_code, 200)
            asset = Asset.objects.last()
        self.assertEqual(asset.input_timeseries_values, [8.5, 3.3, 4.0, 6.0])

    def test_load_demand_csv_semicolon_format_decimal_point(self):
        with open("./test_files/test_ts_semicolon_format_decimal_point.csv") as fp:
            data = {
                "name": "Test_input_timeseries",
                "pos_x": 0,
                "pos_y": 0,
                "input_timeseries_scalar": "",
                "input_timeseries_select": "",
                "input_timeseries_file": fp,
            }
            response = self.client.post(self.post_url, data, format="multipart")
            self.assertEqual(response.status_code, 200)
            asset = Asset.objects.last()
        self.assertEqual(asset.input_timeseries_values, [8.5, 3.3, 4.0, 6.0])

    def test_load_demand_csv_comma_format_decimal_point(self):
        with open("./test_files/test_ts_comma_format_decimal_point.csv") as fp:
            data = {
                "name": "Test_input_timeseries",
                "pos_x": 0,
                "pos_y": 0,
                "input_timeseries_scalar": "",
                "input_timeseries_select": "",
                "input_timeseries_file": fp,
            }
            response = self.client.post(self.post_url, data, format="multipart")
            self.assertEqual(response.status_code, 200)
            asset = Asset.objects.last()
        self.assertEqual(asset.input_timeseries_values, [8.5, 3.3, 4.0, 6.0])

    def test_load_demand_xlsx_double_timeseries(self):
        with open("./test_files/test_ts_double.xlsx", "rb") as fp:
            data = {
                "name": "Test_input_timeseries",
                "pos_x": 0,
                "pos_y": 0,
                "input_timeseries_scalar": "",
                "input_timeseries_select": "",
                "input_timeseries_file": fp,
            }
            response = self.client.post(self.post_url, data, format="multipart")
            self.assertEqual(response.status_code, 200)
            asset = Asset.objects.last()
        self.assertEqual(asset.input_timeseries_values, [1, 2, 3, 4])

    def test_load_demand_csv_1col_format_decimal_comma(self):
        with open("./test_files/test_ts_1col_format_decimal_comma.csv") as fp:
            data = {
                "name": "Test_input_timeseries",
                "pos_x": 0,
                "pos_y": 0,
                "input_timeseries_scalar": "",
                "input_timeseries_select": "",
                "input_timeseries_file": fp,
            }
            response = self.client.post(self.post_url, data, format="multipart")
            self.assertEqual(response.status_code, 200)
            asset = Asset.objects.last()
        self.assertEqual(asset.input_timeseries_values, [1.2, 2, 3.0, 4])

    def test_load_demand_csv_1col_format_decimal_point(self):
        with open("./test_files/test_ts_1col_format_decimal_point.csv") as fp:
            data = {
                "name": "Test_input_timeseries",
                "pos_x": 0,
                "pos_y": 0,
                "input_timeseries_scalar": "",
                "input_timeseries_select": "",
                "input_timeseries_file": fp,
            }
            response = self.client.post(self.post_url, data, format="multipart")
            self.assertEqual(response.status_code, 200)
            asset = Asset.objects.last()
        self.assertEqual(asset.input_timeseries_values, [1.2, 2, 3.0, 4])

    def test_load_demand_file_wrong_format_raises_error(self):
        with open("./test_files/test_ts_wrong_format.notsupported") as fp:
            data = {
                "name": "Test_input_timeseries",
                "pos_x": 0,
                "pos_y": 0,
                "input_timeseries_scalar": "",
                "input_timeseries_select": "",
                "input_timeseries_file": fp,
            }
            response = self.client.post(self.post_url, data, format="multipart")
            form = response.context["form"]
            self.assertIn("input_timeseries", form.errors)
            self.assertIn("not supported", str(form.errors["input_timeseries"]))
            self.assertEqual(response.status_code, 422)

    def test_load_demand_csv_semicolon_header_format_raises_error(self):
        with open(
            "./test_files/test_ts_semicolon_header_format_decimal_point.csv"
        ) as fp:
            data = {
                "name": "Test_input_timeseries",
                "pos_x": 0,
                "pos_y": 0,
                "input_timeseries_scalar": "",
                "input_timeseries_select": "",
                "input_timeseries_file": fp,
            }
            response = self.client.post(self.post_url, data, format="multipart")
            form = response.context["form"]
            self.assertIn("input_timeseries", form.errors)
            self.assertIn("invalid format", str(form.errors["input_timeseries"]))
            self.assertEqual(response.status_code, 422)

    def test_load_demand_csv_timeseries_timestep_length_mismatch_raises_error(self):
        with open("./test_files/test_ts_length_mismatch.csv") as fp:
            data = {
                "name": "Test_input_timeseries",
                "pos_x": 0,
                "pos_y": 0,
                "input_timeseries_scalar": "",
                "input_timeseries_select": "",
                "input_timeseries_file": fp,
            }
            response = self.client.post(self.post_url, data, format="multipart")
            form = response.context["form"]
            self.assertIn("input_timeseries", form.errors)
            self.assertEqual(response.status_code, 422)

    def test_scalar_timeseries(self):
        data = {
            "name": "Test_input_timeseries",
            "pos_x": 0,
            "pos_y": 0,
            "input_timeseries_scalar": 1,
            "input_timeseries_select": "",
            "input_timeseries_file": "",
        }
        response = self.client.post(self.post_url, data, format="multipart")
        asset = Asset.objects.last()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(asset.input_timeseries_values, [1])


class OptimizeCapacityToggleTest(TestCase):
    """optimize_cap toggle should zero out installed_capacity/age_installed
    when turned on, and reset maximum_capacity when turned off (forms.py
    AssetCreateForm.clean)."""

    fixtures = ["fixtures/benchmarks_fixture.json"]

    @classmethod
    def setUpTestData(cls):
        pass

    def setUp(self):
        self.client.login(username="testUser", password="ASas12,.")
        self.project = Project.objects.get(id=1)
        self.scenario = self.project.scenario_set.first()

        # the fixture predates "maximum_capacity" being added to this asset
        # type's visible fields, add it so both branches of the toggle can
        # be exercised
        self.asset_type = AssetType.objects.get(asset_type="transformer_station_in")
        self.asset_type.add_field("maximum_capacity")
        self.asset_type.save()

        self.post_url = reverse(
            "asset_create_or_update",
            args=[self.scenario.id, "transformer_station_in"],
        )

    def asset_data(self, **overrides):
        data = {
            "name": "Toggle test asset",
            "pos_x": 0,
            "pos_y": 0,
            "age_installed": 5,
            "installed_capacity": 50,
            "capex_fix": 1000,
            "capex_var": 10,
            "opex_fix": 5,
            "opex_var": 2,
            "lifetime": 10,
            "efficiency": 0.98,
            "maximum_capacity": 100,
        }
        data.update(overrides)
        return data

    def test_enabling_optimize_cap_resets_installed_capacity_and_age(self):
        response = self.client.post(self.post_url, self.asset_data(optimize_cap="true"))
        self.assertEqual(response.status_code, 200)

        asset = Asset.objects.get(unique_id=response.json()["asset_id"])
        self.assertTrue(asset.optimize_cap)
        self.assertEqual(asset.installed_capacity, 0.0)
        self.assertEqual(asset.age_installed, 0)
        # maximum_capacity is the optimization bound, kept as submitted
        self.assertEqual(asset.maximum_capacity, 100.0)

    def test_disabling_optimize_cap_resets_maximum_capacity(self):
        response = self.client.post(
            self.post_url, self.asset_data()
        )  # optimize_cap omitted -> False
        self.assertEqual(response.status_code, 200)

        asset = Asset.objects.get(unique_id=response.json()["asset_id"])
        self.assertFalse(asset.optimize_cap)
        self.assertIsNone(asset.maximum_capacity)
        self.assertEqual(asset.installed_capacity, 50.0)
        self.assertEqual(asset.age_installed, 5.0)

    def test_toggling_optimize_cap_on_clears_existing_capacity_and_age_on_update(self):
        create_response = self.client.post(self.post_url, self.asset_data())
        asset_uuid = create_response.json()["asset_id"]
        # reverse() can't place asset_uuid into this route's nested optional
        # group, so append it to the uuid-less URL instead
        update_url = f"{self.post_url}/{asset_uuid}"

        response = self.client.post(
            update_url, self.asset_data(optimize_cap="true", maximum_capacity=200)
        )
        self.assertEqual(response.status_code, 200)

        asset = Asset.objects.get(unique_id=asset_uuid)
        self.assertTrue(asset.optimize_cap)
        self.assertEqual(asset.installed_capacity, 0.0)
        self.assertEqual(asset.age_installed, 0)
        self.assertEqual(asset.maximum_capacity, 200.0)

    def test_toggling_optimize_cap_off_clears_maximum_capacity_on_update(self):
        create_response = self.client.post(
            self.post_url, self.asset_data(optimize_cap="true")
        )
        asset_uuid = create_response.json()["asset_id"]
        # reverse() can't place asset_uuid into this route's nested optional
        # group, so append it to the uuid-less URL instead
        update_url = f"{self.post_url}/{asset_uuid}"

        response = self.client.post(
            update_url,
            self.asset_data(
                installed_capacity=30, age_installed=3, maximum_capacity=999
            ),
        )
        self.assertEqual(response.status_code, 200)

        asset = Asset.objects.get(unique_id=asset_uuid)
        self.assertFalse(asset.optimize_cap)
        self.assertIsNone(asset.maximum_capacity)
        self.assertEqual(asset.installed_capacity, 30.0)
        self.assertEqual(asset.age_installed, 3.0)
