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
from projects.forms import *

from dashboard.helpers import KPI_PARAMETERS_ASSETS, KPIFinder
from projects.helpers import parameters_helper, PARAMETERS

CURVES = (("Evening Peak", "Evening Peak"),
          ("Midday Peak", "Midday Peak"))

TIERS = (("Tier 1", "Tier 1"),
         ("Tier 2", "Tier 2"),
         ("Tier 3", "Tier 3"))

class CPNLocationForm(ProjectCreateForm):
    weather = forms.FileField(
        label=_("Upload weather data"),
        required=False
    )


class CPNLoadProfileForm(ProjectCreateForm):
    households = forms.IntegerField(
        label=_("Number of households"),
    )
    tier = forms.ChoiceField(
        label=_("Demand Tier"),
        choices=TIERS,
        widget=forms.Select(
            attrs={
                "data-bs-toggle": "tooltip",
                "title": _("Electricity demand tier"),
            }
        ),
    )
    curve = forms.ChoiceField(
        label=_("Load curve"),
        choices=CURVES,
        widget=forms.Select(
            attrs={
                "data-bs-toggle": "tooltip",
                "title": _("Load curve"),
            }
        ),
    )
