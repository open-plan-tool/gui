import json
import logging
import os
import pickle

import numpy as np
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from dashboard.helpers import KPI_PARAMETERS_ASSETS
from django import forms
from django.conf import settings as django_settings
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import ModelForm
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from projects.constants import (
    ASSET_TO_TIMESERIES_ASSET_TYPE,
    CURRENCY_SYMBOLS,
    RENEWABLE_ASSETS,
)
from projects.helpers import (
    PARAMETERS,
    TS_MANUAL_TYPE,
    TS_SELECT_TYPE,
    TS_UPLOAD_TYPE,
    DualNumberField,
    TimeseriesField,
    parameters_helper,
)
from projects.models import *


def gettext_variables(some_string, lang="de"):
    """Save some expressions to be translated to a temporary file
    Because django makemessages cannot detect gettext with variables
    """

    some_string = str(some_string)

    trans_file = os.path.join(
        django_settings.STATIC_ROOT, f"personal_translation_{lang}.pickle"
    )

    if os.path.exists(trans_file):
        with open(trans_file, "rb") as handle:
            trans_dict = pickle.load(handle)
    else:
        trans_dict = {}

    if some_string is not None:
        if some_string not in trans_dict:
            trans_dict[some_string] = ""

        with open(trans_file, "wb") as handle:
            pickle.dump(trans_dict, handle, protocol=pickle.HIGHEST_PROTOCOL)


def add_help_text_icon(field, param_name, RTD_link=True):
    if field.help_text is not None:
        help_text = field.help_text + ". "
        field.help_text = None
    else:
        help_text = ""
    if field.label is not None:
        RTD_url = "https://open-plan-documentation.readthedocs.io/en/latest/model/input_parameters.html#"
        if param_name in PARAMETERS:
            param_ref = PARAMETERS[param_name]["label"].replace("_", "-")
        else:
            param_ref = ""
        if param_name != "name":
            if RTD_link is True:
                help_text += _("Click on the icon for more help") + "."
                question_icon = f'<a href="{RTD_url}{param_ref.lower()}" target="_blank" rel="noreferrer"><span class="icon icon-question" data-bs-toggle="tooltip" title="{help_text}"></span></a>'
            else:
                question_icon = f'<span class="icon icon-question" data-bs-toggle="tooltip" title="{help_text}"></span>'

        else:
            question_icon = ""
        field.label = mark_safe(field.label + question_icon)


def set_parameter_info(param_name, field, parameters=PARAMETERS):
    # For the storage unit
    if param_name.split("_")[0] in ("cp", "dchp", "chp"):
        param_name = "_".join(param_name.split("_")[1:])

    help_text = None
    unit = None
    verbose = None
    default_value = None
    if param_name == "optimize_cap":
        param_name = "optimize_capacity"
    if param_name in PARAMETERS:
        help_text = PARAMETERS[param_name][":Definition_Short:"]
        unit = PARAMETERS[param_name][":Unit:"]
        verbose = PARAMETERS[param_name]["verbose"]
        default_value = PARAMETERS[param_name][":Default:"]
        if unit == "None" or unit == "" or unit == "Factor":
            unit = None
        if verbose == "None":
            verbose = None
        if default_value == "None":
            default_value = None
    else:
        logging.debug(f"{param_name} not in the parameters file")

    if verbose is not None:
        field.label = verbose
    if unit is not None:
        field.label = _(str(field.label)) + " (" + _(unit) + ")"
    else:
        field.label = _(str(field.label))

    if help_text is not None:
        field.help_text = _(help_text)

    if default_value is not None:
        field.initial = default_value


class OpenPlanModelForm(ModelForm):
    """Class to automatize the assignation and translation of the labels, help_text and units"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fieldname, field in self.fields.items():
            set_parameter_info(fieldname, field)

    def add_help_text_icon(self, param_name, RTD_link=True):
        if param_name in self.fields:
            add_help_text_icon(self.fields[param_name], param_name, RTD_link)


class OpenPlanForm(forms.Form):
    """Class to automatize the assignation and translation of the labels, help_text and units"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fieldname, field in self.fields.items():
            set_parameter_info(fieldname, field)
            add_help_text_icon(field, fieldname, RTD_link=False)


class FeedbackForm(ModelForm):
    class Meta:
        model = Feedback
        exclude = ["id", "rating"]


