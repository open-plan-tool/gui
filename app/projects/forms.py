import pickle
import os
import json
import io
import csv
from openpyxl import load_workbook

from crispy_forms.bootstrap import AppendedText, PrependedText, FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import (
    Submit,
    Layout,
    Row,
    Column,
    Field,
    Fieldset,
    ButtonHolder,
)
from django import forms
from django.forms import ModelForm
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils.translation import ugettext_lazy as _
from django.conf import settings as django_settings
from projects.models import *
from projects.constants import MAP_EPA_MVS, RENEWABLE_ASSETS

from dashboard.helpers import KPI_PARAMETERS_ASSETS, KPIFinder
from projects.helpers import (
    parameters_helper,
    PARAMETERS,
    DualNumberField,
    parse_input_timeseries,
)


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


def set_parameter_info(param_name, field, parameters=PARAMETERS):
    # For the storage unit
    if param_name.split("_")[0] in ("cp", "dchp", "chp"):
        param_name = "_".join(param_name.split("_")[1:])
    param_name = MAP_EPA_MVS.get(param_name, param_name)
    help_text = None
    unit = None
    verbose = None
    default_value = None
    if param_name in PARAMETERS:
        help_text = PARAMETERS[param_name][":Definition_Short:"]
        unit = PARAMETERS[param_name][":Unit:"]
        verbose = PARAMETERS[param_name]["verbose"]
        default_value = PARAMETERS[param_name][":Default:"]
        if unit == "None":
            unit = None
        elif unit == "Factor":
            unit = ""
        if verbose == "None":
            verbose = None
        if default_value == "None":
            default_value = None

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
        super(OpenPlanModelForm, self).__init__(*args, **kwargs)
        for fieldname, field in self.fields.items():
            set_parameter_info(fieldname, field)


class OpenPlanForm(forms.Form):
    """Class to automatize the assignation and translation of the labels, help_text and units"""

    def __init__(self, *args, **kwargs):
        super(OpenPlanForm, self).__init__(*args, **kwargs)
        for fieldname, field in self.fields.items():
            set_parameter_info(fieldname, field)


class FeedbackForm(ModelForm):
    class Meta:
        model = Feedback
        exclude = ["id", "rating"]


