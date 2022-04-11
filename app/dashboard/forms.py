from crispy_forms.helper import FormHelper
from django import forms
from django.utils.translation import ugettext_lazy as _
from django.forms import ModelForm
from dashboard.models import (
    ReportItem,
    AssetsResults,
    SensitivityAnalysisGraph,
    get_project_sensitivity_analysis,
)


from dashboard.helpers import (
    KPI_PARAMETERS,
    GRAPH_TIMESERIES,
    GRAPH_TIMESERIES_STACKED,
    GRAPH_CAPACITIES,
    GRAPH_BAR,
    GRAPH_PIE,
    GRAPH_LOAD_DURATION,
    GRAPH_SANKEY,
    GRAPH_SENSITIVITY_ANALYSIS,
)
from projects.models import ENERGY_VECTOR, Project


class ReportItemForm(ModelForm):

    scenarios = forms.ChoiceField(label=_("Scenario"))

    def __init__(self, *args, **kwargs):
        proj_id = kwargs.pop("proj_id", None)
        multi_scenario = kwargs.pop("multi_scenario", False)
        super().__init__(*args, **kwargs)

        if multi_scenario is True:
            self.fields["scenarios"] = forms.MultipleChoiceField(label=_("Scenarios"))

        if proj_id is not None:
            project = Project.objects.get(id=proj_id)
            self.fields["scenarios"].choices = [
                c
                for c in project.get_scenarios_with_results().values_list("id", "name")
            ]

    class Meta:
        model = ReportItem
        fields = ["report_type", "title"]
        labels = [_("Type of report item"), _("Title")]

    field_order = ["scenarios", "report_type", "title"]


class TimeseriesGraphForm(forms.Form):
    energy_vector = forms.MultipleChoiceField(
        label=_("Energy vector"), choices=ENERGY_VECTOR, initial=ENERGY_VECTOR[1][0]
    )
    y = forms.MultipleChoiceField(label=_("Timeseries variable(s)"), choices=tuple())

    def __init__(self, *args, **kwargs):
        scen_ids = kwargs.pop("scenario_ids", None)
        super().__init__(*args, **kwargs)

        if scen_ids is not None:
            # list available assets parameters for each simulations
            assets_results_across_simulations = AssetsResults.objects.filter(
                simulation__scenario__id__in=scen_ids
            )
            choices = None
            for assets_results in assets_results_across_simulations:
                new_choices = [(n, n) for n in assets_results.available_timeseries]
                if choices is None:
                    choices = set(new_choices)
                else:
                    choices = choices.intersection(new_choices)

            self.fields["y"].choices = tuple(choices)


class StackedTimeseriesGraphForm(forms.Form):
    energy_vector = forms.ChoiceField(
        label=_("Energy vector"), choices=ENERGY_VECTOR, initial=ENERGY_VECTOR[1][0]
    )
    y = forms.MultipleChoiceField(label=_("Timeseries variable(s)"), choices=tuple())

    def __init__(self, *args, **kwargs):
        scen_ids = kwargs.pop("scenario_ids", None)
        super().__init__(*args, **kwargs)

        if scen_ids is not None:
            # list available assets parameters for each simulations
            assets_results_across_simulations = AssetsResults.objects.filter(
                simulation__scenario__id__in=scen_ids
            )
            choices = None
            for assets_results in assets_results_across_simulations:
                new_choices = [(n, n) for n in assets_results.available_timeseries]
                if choices is None:
                    choices = set(new_choices)
                else:
                    choices = choices.intersection(new_choices)

            self.fields["y"].choices = tuple(choices)


class StackedCapacitiesGraphForm(forms.Form):
    energy_vector = forms.ChoiceField(
        label=_("Energy vector"), choices=ENERGY_VECTOR, initial=ENERGY_VECTOR[1][0]
    )
    y = forms.MultipleChoiceField(label=_("Component(s)"), choices=tuple())

    def __init__(self, *args, **kwargs):
        scen_ids = kwargs.pop("scenario_ids", None)
        super().__init__(*args, **kwargs)

        if scen_ids is not None:
            # list available assets parameters for each simulations
            assets_results_across_simulations = AssetsResults.objects.filter(
                simulation__scenario__id__in=scen_ids
            )
            choices = None
            for assets_results in assets_results_across_simulations:
                new_choices = [
                    (n, n)
                    for n in assets_results.available_timeseries
                    if assets_results.single_asset_type_oemof(n) != "sink"
                ]
                if choices is None:
                    choices = set(new_choices)
                else:
                    choices = choices.intersection(new_choices)
            self.fields["y"].choices = tuple(choices)


class SankeyGraphForm(forms.Form):
    energy_vector = forms.MultipleChoiceField(
        label=_("Energy vector"), choices=ENERGY_VECTOR, initial=ENERGY_VECTOR[1][0]
    )

    def __init__(self, *args, **kwargs):
        scen_ids = kwargs.pop("scenario_ids", None)
        super().__init__(*args, **kwargs)


class SensitivityAnalysisGraphForm(ModelForm):
    def __init__(self, *args, **kwargs):
        proj_id = kwargs.pop("proj_id", None)
        super().__init__(*args, **kwargs)

        if proj_id is not None:
            project = Project.objects.get(id=proj_id)
            self.fields["analysis"].choices = [
                (sa.id, sa.name) for sa in get_project_sensitivity_analysis(project)
            ]

    class Meta:
        model = SensitivityAnalysisGraph
        fields = ["analysis", "title", "y"]
        labels = [
            _("Sensitivity analysis"),
            _("Graph title"),
            _("Parameter of interest"),
        ]

    field_order = ["analysis", "title", "y"]


def graph_parameters_form_factory(report_type, *args, **kwargs):
    """Linked to dashboard/models.py:ReportItem.fetch_parameters_values"""
    if report_type == GRAPH_TIMESERIES:
        answer = TimeseriesGraphForm(*args, **kwargs)
    if report_type == GRAPH_TIMESERIES_STACKED:
        answer = StackedTimeseriesGraphForm(*args, **kwargs)
    if report_type == GRAPH_CAPACITIES:
        answer = StackedCapacitiesGraphForm(*args, **kwargs)
    # GRAPH_BAR,
    # GRAPH_PIE,
    # GRAPH_LOAD_DURATION,
    # GRAPH_SANKEY,
    if report_type == GRAPH_SANKEY:
        answer = SankeyGraphForm(*args, **kwargs)
    if report_type == GRAPH_SENSITIVITY_ANALYSIS:
        answer = SensitivityAnalysisGraphForm(*args, **kwargs)
    return answer
