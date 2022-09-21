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
from projects.forms import OpenPlanForm

from dashboard.helpers import KPI_PARAMETERS_ASSETS, KPIFinder
from projects.helpers import parameters_helper, PARAMETERS


class CPNCreateForm(OpenPlanForm):
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
    weather = forms.FileField(
        label=_("Upload weather data"),
        required=False
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

    # Render form
    def __init__(self, *args, **kwargs):
        super(CPNCreateForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = "project_form_id"
        # self.helper.form_class = 'blueForm'
        self.helper.form_method = "post"
        self.helper.add_input(Submit("submit", "Submit"))

        self.helper.form_class = "form-horizontal"
        self.helper.label_class = "col-lg-8"
        self.helper.field_class = "col-lg-10"