class ProjectDetailForm(ModelForm):
    class Meta:
        model = Project
        exclude = ["date_created", "date_updated", "economic_data", "user", "viewers"]

    def __init__(self, *args, **kwargs):
        super(ProjectDetailForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.disabled = True


class EconomicDataDetailForm(OpenPlanModelForm):
    class Meta:
        model = EconomicData
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super(EconomicDataDetailForm, self).__init__(*args, **kwargs)
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
    "tax": forms.NumberInput(
        attrs={"placeholder": "eg. 0.3", "min": "0.0", "max": "1.0", "step": "0.0001"}
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
        widget=forms.TextInput(
            attrs={
                "placeholder": "Name...",
                "data-bs-toggle": "tooltip",
                "title": _("A self explanatory name for the project."),
            }
        ),
    )
    description = forms.CharField(
        label=_("Project Description"),
        widget=forms.Textarea(
            attrs={
                "placeholder": "More detailed description here...",
                "data-bs-toggle": "tooltip",
                "title": _(
                    "A description of what this project objectives or test cases."
                ),
            }
        ),
    )
    country = forms.ChoiceField(
        label=_("Country"),
        choices=COUNTRY,
        widget=forms.Select(
            attrs={
                "data-bs-toggle": "tooltip",
                "title": _("Name of the country where the project is being deployed"),
            }
        ),
    )
    longitude = forms.FloatField(
        label=_("Location, longitude"),
        widget=forms.NumberInput(
            attrs={
                "placeholder": "click on the map",
                "readonly": "",
                "data-bs-toggle": "tooltip",
                "title": _(
                    "Longitude coordinate of the project's geographical location."
                ),
            }
        ),
    )
    latitude = forms.FloatField(
        label=_("Location, latitude"),
        widget=forms.NumberInput(
            attrs={
                "placeholder": "click on the map",
                "readonly": "",
                "data-bs-toggle": "tooltip",
                "title": _(
                    "Latitude coordinate of the project's geographical location."
                ),
            }
        ),
    )
    duration = forms.IntegerField(
        label=_("Project Duration"),
        widget=forms.NumberInput(
            attrs={
                "placeholder": "eg. 1",
                "min": "0",
                "max": "100",
                "step": "1",
                "data-bs-toggle": "tooltip",
                "title": _(
                    "The number of years the project is intended to be operational. The project duration also sets the installation time of the assets used in the simulation. After the project ends these assets are 'sold' and the refund is charged against the initial investment costs."
                ),
            }
        ),
    )
    currency = forms.ChoiceField(
        label=_("Currency"),
        choices=CURRENCY,
        widget=forms.Select(
            attrs={
                "data-bs-toggle": "tooltip",
                "title": _(
                    "The currency of the country where the project is implemented."
                ),
            }
        ),
    )
    discount = forms.FloatField(
        label=_("Discount Factor"),
        widget=forms.NumberInput(
            attrs={
                "placeholder": "eg. 0.1",
                "min": "0.0",
                "max": "1.0",
                "step": "0.0001",
                "data-bs-toggle": "tooltip",
                "title": _(
                    "Discount factor is the factor which accounts for the depreciation in the value of money in the future, compared to the current value of the same money. The common method is to calculate the weighted average cost of capital (WACC) and use it as the discount rate."
                ),
            }
        ),
    )
    tax = forms.FloatField(
        label=_("Tax"),
        widget=forms.NumberInput(
            attrs={
                "placeholder": "eg. 0.3",
                "min": "0.0",
                "max": "1.0",
                "step": "0.0001",
                "data-bs-toggle": "tooltip",
                "title": _("Tax factor"),
            }
        ),
    )

    # Render form
    def __init__(self, *args, **kwargs):
        super(ProjectCreateForm, self).__init__(*args, **kwargs)
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
            self.fields["usecase"].choices = [(uc.id, uc.name) for uc in usecase_qs]
            self.fields["usecase"].label = (
                _("Select a use case (or")
                + f"<a href='{usecase_url}'>"
                + _(" visit use cases page link")
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
            "title": _("Length of the time-steps."),
        },
        choices=((60, "60 min"),),
    ),
    "evaluated_period": forms.NumberInput(
        attrs={
            "placeholder": "eg. 10 days",
            "min": "1",
            "step": "1",
            "data-bs-toggle": "tooltip",
            "title": _("The number of days simulated with the energy system model."),
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
    "evaluated_period": _("Evaluated Period"),
    "time_step": _("Time Step"),
    "start_date": _("Start Date"),
    "capex_fix": _("Development costs"),
}

scenario_field_order = [
    "project",
    "name",
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
            self.fields["project"].queryset = project_queryset
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
            self.fields["project"].queryset = project_queryset
        else:
            self.fields["project"] = forms.ChoiceField(label="Project", choices=())

        for visible in self.visible_fields():
            visible.field.widget.attrs["class"] = "form-control"
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_tag = False  # don't include <form> tag


# endregion Scenario


class MinRenewableConstraintForm(OpenPlanModelForm):
    class Meta:
        model = MinRenewableConstraint
        exclude = ["scenario"]


class MaxEmissionConstraintForm(OpenPlanModelForm):
    class Meta:
        model = MaxEmissionConstraint
        exclude = ["scenario"]


class MinDOAConstraintForm(OpenPlanModelForm):
    class Meta:
        model = MinDOAConstraint
        exclude = ["scenario"]


class NZEConstraintForm(OpenPlanModelForm):
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


class AssetCreateForm(OpenPlanModelForm):
    def __init__(self, *args, **kwargs):
        asset_type_name = kwargs.pop("asset_type", None)
        view_only = kwargs.pop("view_only", False)
        self.existing_asset = kwargs.get("instance", None)

        super().__init__(*args, **kwargs)
        # which fields exists in the form are decided upon AssetType saved in the db
        asset_type = AssetType.objects.get(asset_type=asset_type_name)

        [
            self.fields.pop(field)
            for field in list(self.fields)
            if field not in asset_type.visible_fields
        ]

        if asset_type_name == "heat_pump":
            self.fields["efficiency"] = DualNumberField(
                default=1, min=1, param_name="efficiency"
            )
            self.fields["efficiency"].label = "COP1"

        """ DrawFlow specific configuration, add a special attribute to 
            every field in order for the framework to be able to export
            the data to json.
            !! This addition doesn't affect the previous behavior !!
        """
        for field in self.fields:
            if field == "renewable_asset" and asset_type_name in RENEWABLE_ASSETS:
                self.fields[field].initial = True
            self.fields[field].widget.attrs.update({f"df-{field}": ""})
            if field == "input_timeseries":
                self.fields[field].required = self.is_input_timeseries_empty()
            if view_only is True:
                self.fields[field].disabled = True
        """ ----------------------------------------------------- """

    def is_input_timeseries_empty(self):
        if self.existing_asset is not None:
            return self.existing_asset.is_input_timeseries_empty()
        else:
            return True

    def clean_input_timeseries(self):
        """Override built-in Form method which is called upon form validation"""
        try:
            input_timeseries_values = []
            timeseries_file = self.files.get("input_timeseries", None)
            # read the timeseries from file if any
            if timeseries_file is not None:
                input_timeseries_values = parse_input_timeseries(timeseries_file)
                # TODO here list the possible options
            else:
                # set the previous timeseries from the asset if any
                if self.is_input_timeseries_empty() is False:
                    input_timeseries_values = (
                        self.existing_asset.input_timeseries_values
                    )
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
            raise ValidationError(_("Could not parse a file. Did you upload one?"))

    class Meta:
        model = Asset
        exclude = ["scenario"]
        widgets = {
            "optimize_cap": forms.Select(
                choices=BOOL_CHOICES,
                attrs={
                    "data-bs-toggle": "tooltip",
                    "title": _(
                        "True if the user wants to perform capacity optimization for various components as part of the simulation."
                    ),
                    "style": "font-weight:400; font-size:13px;",
                },
            ),
            "dispatchable": forms.Select(choices=TRUE_FALSE_CHOICES),
            "renewable_asset": forms.Select(
                choices=TRUE_FALSE_CHOICES,
                attrs={
                    "data-bs-toggle": "tooltip",
                    "title": _("Indicate if the asset is renewable or not."),
                    "style": "font-weight:400; font-size:13px;",
                },
            ),
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Asset Name",
                    "style": "font-weight:400; font-size:13px;",
                }
            ),
            "capex_fix": forms.NumberInput(
                attrs={
                    "placeholder": "e.g. 10000",
                    "min": "0.0",
                    "step": ".01",
                    "data-bs-toggle": "tooltip",
                    "title": _(
                        " A fixed cost to implement the asset, eg. planning costs which do not depend on the (optimized) asset capacity."
                    ),
                    "style": "font-weight:400; font-size:13px;",
                }
            ),
            "capex_var": forms.NumberInput(
                attrs={
                    "placeholder": "e.g. 4000",
                    "min": "0.0",
                    "step": ".01",
                    "data-bs-toggle": "tooltip",
                    "title": _(
                        " Actual CAPEX of the asset, i.e., specific investment costs."
                    ),
                    "style": "font-weight:400; font-size:13px;",
                }
            ),
            "opex_fix": forms.NumberInput(
                attrs={
                    "placeholder": "e.g. 0",
                    "min": "0.0",
                    "step": ".01",
                    "data-bs-toggle": "tooltip",
                    "title": _(
                        "Actual OPEX of the asset, i.e., specific operational and maintenance costs."
                    ),
                    "style": "font-weight:400; font-size:13px;",
                }
            ),
            "opex_var": forms.NumberInput(
                attrs={
                    "placeholder": "Currency",
                    "min": "0.0",
                    "step": ".01",
                    "data-bs-toggle": "tooltip",
                    "title": _(
                        "Variable cost associated with a flow through/from the asset."
                    ),
                    "style": "font-weight:400; font-size:13px;",
                }
            ),
            "lifetime": forms.NumberInput(
                attrs={
                    "placeholder": "e.g. 10 years",
                    "min": "0",
                    "step": "1",
                    "data-bs-toggle": "tooltip",
                    "title": _(
                        "Number of operational years of the asset until it has to be replaced."
                    ),
                    "style": "font-weight:400; font-size:13px;",
                }
            ),
            # TODO: Try changing this to FileInput
            "input_timeseries": forms.FileInput(
                attrs={
                    "onchange": "plot_file_trace(obj=this.files, plot_id='timeseries_trace')"
                }
            ),
            # 'input_timeseries': forms.Textarea(attrs={'placeholder': 'e.g. [4,3,2,5,3,...]',
            #                                           'style': 'font-weight:400; font-size:13px;'}),
            "crate": forms.NumberInput(
                attrs={
                    "placeholder": "factor of total capacity (kWh), e.g. 0.7",
                    "min": "0.0",
                    "max": "1.0",
                    "step": ".0001",
                    "data-bs-toggle": "tooltip",
                    "title": _(
                        "C-rate is the rate at which the storage can charge or discharge relative to the nominal capacity of the storage. A c-rate of 1 implies that the battery can discharge or charge completely in a single timestep."
                    ),
                    "style": "font-weight:400; font-size:13px;",
                }
            ),
            "efficiency": forms.NumberInput(
                attrs={
                    "placeholder": "e.g. 0.99",
                    "data-bs-toggle": "tooltip",
                    "title": _("Ratio of energy output/energy input."),
                    "style": "font-weight:400; font-size:13px;",
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
                    "data-bs-toggle": "tooltip",
                    "title": _(
                        "The maximum permissible level of charge in the battery (generally, it is when the battery is filled to its nominal capacity), represented by the value 1.0. Users can  also specify a certain value as a factor of the actual capacity."
                    ),
                    "style": "font-weight:400; font-size:13px;",
                }
            ),
            "soc_min": forms.NumberInput(
                attrs={
                    "placeholder": "e.g. 0.1",
                    "min": "0.0",
                    "max": "1.0",
                    "step": ".01",
                    "data-bs-toggle": "tooltip",
                    "title": _(
                        "The minimum permissible level of charge in the battery as a factor of the nominal capacity of the battery."
                    ),
                    "style": "font-weight:400; font-size:13px;",
                }
            ),
            "maximum_capacity": forms.NumberInput(
                attrs={
                    "placeholder": "e.g. 1000",
                    "min": "0.0",
                    "step": ".01",
                    "data-bs-toggle": "tooltip",
                    "title": _("The maximum installable capacity."),
                    "style": "font-weight:400; font-size:13px;",
                }
            ),
            "energy_price": forms.NumberInput(
                attrs={
                    "placeholder": "e.g. 0.1",
                    "min": "0.0",
                    "step": ".0001",
                    "data-bs-toggle": "tooltip",
                    "title": _("Price of electricity sourced from the utility grid."),
                    "style": "font-weight:400; font-size:13px;",
                }
            ),
            "feedin_tariff": forms.NumberInput(
                attrs={
                    "placeholder": "e.g. 0.0",
                    "min": "0.0",
                    "step": ".0001",
                    "data-bs-toggle": "tooltip",
                    "title": _("Price received for feeding electricity into the grid."),
                    "style": "font-weight:400; font-size:13px;",
                }
            ),
            "feedin_cap": forms.NumberInput(
                attrs={
                    "placeholder": "e.g. 0.0",
                    "min": "0.0",
                    "data-bs-toggle": "tooltip",
                    "title": _("Capping the feedin capacity of a DSO."),
                    "style": "font-weight:400; font-size:13px;",
                }
            ),
            "peak_demand_pricing": forms.NumberInput(
                attrs={
                    "placeholder": "e.g. 60",
                    "min": "0.0",
                    "step": ".01",
                    "data-bs-toggle": "tooltip",
                    "title": _(
                        "Price to be paid additionally for energy-consumption based on the peak demand of a period."
                    ),
                    "style": "font-weight:400; font-size:13px;",
                }
            ),
            "peak_demand_pricing_period": forms.NumberInput(
                attrs={
                    "placeholder": "times per year, e.g. 2",
                    "data-bs-toggle": "tooltip",
                    "title": _(
                        "Number of reference periods in one year for the peak demand pricing. Only one of the following are acceptable values: 1 (yearly), 2, 3 ,4, 6, 12 (monthly)."
                    ),
                    "style": "font-weight:400; font-size:13px;",
                    "min": "1",
                    "max": "12",
                    "step": "1",
                }
            ),
            "renewable_share": forms.NumberInput(
                attrs={
                    "placeholder": "e.g. 0.1",
                    "min": "0.0",
                    "max": "1.0",
                    "step": ".0001",
                    "data-bs-toggle": "tooltip",
                    "title": "The share of renewables in the generation mix of the energy supplied by the DSO (utility).",
                    "style": "font-weight:400; font-size:13px;",
                }
            ),
            "installed_capacity": forms.NumberInput(
                attrs={
                    "placeholder": "e.g. 50",
                    "min": "0.0",
                    "step": ".01",
                    "data-bs-toggle": "tooltip",
                    "title": _(
                        "The already existing installed capacity in-place, which will also be replaced after its lifetime."
                    ),
                    "style": "font-weight:400; font-size:13px;",
                }
            ),
            "age_installed": forms.NumberInput(
                attrs={
                    "placeholder": "e.g. 10",
                    "min": "0.0",
                    "step": "1",
                    "data-bs-toggle": "tooltip",
                    "title": _(
                        "The number of years the asset has already been in operation."
                    ),
                    "style": "font-weight:400; font-size:13px;",
                }
            ),
        }
        labels = {
            "name": _("Name"),
            "optimize_cap": _("Optimize cap"),
            "dispatchable": _("Dispatchable"),
            "renewable_asset": _("Renewable asset"),
            "capex_fix": _("Development costs"),
            "capex_var": _("Specific costs"),
            "opex_fix": _("Specific OM costs"),
            "opex_var": _("Dispatch price"),
            "lifetime": _("Asset Lifetime"),
            "input_timeseries": _("Timeseries vector"),
            "crate": _("Crate"),
            "efficiency": _("Efficiency"),
            "soc_max": _("SoC max"),
            "soc_min": _("SoC min"),
            "maximum_capacity": _("Maximum capacity"),
            "energy_price": _("Energy price"),
            "feedin_tariff": _("Feedin tariff"),
            "peak_demand_pricing": _("Peak demand pricing"),
            "peak_demand_pricing_period": _("Peak demand pricing period (times/year)"),
            "renewable_share": _("Renewable share"),
            "installed_capacity": _("installed capacity (kW)"),
            "age_installed": _("Age installed"),
        }
        help_texts = {
            "input_timeseries": _(
                "You can upload your timeseries as xls(x), csv or json format. Either there is one column with the values of the timeseries matching the scenario timesteps, or there are two columns, the first one being the timestamps and the second one the values of the timeseries. If you upload a spreadsheet with more than one tab only the first tab will be considered. The timeseries in csv format is expected to be in comma separated values with dot as decimal separator."
            )
        }


class StorageForm(AssetCreateForm):
    def __init__(self, *args, **kwargs):
        asset_type_name = kwargs.pop("asset_type", None)
        super(StorageForm, self).__init__(*args, asset_type="capacity", **kwargs)

        self.fields["crate"].widget = forms.HiddenInput()
        self.fields["crate"].initial = 1
        self.fields["dispatchable"].widget = forms.HiddenInput()
        self.fields["dispatchable"].initial = True
        self.fields["installed_capacity"].label = _("Installed capacity (kWh)")

    field_order = [
        "name",
        "capex_fix",
        "capex_var",
        "opex_fix",
        "opex_var",
        "installed_capacity",
        "optimize_cap",
        "lifetime",
        "age_installed",
        "crate",
        "efficiency",
        "soc_max",
        "soc_min",
        "dispatchable",
    ]