class ProjectDetailForm(ModelForm):
    class Meta:
        model = Project
        exclude = ["date_created", "date_updated", "economic_data", "user", "viewers"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.disabled = True


class EconomicDataDetailForm(OpenPlanModelForm):
    class Meta:
        model = EconomicData
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.disabled = True


economic_widgets = {
    "discount": forms.NumberInput(
        attrs={
            "placeholder": _("eg. 0.1"),
            "min": "0.0",
            "max": "1.0",
            "step": "0.0001",
            "title": _("Investment Discount factor."),
        }
    ),
    "tax": forms.HiddenInput(
        attrs={
            "placeholder": "eg. 0.3",
            "min": "0.0",
            "max": "1.0",
            "step": "0.0001",
            "value": 0,
        }
    ),
}


class EconomicDataUpdateForm(OpenPlanModelForm):
    class Meta:
        model = EconomicData
        fields = "__all__"
        widgets = economic_widgets


class ProjectCreateForm(OpenPlanForm):
    name = forms.CharField(
        label=_("Project Name"),
        help_text=_("A self explanatory name for the project."),
        widget=forms.TextInput(
            attrs={
                "placeholder": _("Name..."),
            }
        ),
    )
    description = forms.CharField(
        label=_("Project Description"),
        help_text=_("A description of what this project objectives or test cases."),
        widget=forms.Textarea(
            attrs={
                "placeholder": _("More detailed description here..."),
                "data-bs-toggle": "tooltip",
            }
        ),
    )
    country = forms.ChoiceField(
        label=_("Country"),
        help_text=_("Name of the country where the project is being deployed"),
        choices=COUNTRY,
        widget=forms.Select(),
    )
    longitude = forms.FloatField(
        label=_("Location, longitude"),
        help_text=_("Longitude coordinate of the project's geographical location."),
        widget=forms.NumberInput(
            attrs={
                "placeholder": _("click on the map"),
                "readonly": "",
            }
        ),
    )
    latitude = forms.FloatField(
        label=_("Location, latitude"),
        help_text=_("Latitude coordinate of the project's geographical location."),
        widget=forms.NumberInput(
            attrs={
                "placeholder": _("click on the map"),
                "readonly": "",
            }
        ),
    )
    duration = forms.IntegerField(
        label=_("Project Duration"),
        help_text=_(
            "The number of years the project is intended to be operational. The project duration also sets the installation time of the assets used in the simulation. After the project ends these assets are 'sold' and the refund is charged against the initial investment costs."
        ),
        widget=forms.NumberInput(
            attrs={
                "placeholder": _("eg. 1"),
                "min": "0",
                "max": "100",
                "step": "1",
            }
        ),
    )
    currency = forms.ChoiceField(
        label=_("Currency"),
        choices=CURRENCY,
        help_text=_("The currency of the country where the project is implemented."),
        widget=forms.Select(),
    )
    discount = forms.FloatField(
        label=_("Discount Factor"),
        help_text=_(
            "Discount factor is the factor which accounts for the depreciation in the value of money in the future, compared to the current value of the same money. The common method is to calculate the weighted average cost of capital (WACC) and use it as the discount rate."
        ),
        widget=forms.NumberInput(
            attrs={
                "placeholder": _("eg. 0.1"),
                "min": "0.0",
                "max": "1.0",
                "step": "0.0001",
            }
        ),
    )
    tax = forms.FloatField(
        label=_("Tax"),
        help_text=_("Tax factor"),
        widget=forms.HiddenInput(
            attrs={
                "placeholder": _("eg. 0.3"),
                "min": "0.0",
                "max": "1.0",
                "step": "0.0001",
                "value": 0,
            }
        ),
    )

    # Render form
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = "project_form_id"
        # self.helper.form_class = 'blueForm'
        self.helper.form_method = "post"
        self.helper.add_input(Submit("submit", "Submit"))

        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-lg-8"
        self.helper.field_class = "col-lg-10"


class ProjectUpdateForm(OpenPlanModelForm):
    class Meta:
        model = Project
        exclude = ["date_created", "date_updated", "economic_data", "user", "viewers"]


class ProjectShareForm(ModelForm):
    email = forms.EmailField(label=_("Email address"))

    class Meta:
        model = Viewer
        exclude = ["id", "user"]


class ProjectRevokeForm(ModelForm):
    class Meta:
        model = Project
        fields = ["viewers"]
        widgets = {"viewers": forms.SelectMultiple()}
        help_texts = {
            "viewers": _(
                "Select the user(s) for which you want to revoke access rights "
            )
        }
        labels = {"viewers": _("Users currently having access to the project")}

    def __init__(self, *args, **kwargs):
        proj_id = kwargs.pop("proj_id", None)
        super().__init__(*args, **kwargs)
        self.fields["viewers"].empty_label = _("No users have access to this project")
        self.fields["viewers"].required = False
        if proj_id is not None:
            self.fields["viewers"].queryset = Project.objects.get(
                id=proj_id
            ).viewers.all()


class UploadFileForm(forms.Form):
    name = forms.CharField(required=False)
    file = forms.FileField()

    def __init__(self, *args, **kwargs):
        labels = kwargs.pop("labels", None)
        super().__init__(*args, **kwargs)
        if labels is not None:
            for field in labels:
                self.fields[field].label = _(labels[field])


class UseCaseForm(forms.Form):
    usecase = forms.ChoiceField()

    def __init__(self, *args, **kwargs):
        usecase_qs = kwargs.pop("usecase_qs")
        usecase_url = kwargs.pop("usecase_url", "usecase_url")
        super().__init__(*args, **kwargs)
        if usecase_qs is not None:
            self.fields["usecase"].choices = [(uc.id, _(uc.name)) for uc in usecase_qs]
            self.fields["usecase"].label = (
                _("Select a use case (or")
                + f"<a href='{usecase_url}'>"
                + _("visit use cases page")
                + "</a>)"
            )


class CommentForm(ModelForm):
    class Meta:
        model = Comment
        exclude = ["id", "project"]


# region Scenario
# TODO build this from the documentation with a for loop over the keys
scenario_widgets = {
    "name": forms.TextInput(attrs={"placeholder": "Scenario name"}),
    "start_date": forms.DateInput(
        format="%Y-%m-%d",
        attrs={
            "class": "TestDateClass",
            "placeholder": "Select a start date",
            "type": "date",
        },
    ),
    "time_step": forms.Select(
        attrs={
            "placeholder": "eg. 120 minutes",
            "min": "1",
            "max": "600",
            "step": "1",
            "data-bs-toggle": "tooltip",
            "title": _("Length of the time steps"),
        },
        choices=((60, "60 min"),),
    ),
    "evaluated_period": forms.NumberInput(
        attrs={
            "placeholder": "eg. 10 days",
            "min": "1",
            "step": "1",
            "data-bs-toggle": "tooltip",
            "title": _("Number of days simulated with the energy system model."),
        }
    ),
    "capex_fix": forms.NumberInput(
        attrs={
            "placeholder": "e.g. 10000€",
            "min": "0",
            "data-bs-toggle": "tooltip",
            "title": _(
                "A fixed cost to implement the asset, eg. planning costs which do not depend on the (optimized) asset capacity."
            ),
        }
    ),
}

scenario_labels = {
    "project": _("Project"),
    "name": _("Scenario name"),
    "description": _("Scenario description"),
    "evaluated_period": _("Evaluated Period"),
    "time_step": _("Time Step"),
    "start_date": _("Start Date"),
    "capex_fix": _("Development costs"),
}

scenario_field_order = [
    "project",
    "name",
    "description",
    "evaluated_period",
    "time_step",
    "start_date",
    "capex_fix",
]


class ScenarioCreateForm(OpenPlanModelForm):
    field_order = scenario_field_order

    class Meta:
        model = Scenario
        exclude = ["id", "capex_var", "opex_fix", "opex_var"]
        widgets = scenario_widgets
        labels = scenario_labels

    def __init__(self, *args, **kwargs):
        project_queryset = kwargs.pop("project_queryset", None)
        super().__init__(*args, **kwargs)
        if project_queryset is not None:
            self.fields["project"].queryset = project_queryset
        else:
            self.fields["project"] = forms.ChoiceField(label="Project", choices=())
        for visible in self.visible_fields():
            visible.field.widget.attrs["class"] = "form-control"


class ScenarioSelectProjectForm(OpenPlanModelForm):
    field_order = scenario_field_order

    class Meta:
        model = Scenario
        fields = ["project"]
        widgets = scenario_widgets
        labels = scenario_labels

    def __init__(self, *args, **kwargs):
        project_queryset = kwargs.pop("project_queryset", None)
        super().__init__(*args, **kwargs)
        if project_queryset is not None:
            self.fields["project"] = forms.ChoiceField(
                label="Project",
                choices=[p for p in project_queryset.values_list("id", "label")],
            )

        else:
            self.fields["project"] = forms.ChoiceField(label="Project", choices=())
        for visible in self.visible_fields():
            visible.field.widget.attrs["class"] = "form-control"


class ScenarioUpdateForm(OpenPlanModelForm):
    field_order = scenario_field_order

    class Meta:
        model = Scenario
        exclude = ["id", "capex_var", "opex_fix", "opex_var"]
        widgets = scenario_widgets
        labels = scenario_labels

    def __init__(self, *args, **kwargs):
        project_queryset = kwargs.pop("project_queryset", None)
        super().__init__(*args, **kwargs)
        if project_queryset is not None:
            self.fields["project"] = forms.ChoiceField(
                label="Project",
                choices=[p for p in project_queryset.values_list("id", "label")],
            )

        else:
            self.fields["project"] = forms.ChoiceField(label="Project", choices=())

        for visible in self.visible_fields():
            visible.field.widget.attrs["class"] = "form-control"
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_tag = False  # don't include <form> tag


# endregion Scenario


class ConstraintForm(OpenPlanModelForm):
    """Introduces a way to carry i18n strings into template for help texts"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["help_text"] = forms.CharField(
            widget=forms.HiddenInput(), required=False
        )


class MinRenewableConstraintForm(ConstraintForm):
    class Meta:
        model = MinRenewableConstraint
        exclude = ["scenario"]


class MaxEmissionConstraintForm(ConstraintForm):
    class Meta:
        model = MaxEmissionConstraint
        exclude = ["scenario"]


class MinDOAConstraintForm(ConstraintForm):
    class Meta:
        model = MinDOAConstraint
        exclude = ["scenario"]


class NZEConstraintForm(ConstraintForm):
    class Meta:
        model = NZEConstraint
        exclude = ["scenario", "value"]


class SensitivityAnalysisForm(ModelForm):
    output_parameters_names = forms.MultipleChoiceField(
        choices=[
            (v, _(KPI_PARAMETERS_ASSETS[v]["verbose"])) for v in KPI_PARAMETERS_ASSETS
        ]
    )

    class Meta:
        model = SensitivityAnalysis
        fields = [
            "name",
            "variable_name",
            "variable_min",
            "variable_max",
            "variable_step",
            "variable_reference",
            "output_parameters_names",
        ]

    def __init__(self, *args, **kwargs):
        scen_id = kwargs.pop("scen_id", None)
        super().__init__(*args, **kwargs)

        forbidden_parameters_for_sa = ("name", "input_timeseries")

        if scen_id is not None:
            scenario = Scenario.objects.get(id=scen_id)
            asset_parameters = []
            for asset in scenario.asset_set.all():
                asset_parameters += [
                    (
                        f"{asset.name}.{p}",
                        _(parameters_helper.get_doc_verbose(p)) + f" ({asset.name})",
                    )
                    for p in asset.visible_fields
                    if p not in forbidden_parameters_for_sa
                ]
            self.fields["variable_name"] = forms.ChoiceField(choices=asset_parameters)
            # self.fields["output_parameters_names"] = forms.MultipleChoiceField(choices = [(v, _(KPI_PARAMETERS_ASSETS[v]["verbose"])) for v in KPI_PARAMETERS_ASSETS])
            # TODO restrict possible parameters here
            self.fields["output_parameters_names"].choices = [
                (v, _(KPI_PARAMETERS_ASSETS[v]["verbose"]))
                for v in KPI_PARAMETERS_ASSETS
            ]

    def clean_output_parameters_names(self):
        """method which gets called upon form validation"""
        data = self.cleaned_data["output_parameters_names"]
        data_js = json.dumps(data)
        return data_js


class COPCalculatorForm(OpenPlanModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["temperature_high"] = DualNumberField(
            default=60, min=-273, param_name="temperature_high"
        )
        self.fields["temperature_low"] = DualNumberField(
            default=40, min=-273, param_name="temperature_low"
        )
        # Reset labels, units, help text etc. (deleted when defining as DualNumberField)
        for field in ["temperature_low", "temperature_high"]:
            set_parameter_info(field, self.fields[field])

        for field in self.fields:
            self.add_help_text_icon(field, RTD_link=True)

    class Meta:
        model = COPCalculator
        exclude = ["id", "scenario", "asset", "mode"]


class BusForm(OpenPlanModelForm):
    def __init__(self, *args, **kwargs):
        bus_type_name = kwargs.pop("asset_type", None)  # always = bus
        view_only = kwargs.pop("view_only", False)
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({f"df-{field}": ""})
            if view_only is True:
                self.fields[field].disabled = True

    class Meta:
        model = Bus
        fields = ["name", "type"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Bus Name",
                    "style": "font-weight:400; font-size:13px;",
                }
            ),
            "type": forms.Select(
                choices=ENERGY_VECTOR,
                attrs={
                    "data-bs-toggle": "tooltip",
                    "title": _("The energy Vector of the connected assets."),
                    "style": "font-weight:400; font-size:13px;",
                },
            ),
        }
        labels = {"name": _("Name"), "type": _("Energy carrier")}


class ToggleSwitchWidget(forms.CheckboxInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def render(self, name, value, attrs=None, renderer=None):
        checkbox_html = super().render(name, value, attrs, renderer)
        return format_html(
            '<label class="toggle-switch">{}<span class="toggle-slider"></span></label>',
            checkbox_html,
        )


class AssetCreateForm(OpenPlanModelForm):
    def __init__(self, *args, **kwargs):
        self.asset_type_name = kwargs.pop("asset_type", None)
        proj_id = kwargs.pop("proj_id", None)
        scenario_id = kwargs.pop("scenario_id", None)
        view_only = kwargs.pop("view_only", False)
        self.existing_asset = kwargs.get("instance")
        # get the connections with busses
        self.input_output_mapping = kwargs.pop("input_output_mapping", None)

        super().__init__(*args, **kwargs)
        # which fields exists in the form are decided upon AssetType saved in the db
        self.asset_type = AssetType.objects.get(asset_type=self.asset_type_name)

        # remove the fields not needed for the AssetType
        for field in list(self.fields):
            if field not in self.asset_type.visible_fields:
                self.fields.pop(field)
            else:
                self.add_help_text_icon(field)

        self.timestamps = None
        if scenario_id is not None:
            qs = Scenario.objects.filter(id=scenario_id)
            if qs.exists():
                self.scenario = qs.get()
                self.timestamps = self.scenario.get_timestamps()
                self.user = self.scenario.project.user
                if proj_id is None:
                    proj_id = self.scenario.project.id
        elif self.existing_asset is not None:
            self.timestamps = self.existing_asset.timestamps
            self.user = self.existing_asset.scenario.project.user

        currency = None
        if proj_id is not None:
            qs = Project.objects.filter(id=proj_id)
            if qs.exists():
                currency = qs.values_list("economic_data__currency", flat=True).get()
                currency = CURRENCY_SYMBOLS[currency]
                # TODO use mapping to display currency symbol
                self.user = qs.get().user

        # set the custom timeseries field for timeseries
        # the qs_ts selects timeseries (excluding scalars) that either belong to the user or are open source
        if "input_timeseries" in self.fields:
            self.fields["input_timeseries"] = TimeseriesField(
                qs_ts=Timeseries.objects.filter(
                    ~Q(ts_type="scalar")
                    & (Q(asset_type=self.asset_type.asset_type))
                    & (Q(open_source=True) | Q(user=self.user))
                ),
                default=0,
                param_name="input_timeseries",
                label=self.fields["input_timeseries"].label,
                asset_type=self.asset_type_name,
            )
            # TODO here one can play with min, max, max_length as kwargs

        self.fields["inputs"] = forms.CharField(
            widget=forms.HiddenInput(), required=False, label=""
        )

        if self.asset_type_name == "heat_pump":
            self.fields["efficiency"] = DualNumberField(
                default=1, min=1, param_name="efficiency"
            )
            self.fields["efficiency"].label = "COP"
            self.fields["efficiency"].help_text = "This is the custom help text for COP"
            self.add_help_text_icon("efficiency", RTD_link=True)
            value = self.fields.pop("efficiency")
            self.fields["efficiency"] = value
        if self.asset_type_name == "chp":
            self.fields["efficiency"] = DualNumberField(
                default=1, min=0, max=1, param_name="efficiency"
            )
            self.fields["efficiency"].label = _(
                "Electrical efficiency with no heat extraction"
            )

            self.fields[
                "efficiency"
            ].help_text = "This is the custom help text for chp efficiency"
            self.add_help_text_icon("efficiency", RTD_link=True)
            self.fields["efficiency_multiple"] = DualNumberField(
                default=1, min=0, max=1, param_name="efficiency_multiple"
            )
            self.fields["efficiency_multiple"].label = _(
                "Thermal efficiency with maximal heat extraction"
            )

            self.fields["thermal_loss_rate"].label = _("Power loss index")

        if self.asset_type_name == "chp_fixed_ratio":
            self.fields["efficiency"].label = _("Efficiency gas to electricity")

            # TODO
            self.fields[
                "efficiency"
            ].help_text = "This is the custom help text for chp efficiency"
            self.add_help_text_icon("efficiency", RTD_link=True)

            self.fields["efficiency_multiple"].widget = forms.NumberInput(
                attrs={
                    "placeholder": _("eg. 0.1"),
                    "min": 0.0,
                    "max": 1.0,
                    "step": "0.00001",
                }
            )
            self.fields["efficiency_multiple"].label = _("Efficiency gas to heat")

        if self.asset_type_name == "electrolyzer":
            self.fields["efficiency_multiple"].widget = forms.NumberInput(
                attrs={
                    "placeholder": _("eg. 0.1"),
                    "min": 0.0,
                    "max": 1.0,
                    "value": 0,
                    "step": "0.00001",
                }
            )
            self.fields["efficiency_multiple"].label = _("Heat loss")
            self.fields[
                "efficiency_multiple"
            ].help_text = "Ratio of energy converted to heat"
            self.add_help_text_icon("efficiency_multiple", RTD_link=True)

        if "dso" in self.asset_type_name:
            for field_name in ("energy_price", "feedin_tariff"):
                help_text = self.fields[field_name].help_text
                label = self.fields[field_name].label
                self.fields[field_name] = DualNumberField(
                    default=0.1, param_name=field_name
                )
                self.fields[field_name].help_text = help_text
                self.fields[field_name].label = label

        """ DrawFlow specific configuration, add a special attribute to
            every field in order for the framework to be able to export
            the data to json.
            !! This addition doesn't affect the previous behavior !!
        """
        for field in self.fields:
            if field == "renewable_asset" and self.asset_type_name in RENEWABLE_ASSETS:
                self.initial[field] = True
            self.fields[field].widget.attrs.update({f"df-{field}": ""})
            if field == "input_timeseries":
                self.fields[field].required = self.is_input_timeseries_empty()
            if view_only is True:
                self.fields[field].disabled = True
                if "capex_fix" in field:
                    self.fields[field].label = (
                        self.fields[field]
                        .label.replace("project", "")
                        .replace("Feste Projektkosten", "Fixkosten")
                    )
            if "€" in self.fields[field].label and currency is not None:
                self.fields[field].label = self.fields[field].label.replace(
                    "€", currency
                )
            if ":unit:" in self.fields[field].label:
                self.fields[field].label = self.fields[field].label.replace(
                    ":unit:", self.asset_type.unit
                )

            self.fields[field].label = format_html(self.fields[field].label)

        """ ----------------------------------------------------- """

    def is_input_timeseries_empty(self):
        if self.existing_asset is not None:
            return self.existing_asset.is_input_timeseries_empty()
        else:
            return True

    def clean_input_timeseries_old(self):
        """Override built-in Form method which is called upon form validation"""
        try:
            input_timeseries_values = []
            timeseries_file = self.files.get("input_timeseries_file", None)
            # read the timeseries from file if any
            if timeseries_file is not None:
                input_timeseries_values = parse_input_timeseries(timeseries_file)
                # TODO here list the possible options
            # set the previous timeseries from the asset if any
            elif self.is_input_timeseries_empty() is False:
                input_timeseries_values = self.existing_asset.input_timeseries_values
            return input_timeseries_values
        except json.decoder.JSONDecodeError as ex:
            raise ValidationError(
                _(
                    "File not properly formatted. Please ensure you upload a comma separated array of values. E.g. [1,2,0.32]"
                )
            )
        except TypeError as e:
            raise ValidationError(str(e))
        except Exception as ex:
            raise ValidationError(
                _(
                    f"Could not parse a file due to the following error: {ex}. Did you upload a file?"
                )
            )

    def clean_efficiency_multiple(self):
        data = self.cleaned_data["efficiency_multiple"]
        if self.asset_type_name == "chp_fixed_ratio":
            try:
                data = float(data)
            except ValueError:
                raise ValidationError("Please enter a float value between 0.0 and 1.0")
            if 0 <= data <= 1:
                pass
            else:
                raise ValidationError("Please enter a float value between 0.0 and 1.0")
            data = str(data)
        return data

    def clean(self):
        cleaned_data = super().clean()
        if "installed_capacity" in cleaned_data and "age_installed" in cleaned_data:
            if (
                cleaned_data["installed_capacity"] == 0.0
                and cleaned_data["age_installed"] > 0
            ):
                self.add_error(
                    "age_installed",
                    _(
                        "If you have no installed capacity, age installed should also be 0"
                    ),
                )

        # If optimize capacity is selected, set the installed capacity and age to zero (as they are explicitly hidden in the form but might contain old values)
        # otherwise reset maximum capacity instead
        if "optimize_cap" in cleaned_data:
            if cleaned_data["optimize_cap"]:
                cleaned_data["age_installed"] = 0
                cleaned_data["installed_capacity"] = 0.0
            else:
                cleaned_data["maximum_capacity"] = None

        if self.asset_type_name == "heat_pump":
            if "efficiency" not in self.errors:
                efficiency = cleaned_data["efficiency"]
                self.timeseries_same_as_timestamps(efficiency, "efficiency")

        if self.asset_type_name == "chp_fixed_ratio":
            # efficiency and efficiency_multiple must have been cleaned (no errors)
            if self.errors.keys().isdisjoint({"efficiency", "efficiency_multiple"}):
                if (
                    float(cleaned_data["efficiency"])
                    + float(cleaned_data["efficiency_multiple"])
                    > 1
                ):
                    msg = _("The sum of the efficiencies should not exceed 1")
                    self.add_error("efficiency", msg)
                    self.add_error("efficiency_multiple", msg)

        if "dso" in self.asset_type_name:
            if "feedin_tariff" not in self.errors and "energy_price" not in self.errors:
                feedin_tariff = np.array([cleaned_data["feedin_tariff"]])
                energy_price = np.array([cleaned_data["energy_price"]])
                diff = feedin_tariff - energy_price
                max_capacity = cleaned_data.get("max_capacity", 0)
                if (diff > 0).any() is True and max_capacity == 0:
                    msg = _(
                        "Feed-in tariff > energy price for some of simulation's timesteps. This would cause an unbound solution and terminate the optimization. Please reconsider your feed-in tariff and energy price."
                    )
                    self.add_error("feedin_tariff", msg)
                self.timeseries_same_as_timestamps(feedin_tariff, "feedin_tariff")
                self.timeseries_same_as_timestamps(energy_price, "energy_price")

        if "input_timeseries" in cleaned_data:
            # TODO add either a checkbox or a user setting to save ts to model
            ts_data = json.loads(cleaned_data["input_timeseries"])
            input_method = ts_data["input_method"]["type"]
            if input_method == TS_UPLOAD_TYPE or input_method == TS_MANUAL_TYPE:
                # replace the dict with a new timeseries instance
                timeseries_obj = self.assign_timeseries_from_input(ts_data)
                if input_method == TS_UPLOAD_TYPE:
                    self.timeseries_same_as_timestamps(
                        timeseries_obj.values, "input_timeseries"
                    )
                cleaned_data["input_timeseries"] = timeseries_obj
            if input_method == TS_SELECT_TYPE:
                # return the timeseries instance
                timeseries_id = ts_data["input_method"]["extra_info"]
                cleaned_data["input_timeseries"] = Timeseries.objects.get(
                    id=timeseries_id
                )

        return cleaned_data

    def assign_timeseries_from_input(self, input_timeseries):
        # Assign the existing timeseries if already uploaded by the same user, else create a new instance
        timeseries_name = input_timeseries["input_method"].get("extra_info", "no_name")
        timeseries_values = input_timeseries["values"]

        ts_default_settings = {
            "ts_type": self.asset_type.mvs_type,
            "open_source": False,
        }
        asset_type_name = self.asset_type.asset_type
        ts_asset_type = ASSET_TO_TIMESERIES_ASSET_TYPE.get(asset_type_name)

        if input_timeseries["input_method"]["type"] == TS_MANUAL_TYPE:
            if len(timeseries_values) == 1:
                timeseries_name = f"constant value = {timeseries_values[0]}"
                ts_default_settings["ts_type"] = "scalar"
            else:
                timeseries_name = f"Created timeseries ({self.asset_type_name})"
                generation_parameters = input_timeseries["input_method"].get(
                    "generation_parameters"
                )
                if generation_parameters:
                    ts_default_settings["generation_parameters"] = generation_parameters

        timeseries, created = Timeseries.objects.get_or_create(
            values=timeseries_values,
            user=self.user,
            name=timeseries_name,
            scenario=self.scenario,
            asset_type=ts_asset_type,
            defaults=ts_default_settings,
        )

        return timeseries

    def timeseries_same_as_timestamps(self, ts, param):
        if isinstance(ts, np.ndarray):
            ts = np.squeeze(ts).tolist()
        if isinstance(ts, float) is False and isinstance(ts, int) is False:
            if len(ts) > 1:
                if self.timestamps is not None:
                    if len(ts) != len(self.timestamps):
                        # TODO look for verbose of param
                        msg = (
                            _("The number of values of the parameter ")
                            + _(param)
                            + f" ({len(ts)})"
                            + _(" are not equal to the number of simulation timesteps")
                            + f" ({len(self.timestamps)})"
                            + _(
                                ". You can change the number of timesteps in the first step of scenario creation."
                            )
                        )
                        self.add_error(param, msg)

    class Meta:
        model = Asset
        exclude = ["scenario"]
        widgets = {
            "optimize_cap": ToggleSwitchWidget(),
            "dispatchable": ToggleSwitchWidget(),
            "renewable_asset": ToggleSwitchWidget(),
            "name": forms.TextInput(
                attrs={
                    "placeholder": _("Asset Name"),
                    # "style": "font-weight:400; font-size:13px;",
                }
            ),
            "capex_fix": forms.NumberInput(
                attrs={"placeholder": "e.g. 10000", "min": "0.0", "step": ".01"}
            ),
            "capex_var": forms.NumberInput(
                attrs={"placeholder": "e.g. 4000", "min": "0.0", "step": ".01"}
            ),
            "opex_fix": forms.NumberInput(
                attrs={"placeholder": "e.g. 0", "min": "0.0", "step": ".01"}
            ),
            "opex_var": forms.NumberInput(
                attrs={"placeholder": "Currency", "min": "0.0", "step": ".01"}
            ),
            "lifetime": forms.NumberInput(
                attrs={"placeholder": "e.g. 10 years", "min": "0", "step": "1"}
            ),
            "input_timeseries_old": forms.FileInput(
                attrs={
                    "onchange": "plot_file_trace(obj=this.files, plot_id='timeseries_trace')"
                }
            ),
            "crate": forms.NumberInput(
                attrs={
                    "placeholder": "factor of total capacity (kWh), e.g. 0.7",
                    "min": "0.0",
                    "max": "1.0",
                    "step": ".0001",
                }
            ),
            "efficiency": forms.NumberInput(
                attrs={
                    "placeholder": "e.g. 0.99",
                    "min": "0.0",
                    "max": "1.0",
                    "step": ".01",
                }
            ),
            "soc_max": forms.NumberInput(
                attrs={
                    "placeholder": "e.g. 0.95",
                    "min": "0.0",
                    "max": "1.0",
                    "step": ".01",
                }
            ),
            "soc_min": forms.NumberInput(
                attrs={
                    "placeholder": "e.g. 0.1",
                    "min": "0.0",
                    "max": "1.0",
                    "step": ".01",
                }
            ),
            "maximum_capacity": forms.NumberInput(
                attrs={"placeholder": "e.g. 1000", "min": "0.0", "step": ".01"}
            ),
            "energy_price": forms.NumberInput(
                attrs={"placeholder": "e.g. 0.1", "min": "0.0", "step": ".0001"}
            ),
            "feedin_tariff": forms.NumberInput(
                attrs={"placeholder": "e.g. 0.0", "min": "0.0", "step": ".0001"}
            ),
            "feedin_cap": forms.NumberInput(
                attrs={"placeholder": "e.g. 0.0", "min": "0.0"}
            ),
            "peak_demand_pricing": forms.NumberInput(
                attrs={"placeholder": "e.g. 60", "min": "0.0", "step": ".01"}
            ),
            "peak_demand_pricing_period": forms.Select(
                choices=((1, 1), (2, 2), (3, 3), (4, 4), (6, 6), (12, 12))
            ),
            "renewable_share": forms.NumberInput(
                attrs={
                    "placeholder": "e.g. 0.1",
                    "min": "0.0",
                    "max": "1.0",
                    "step": ".0001",
                }
            ),
            "installed_capacity": forms.NumberInput(
                attrs={"placeholder": "e.g. 50", "min": "0.0", "step": ".01"}
            ),
            "age_installed": forms.NumberInput(
                attrs={"placeholder": "e.g. 10", "min": "0.0", "step": "1"}
            ),
        }
        labels = {"input_timeseries": _("Timeseries vector")}
        help_texts = {
            "input_timeseries": _(
                "You can upload your timeseries as xls(x), csv or json format. Either there is one column with the values of the timeseries matching the scenario timesteps, or there are two columns, the first one being the timestamps and the second one the values of the timeseries. If you upload a spreadsheet with more than one tab only the first tab will be considered. The timeseries in csv format is expected to be in comma separated values with dot as decimal separator."
            )
        }


class StorageForm(AssetCreateForm):
    def __init__(self, *args, **kwargs):
        asset_type_name = kwargs.pop("asset_type", None)
        super().__init__(*args, asset_type="capacity", **kwargs)
        self.fields["dispatchable"].widget = forms.HiddenInput()
        self.initial["dispatchable"] = True

        if asset_type_name != "hess":
            self.fields["fixed_thermal_losses_relative"].widget = forms.HiddenInput()
            self.initial["fixed_thermal_losses_relative"] = 0
            self.fields["fixed_thermal_losses_absolute"].widget = forms.HiddenInput()
            self.initial["fixed_thermal_losses_absolute"] = 0
            self.fields["thermal_loss_rate"].widget = forms.HiddenInput()
            self.initial["thermal_loss_rate"] = 0
        else:
            field_name = "fixed_thermal_losses_relative"
            help_text = self.fields[field_name].help_text
            label = self.fields[field_name].label
            self.fields[field_name] = DualNumberField(
                default=0.1, min=0, max=1, param_name=field_name
            )
            self.fields[field_name].help_text = help_text
            self.fields[field_name].label = label

            field_name = "fixed_thermal_losses_absolute"
            help_text = self.fields[field_name].help_text
            label = self.fields[field_name].label
            self.fields[field_name] = DualNumberField(
                default=0.1, min=0, param_name=field_name
            )
            self.fields[field_name].help_text = help_text
            self.fields[field_name].label = label

    field_order = [
        "name",
        "capex_fix",
        "capex_var",
        "opex_fix",
        "opex_var",
        "lifetime",
        "maximum_capacity",
        "optimize_cap",
        "installed_capacity",
        "age_installed",
        "crate",
        "efficiency",
        "soc_max",
        "soc_min",
        "dispatchable",
    ]


class UploadTimeseriesForm(OpenPlanModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["values"] = DualNumberField(default=0, param_name="values")

    class Meta:
        model = Timeseries
        exclude = ["id", "user"]
        widgets = {
            "start_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "TestDateClass",
                    "placeholder": "Select a start date",
                    "type": "date",
                },
            )
        }


class CreatePVProductionTimeseriesForm(OpenPlanForm):
    mounting_type_choices = (
        ("fix_tilt", _("Fix Tilt")),
        ("fix_tilt_two_dir", _("Fix Tilt Two Directions Back To Back")),
        ("tracker", _("Tracker")),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    # TODO: these parameters would not be manual inputs but come from weather data, I assume? check with Markus

    # direct_irradiation_horizontal =
    # diffuse_irradiation_horizontal =
    azimuth = forms.FloatField(
        label=_("Azimuth"),
        widget=forms.NumberInput(
            attrs={
                "placeholder": _("e.g. 180"),
                "data-bs-toggle": "tooltip",
                "title": _(
                    "For fix tilt: Azimuth angle of the module orientation in degrees (North is 0°, East is 90°...); For tracker: Azimuth angle of the rotation-axis for tracking systems"
                ),
            }
        ),
    )

    tilt = forms.FloatField(
        label=_("Tilt"),
        widget=forms.NumberInput(
            attrs={
                "placeholder": _("e.g. 180"),
                "data-bs-toggle": "tooltip",
                "title": _("Tilt angle in degrees (0° is horizontal, 90° is vertical)"),
            }
        ),
    )

    system_efficiency = forms.FloatField(
        label=_("System Efficiency"),
        widget=forms.NumberInput(
            attrs={
                "placeholder": _("e.g. 0.8"),
                "data-bs-toggle": "tooltip",
                "title": _(
                    "Performance ratio of the total PV-System (usually around 0.8)"
                ),
            }
        ),
    )

    gcr = forms.FloatField(
        label=_("Ground Coverage Ratio"),
        widget=forms.NumberInput(
            attrs={
                "data-bs-toggle": "tooltip",
                "title": _(
                    "Ground Coverage Ratio (Ratio of the module area to the ground area of the module field), only needed for tracker"
                ),
            }
        ),
        required=False,
    )

    mounting_type = forms.ChoiceField(
        choices=mounting_type_choices,
        label=_("Mounting Type"),
        widget=forms.Select(
            attrs={
                "data-bs-toggle": "tooltip",
                "title": _(
                    "Static systems, east-west like system or 1-axis tracking system"
                ),
            }
        ),
    )
    albedo = forms.FloatField(
        label=_("Albedo"),
        widget=forms.NumberInput(
            attrs={
                "data-bs-toggle": "tooltip",
                "title": _("Reflection fraction of sunlight in the surrounding area"),
            }
        ),
    )

    # TODO: Add validation that checks e.g. that this field is only filled in if tracker is selected
    max_angle = forms.FloatField(
        label=_("Max. tilt angle"),
        widget=forms.NumberInput(
            attrs={
                "data-bs-toggle": "tooltip",
                "title": _(
                    "Maximum tilt angle for tracking systems. This value is only used for 'tracker' systems"
                ),
            }
        ),
        required=False,
    )


class CreateHeatDemandForm(OpenPlanForm):
    profile_type_choices = (
        ("EFH", _("Single-family house")),
        ("MFH", _("Apartment building")),
        ("GHD", _("Commerce/services general")),
        ("GMF", _("Household-like business enterprises")),
        ("GGA", _("Restaurants")),
        ("GBH", _("Retail and wholesale")),
        ("GMK", _("Metal and automotive")),
        ("GBH", _("Accommodation")),
        ("GKO", _("Local authorities, credit institutions and insurance companies")),
        ("GBD", _("Other operational services")),
        ("GWA", _("Laundries, dry cleaning")),
        ("GGB", _("Horticulture")),
        ("GBA", _("Bakery")),
        ("GPD", _("Paper and printing")),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    outdoor_temperature = DualNumberField(
        label=_("Outdoor Temperature"),
        help_text=_("Constant Temperature or Timeseries"),
        param_name="outdoor_temperature",
    )

    profile_type = forms.ChoiceField(
        choices=profile_type_choices,
        label=_("Profile Type"),
        help_text=_("Select from one of the available BDEW heat profiles"),
        widget=forms.Select(),
    )

    annual_heat_demand = forms.FloatField(
        label=_("Annual Heat Demand"),
        help_text=_("Total heat demand in the chosen timeperiod"),
        widget=forms.NumberInput(
            attrs={
                "placeholder": _("e.g. 1000"),
            }
        ),
    )

    building_year = forms.FloatField(
        label=_("Building Year"),
        help_text=_("Only for residential buildings, used for estimating insulation"),
        widget=forms.NumberInput(
            attrs={
                "placeholder": _("e.g. 1970"),
            }
        ),
        required=False,
    )

    wind_class = forms.ChoiceField(
        label=_("Wind class"),
        choices=(("Windy", _("Windy")), ("Not windy", _("Not Windy"))),
        help_text=_(
            "Windy for exposed buildings on free fields, near coast or high ground. Not windy for unexposed buildings in villages/cities"
        ),
        widget=forms.Select(),
    )

    def clean_building_year(self):
        building_year = self.cleaned_data["building_year"]
        profile_type = self.cleaned_data["profile_type"]
        if (
            profile_type
            in [
                "EFH",
                "MFH",
            ]
            and not building_year
        ):
            raise ValidationError(
                _("Building year is required for residential buildings")
            )
        return building_year


CUSTOM_TIMESERIES_FORMS = {
    # TODO: re-enable PV timeseries creation when weather data handling is settled
    # "pv_plant": CreatePVProductionTimeseriesForm,
    "heat_demand": CreateHeatDemandForm,
}
