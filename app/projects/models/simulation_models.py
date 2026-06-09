from projects.models.base_models import AbstractSimulation, Scenario, Asset


import json
import jsonschema
import numpy as np
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

from django.utils.translation import gettext_lazy as _
from datetime import datetime

from oemof.datapackage import datapackage
from oemof.eesyplan.datapackage.energy_system import create_energy_system_from_dp
import oemof.eesyplan as eesyplan

from projects.constants import (
    USER_RATING,
    DONE,
    PENDING,
    ERROR,
    PARAM_CATEGORY,
    PARAM_TYPE,
)
from projects.helpers import (
    sensitivity_analysis_payload,
    SA_OUPUT_NAMES_SCHEMA,
    sa_output_values_schema_generator,
    SA_RESPONSE_SCHEMA,
    format_scenario_for_mvs,
    parameters_helper,
    DP_RESULTS_SCHEMA,
    validate_dp_results,
)

from dashboard.helpers import nested_dict_crawler


class Simulation(AbstractSimulation):
    scenario = models.OneToOneField(Scenario, on_delete=models.CASCADE, null=False)
    user_rating = models.PositiveSmallIntegerField(
        null=True, choices=USER_RATING, default=None
    )
    dp_results = models.JSONField(
        null=True, blank=True, validators=[validate_dp_results]
    )

    def clean_dp_results(self):
        field = self._meta.get_field("dp_results")
        field.clean(self.dp_results, self)

    def eesyplan_results(self):
        results = None
        if self.dp_results is not None:
            rebuilt_dp = self.scenario.rebuild_datapackage()
            with tempfile.TemporaryDirectory(prefix="dp_") as td:
                temp_path = Path(td)
                dp_path = datapackage.rebuild_dp_from_json(rebuilt_dp, temp_path)
                es = create_energy_system_from_dp(dp_path)

                with tempfile.TemporaryDirectory(prefix="res_") as temp_res:
                    temp_res = Path(temp_res)
                    res_path = datapackage.rebuild_dp_from_json(
                        json.loads(self.dp_results), temp_res
                    )
                    results = eesyplan.import_results(res_path, es)
        return results


class ParameterChangeTracker(models.Model):
    name = models.CharField(max_length=60, null=False, blank=False)
    simulation = models.ForeignKey(
        Simulation, on_delete=models.CASCADE, null=False, blank=False
    )
    old_value = models.TextField(null=True, blank=False)
    new_value = models.TextField(null=True, blank=False)
    parameter_category = models.CharField(max_length=20, choices=PARAM_CATEGORY)
    parameter_type = models.CharField(
        null=True, blank=True, max_length=20, choices=PARAM_TYPE
    )
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.name} [{self.old_value}, {self.new_value}]"


class AssetChangeTracker(models.Model):
    name = models.CharField(max_length=60, null=False, blank=False)
    simulation = models.ForeignKey(
        Simulation, on_delete=models.CASCADE, null=False, blank=False
    )
    asset_dto = models.TextField(null=True, blank=True)
    action = models.SmallIntegerField(
        null=False, blank=False, choices=((0, "delete"), (0, "create"))
    )


