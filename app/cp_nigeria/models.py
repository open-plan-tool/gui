from django.conf import settings
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from datetime import timedelta
from django.forms.models import model_to_dict
from django.utils.translation import gettext_lazy as _
from projects.models import Timeseries, Project, Scenario, Asset, Bus, UseCase
from projects.scenario_topology_helpers import assign_assets, assign_busses


class ConsumerType(models.Model):
    consumer_type = models.CharField(max_length=50)

    def __str__(self):
        return self.consumer_type


class DemandTimeseries(Timeseries):
    consumer_type = models.ForeignKey(ConsumerType, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.name


class ConsumerGroup(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, blank=True, null=True)
    consumer_type = models.ForeignKey(ConsumerType, on_delete=models.CASCADE, null=True)
    timeseries = models.ForeignKey(DemandTimeseries, on_delete=models.CASCADE, null=True)
    number_consumers = models.IntegerField()
    expected_consumer_increase = models.FloatField(blank=True, null=True)
    expected_demand_increase = models.FloatField(blank=True, null=True)


def copy_energy_system_from_usecase(usecase_name, scenario):
    """Given a scenario, copy the topology of the usecase"""
    # Filter the name of the project and the usecasename within this project
    usecase_scenario = Scenario.objects.get(project=UseCase.objects.get(name="cp_usecases"), name=usecase_name)
    dm = usecase_scenario.export()
    assets = dm.pop("assets")
    busses = dm.pop("busses")
    # delete pre-existing energy system
    qs_assets = Asset.objects.filter(scenario=scenario)
    qs_busses = Bus.objects.filter(scenario=scenario)
    if qs_busses.exists() or qs_assets.exists():
        qs_assets.delete()
        qs_busses.delete()
    # assign the assets and busses to the given scenario
    assign_assets(scenario, assets)
    assign_busses(scenario, busses)
