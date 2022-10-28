import json

import pytest
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse
from projects.models import Project, Scenario, Asset
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
        self
    ):
        pass

    # user not owner cannot share or revoke share rights

    def test_visit_create_scenario_link_from_landing_page_links_to_right_view(self):
        """Make sure a user clicking on create project link from does not experience errors"""
        response = self.client.get(reverse("scenario_steps", args=[self.project.id]))
        response = self.client.get(response.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "scenario/scenario_step1.html")


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
        self.post_url = reverse("asset_create_or_update", args=[2, "demand"])

    def test_load_demand_csv_double_timeseries(self):
        with open("./test_files/test_ts_double.csv") as fp:
            data = {
                "name": "Test_input_timeseries",
                "pos_x": 0,
                "pos_y": 0,
                "input_timeseries": fp,
            }
            response = self.client.post(self.post_url, data, format="multipart")
            self.assertEqual(response.status_code, 200)
            asset = Asset.objects.last()
        self.assertEqual(asset.input_timeseries_values, [1, 2, 3, 4])

    def test_load_demand_csv_double_decimal_point_with_comma(self):
        with open("./test_files/test_ts_csv_semicolon.csv") as fp:
            data = {
                "name": "Test_input_timeseries",
                "pos_x": 0,
                "pos_y": 0,
                "input_timeseries": fp,
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
                "input_timeseries": fp,
            }
            response = self.client.post(self.post_url, data, format="multipart")
            self.assertEqual(response.status_code, 200)
            asset = Asset.objects.last()
        self.assertEqual(asset.input_timeseries_values, [1, 2, 3, 4])

    def test_load_demand_csv_decimal_point_with_comma(self):
        with open("./test_files/test_ts_comma_decimal.csv") as fp:
            data = {
                "name": "Test_input_timeseries",
                "pos_x": 0,
                "pos_y": 0,
                "input_timeseries": fp,
            }
            response = self.client.post(self.post_url, data, format="multipart")
            self.assertEqual(response.status_code, 200)
            asset = Asset.objects.last()
        self.assertEqual(asset.input_timeseries_values, [1.2, 2, 3.0, 4])

    def test_load_demand_file_wrong_format_raises_error(self):
        with open("./test_files/test_ts.notsupported") as fp:
            data = {
                "name": "Test_input_timeseries",
                "pos_x": 0,
                "pos_y": 0,
                "input_timeseries": fp,
            }
            response = self.client.post(self.post_url, data, format="multipart")
            self.assertEqual(response.status_code, 422)
