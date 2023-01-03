from django import forms
from django.utils.translation import ugettext_lazy as _
from projects.forms import OpenPlanModelForm, ProjectCreateForm
from .models import Project

CURVES = (("Evening Peak", "Evening Peak"),
          ("Midday Peak", "Midday Peak"))

TIERS = (("Tier 1", "Tier 1"),
         ("Tier 2", "Tier 2"),
         ("Tier 3", "Tier 3"))


class ProjectForm(OpenPlanModelForm):
    class Meta:
        model = Project
        fields = "__all__"


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