class SensitivityAnalysis(AbstractSimulation):
    name = models.CharField(max_length=50)
    # attribute linked to output_parameter_names
    output_parameters_names = models.TextField()
    # attributes linked to variable_parameter_name
    variable_name = models.CharField(max_length=100)
    # attributes to compute the variable_parameter_range
    variable_min = models.FloatField()
    variable_max = models.FloatField()
    variable_step = models.FloatField(validators=[MinValueValidator(0.0)])
    # attributes linked to variable_parameter_ref_val
    variable_reference = models.FloatField(
        help_text=_(
            "The value of the variable parameter for the reference scenario of the sensitivity analysis, if is it different than the value of the current scenario user need to decide whether to take current scenario as reference with its actual value for this parameter, duplicate the scenario and use the duplicata with chosen reference value or keep current scenario but change parameter value to chosen one"
        )
    )  # label=_("Variable parameter of the reference scenario"),
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, null=True)
    # attribute linked to the output values of the sensitivity analysis
    output_parameters_values = models.TextField()
    nested_dict_pathes = None

    # TODO look at jsonschema to create a custon TextField --> https://dev.to/saadullahaleem/adding-validation-support-for-json-in-django-models-5fbm

    def save(self, *args, **kwargs):
        # if self.output_parameters_names is not None:
        #     self.output_parameters_names = json.dumps(self.output_parameters_names)
        super().save(*args, **kwargs)
        if self.scenario is not None:
            self.nested_dict_pathes = nested_dict_crawler(
                format_scenario_for_mvs(self.scenario)
            )

    def set_reference_scenario(self, scenario):
        self.scenario = scenario
        self.save()

    @property
    def variable_range(self):
        return np.arange(
            self.variable_min, self.variable_max, self.variable_step
        ).tolist()

    @property
    def output_names(self):
        try:
            answer = json.loads(self.output_parameters_names)
            try:
                jsonschema.validate(answer, SA_OUPUT_NAMES_SCHEMA)
            except jsonschema.exceptions.ValidationError:
                answer = []
        except json.decoder.JSONDecodeError:
            answer = []

        return answer

    @property
    def output_values(self):
        try:
            out_values = json.loads(self.output_parameters_values)
            answer = {}
            for in_value, sa_step in zip(self.variable_range, out_values):
                try:
                    jsonschema.validate(
                        sa_step, sa_output_values_schema_generator(self.output_names)
                    )
                    answer[in_value] = sa_step
                except jsonschema.exceptions.ValidationError:
                    answer[in_value] = None
        except json.decoder.JSONDecodeError:
            answer = {}
        return answer

    def graph_data(self, param_name):
        try:
            out_values = json.loads(self.output_parameters_values)
            answer = dict(x=[], y=[])
            if param_name not in self.output_names:
                logger.error(
                    f"The sensitivity analysis output parameter {param_name} is not present in the sensitivity analysis {self.name}"
                )
            else:
                for in_value, sa_step in zip(self.variable_range, out_values):
                    answer["x"].append(in_value)
                    try:
                        jsonschema.validate(
                            sa_step,
                            sa_output_values_schema_generator(self.output_names),
                        )

                        y_val = sa_step[param_name]["value"][0]

                    except jsonschema.exceptions.ValidationError:
                        y_val = np.nan

                    answer["y"].append(y_val)
        except json.decoder.JSONDecodeError:
            answer = {}
        return answer

    def parse_server_response(self, sa_results):
        try:
            # make sure the response is formatted as expected
            jsonschema.validate(sa_results, SA_RESPONSE_SCHEMA)
            self.status = sa_results["status"]
            self.errors = (
                json.dumps(sa_results["results"][ERROR])
                if self.status == ERROR
                else None
            )
            if self.status == DONE:
                sa_steps = sa_results["results"]["sensitivity_analysis_steps"]
                sa_steps_processed = []
                # make sure that each step is formatted as expected
                for step_idx, sa_step in enumerate(sa_steps):
                    try:
                        jsonschema.validate(
                            sa_step,
                            sa_output_values_schema_generator(self.output_names),
                        )
                        sa_steps_processed.append(sa_step)
                    except jsonschema.exceptions.ValidationError as e:
                        logger.error(
                            f"Could not parse the results of the sensitivity analysis {self.id} for step {step_idx}"
                        )
                        sa_steps_processed.append(None)
                self.output_parameters_values = json.dumps(sa_steps_processed)

        except jsonschema.exceptions.ValidationError as e:
            self.status = ERROR
            self.output_parameters_values = ""
            self.errors = str(e)

        self.elapsed_seconds = (datetime.now() - self.start_date).seconds
        self.end_date = (
            datetime.now() if sa_results["status"] in [ERROR, DONE] else None
        )
        self.save()

    @property
    def payload(self):
        return sensitivity_analysis_payload(
            variable_parameter_name=self.variable_name_path,
            variable_parameter_range=self.variable_range,
            variable_parameter_ref_val=self.variable_reference,
            output_parameter_names=self.output_names,
        )

    @property
    def variable_unit(self):
        if "." in self.variable_name:
            _, var_name = self.variable_name.split(".")
        else:
            var_name = self.variable_name

        return parameters_helper.get_doc_unit(var_name)

    @property
    def variable_name_verbose(self):
        if "." in self.variable_name:
            asset_name, variable_name = self.variable_name.split(".")
            answer = f"{parameters_helper.get_doc_verbose(variable_name)} of asset {asset_name}"
        else:
            answer = parameters_helper.get_doc_verbose(self.variable_name)
        return answer

    @property
    def variable_name_path(self):
        """Provided with a (nested) dict, find the path to the variable_name"""
        if self.nested_dict_pathes is None:
            variable_name_path = self.variable_name
        else:
            if "." in self.variable_name:
                asset_name, variable_name = self.variable_name.split(".")
            else:
                variable_name = self.variable_name
                asset_name = None
            variable_name_path = self.nested_dict_pathes.get(variable_name, None)
            if variable_name_path is None:
                if asset_name is not None:
                    asset = self.scenario.asset_set.get(name=asset_name)
                    variable_name_path = asset.parameter_path(variable_name)
                if variable_name_path is None:
                    logging.error(
                        f"The variable '{self.variable_name}' cannot be found in the scenario json structure"
                    )

            if isinstance(variable_name_path, list):
                variable_name_path = variable_name_path[0]
        return variable_name_path


def get_project_sensitivity_analysis(project):
    """Given a project, return the ReportItem instances linked to that project"""
    qs = (
        project.scenario_set.filter(simulation__isnull=False)
        .filter(simulation__results__isnull=False)
        .values_list("sensitivityanalysis", flat=True)
        .distinct()
    )
    return SensitivityAnalysis.objects.filter(id__in=[sa_id for sa_id in qs])
