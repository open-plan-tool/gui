import json
from typing import List
from django.db.models import Q
import numpy as np
from numpy.core import long
from datetime import date, datetime, time

from projects.models import (
    ConnectionLink,
    Scenario,
    Project,
    EconomicData,
    Asset,
    Bus,
    Constraint,
    ValueType,
)


class ProjectDataDto:
    def __init__(
        self,
        project_id: str,
        project_name: str,
        scenario_id: str,
        scenario_name: str,
        country: str,
        latitude: float,
        longitude: float,
    ):
        self.project_id = project_id
        self.project_name = project_name
        self.scenario_id = scenario_id
        self.scenario_name = scenario_name
        self.country = country
        self.latitude = latitude
        self.longitude = longitude


class ValueTypeDto:
    def __init__(self, unit: str, value: float):
        self.unit = unit
        self.value = value


class EconomicDataDto:
    def __init__(
        self,
        currency: str,
        project_duration: ValueTypeDto,
        discount_factor: ValueTypeDto,
        tax: ValueTypeDto,
    ):
        self.currency = currency
        self.project_duration = project_duration
        # self.annuity_factor = annuity_factor
        self.discount_factor = discount_factor
        self.tax = tax
        # self.crf = crf


class SimulationSettingsDto:
    def __init__(self, start_date: str, time_step: int, evaluated_period: ValueTypeDto):
        self.start_date = start_date
        # self.end_date = end_date
        self.time_step = time_step
        self.evaluated_period = evaluated_period


class TimeseriesDataDto:
    def __init__(self, unit: str, value: List[List[float]]):
        self.unit = unit
        self.value = value


class AssetDto:
    def __init__(
        self,
        asset_type: str,
        label: str,
        unique_id: str,
        type_oemof: str,
        energy_vector: str,
        inflow_direction: str,
        outflow_direction: str,
        dispatchable: bool,
        age_installed: ValueTypeDto,
        c_rate: ValueTypeDto,
        soc_max: ValueTypeDto,
        soc_min: ValueTypeDto,
        development_costs: ValueTypeDto,
        dispatch_price: ValueTypeDto,
        efficiency: ValueTypeDto,
        installed_capacity: ValueTypeDto,
        lifetime: ValueTypeDto,
        maximum_capacity: ValueTypeDto,
        energy_price: ValueTypeDto,
        feedin_tariff: ValueTypeDto,
        feedin_cap: ValueTypeDto,
        optimize_capacity: ValueTypeDto,
        peak_demand_pricing: ValueTypeDto,
        peak_demand_pricing_period: ValueTypeDto,
        renewable_share: ValueTypeDto,
        renewable_asset: ValueTypeDto,
        specific_costs: ValueTypeDto,
        specific_costs_om: ValueTypeDto,
        input_timeseries: TimeseriesDataDto,
        unit: str,
    ):
        self.asset_type = asset_type
        self.label = label
        self.unique_id = unique_id
        self.type_oemof = type_oemof
        self.energy_vector = energy_vector
        self.inflow_direction = inflow_direction
        self.outflow_direction = outflow_direction
        self.dispatchable = dispatchable
        self.age_installed = age_installed
        self.c_rate = c_rate
        self.soc_max = soc_max
        self.soc_min = soc_min
        self.development_costs = development_costs
        self.dispatch_price = dispatch_price
        self.efficiency = efficiency
        self.installed_capacity = installed_capacity
        self.lifetime = lifetime
        self.maximum_capacity = maximum_capacity
        self.energy_price = energy_price
        self.feedin_tariff = feedin_tariff
        self.feedin_cap = feedin_cap
        self.optimize_capacity = optimize_capacity
        self.peak_demand_pricing = peak_demand_pricing
        self.peak_demand_pricing_period = peak_demand_pricing_period
        self.renewable_share = renewable_share
        self.renewable_asset = renewable_asset
        self.specific_costs = specific_costs
        self.specific_costs_om = specific_costs_om
        self.input_timeseries = input_timeseries
        self.unit = unit
        self.beta = beta


class EssDto:
    def __init__(
        self,
        asset_type: str,
        label: str,
        type_oemof: str,
        energy_vector: str,
        inflow_direction: str,
        outflow_direction: str,
        input_power: AssetDto,
        output_power: AssetDto,
        capacity: AssetDto,
    ):
        self.asset_type = asset_type
        self.label = label
        self.type_oemof = type_oemof
        self.energy_vector = energy_vector
        self.inflow_direction = inflow_direction
        self.outflow_direction = outflow_direction
        self.input_power = input_power
        self.output_power = output_power
        self.capacity = capacity


class BusDto:
    def __init__(self, label: str, energy_vector: str, assets: List[AssetDto]):
        self.label = label
        self.energy_vector = energy_vector
        self.assets = assets


class ConstraintDto:
    def __init__(self, label: str, value: ValueTypeDto):
        self.label = label
        self.value = value


def get_all_subclasses(python_class):
    """
    Credit: https://gist.github.com/pzrq/460424c9382dd50d02b8
    Helper function to get all the subclasses of a class.
    :param python_class: Any Python class that implements __subclasses__()
    """
    python_class.__subclasses__()

    subclasses = set()
    check_these = [python_class]

    while check_these:
        parent = check_these.pop()
        for child in parent.__subclasses__():
            if child not in subclasses:
                subclasses.add(child)
                check_these.append(child)

    return sorted(subclasses, key=lambda x: x.__name__)


def get_concrete_models(base_model):
    """
    Credit: https://gist.github.com/pzrq/460424c9382dd50d02b8
    Helper function to get all concrete models
    that are subclasses of base_model
    in sorted order by name.
    :param base_model: A Django models.Model instance.
    """
    found = get_all_subclasses(base_model)

    def filter_func(model):
        meta = getattr(model, "_meta", "")
        if getattr(meta, "abstract", True):
            # Skip meta classes
            return False
        if "_Deferred_" in model.__name__:
            # See deferred_class_factory() in django.db.models.query_utils
            # Catches when you do .only('attr') on a queryset
            return False
        return True

    subclasses = list(filter(filter_func, found))
    return sorted(subclasses, key=lambda x: x.__name__)


class MVSRequestDto:
    def __init__(
        self,
        project_data: ProjectDataDto,
        economic_data: EconomicDataDto,
        simulation_settings: SimulationSettingsDto,
        energy_providers: List[AssetDto],
        energy_consumption: List[AssetDto],
        energy_conversion: List[AssetDto],
        energy_production: List[AssetDto],
        energy_storage: List[EssDto],
        energy_busses: List[BusDto],
        constraints: List[ConstraintDto],
    ):
        self.project_data = project_data
        self.economic_data = economic_data
        self.simulation_settings = simulation_settings
        self.energy_providers = energy_providers
        self.energy_consumption = energy_consumption
        self.energy_conversion = energy_conversion
        self.energy_production = energy_production
        self.energy_storage = energy_storage
        self.energy_busses = energy_busses
        self.constraints = constraints


# Function to serialize scenario topology models to JSON
def convert_to_dto(scenario: Scenario):
    # Retrieve models
    project = Project.objects.get(scenario=scenario)
    economic_data = EconomicData.objects.get(project=project)
    ess_list = Asset.objects.filter(
        Q(scenario=scenario), Q(asset_type__asset_type__contains="ess")
    )
    # Exclude ESS related assets
    asset_list = Asset.objects.filter(Q(scenario=scenario)).exclude(
        Q(asset_type__asset_type__contains="ess")
        | Q(parent_asset__asset_type__asset_type__contains="ess")
    )
    bus_list = Bus.objects.filter(scenario=scenario).exclude(
        Q(connectionlink__asset__parent_asset__asset_type__asset_type__contains="ess")
    )

    constraint_list = [
        c.objects.get(scenario=scenario) for c in get_concrete_models(Constraint)
    ]
    constraint_list = [c for c in constraint_list if c.activated is True]

    # Create  dto objects
    project_data_dto = ProjectDataDto(
        project.id,
        project.name,
        scenario.id,
        scenario.name,
        project.country,
        project.latitude,
        project.longitude,
    )

    economic_data_dto = EconomicDataDto(
        economic_data.currency,
        to_value_type(economic_data, "duration"),
        # to_value_type(economic_data, 'annuity_factor'),
        to_value_type(economic_data, "discount"),
        to_value_type(economic_data, "tax"),
        # to_value_type(economic_data, 'crf'),
    )

    simulation_settings = SimulationSettingsDto(
        scenario.start_date.strftime(
            "%Y-%m-%d %H:%M"
        ),  # datetime.combine(scenario.start_date, time()).timestamp(),
        scenario.time_step,
        to_value_type(scenario, "evaluated_period"),
    )

    # map_to_dto(economic_data, economic_data_dto)

    # Initialize asset lists depending on asset category
    energy_providers = []
    energy_production = []
    energy_consumption = []
    energy_storage = []
    energy_conversion = []
    constraints = []

    bus_dto_list = []

    # Iterate over ess_assets
    for ess in ess_list:
        # Find all connections to ess
        input_connection = ConnectionLink.objects.filter(
            asset=ess, flow_direction="B2A"
        ).first()
        output_connection = ConnectionLink.objects.filter(
            asset=ess, flow_direction="A2B"
        ).first()

        inflow_direction = (
            input_connection.bus.name if input_connection is not None else None
        )
        outflow_direction = (
            output_connection.bus.name if output_connection is not None else None
        )

        ess_sub_assets = {}

        for asset in Asset.objects.filter(parent_asset=ess):
            asset_dto = AssetDto(
                asset.asset_type.asset_type,
                asset.name,
                asset.unique_id,
                None,
                None,
                None,
                None,
                asset.dispatchable,
                to_value_type(asset, "age_installed"),
                to_value_type(asset, "crate"),
                to_value_type(asset, "soc_max"),
                to_value_type(asset, "soc_min"),
                to_value_type(asset, "capex_fix"),
                to_value_type(asset, "opex_var"),
                to_value_type(asset, "efficiency"),
                to_value_type(asset, "installed_capacity"),
                to_value_type(asset, "lifetime"),
                to_value_type(asset, "maximum_capacity"),
                to_value_type(asset, "energy_price"),
                to_value_type(asset, "feedin_tariff"),
                to_value_type(asset, "feedin_cap"),
                to_value_type(asset, "optimize_cap"),
                to_value_type(asset, "peak_demand_pricing"),
                to_value_type(asset, "peak_demand_pricing_period"),
                to_value_type(asset, "renewable_share"),
                to_value_type(asset, "renewable_asset"),
                to_value_type(asset, "capex_var"),
                to_value_type(asset, "opex_fix"),
                to_timeseries_data(asset, "input_timeseries"),
                asset.asset_type.unit,
            )

            ess_sub_assets.update({asset.asset_type.asset_type: asset_dto})

        ess_dto = EssDto(
            ess.asset_type.asset_type,
            ess.name,
            ess.asset_type.mvs_type,
            ess.asset_type.energy_vector,
            inflow_direction,
            outflow_direction,
            ess_sub_assets["charging_power"],
            ess_sub_assets["discharging_power"],
            ess_sub_assets["capacity"],
        )

        energy_storage.append(ess_dto)

    # Iterate over assets
    for asset in asset_list:
        # Find all connections to asset
        input_connection = ConnectionLink.objects.filter(
            asset=asset, flow_direction="B2A"
        )
        output_connection = ConnectionLink.objects.filter(
            asset=asset, flow_direction="A2B"
        )

        inflow_direction = None
        num_inputs = input_connection.count()
        if num_inputs == 1:
            inflow_direction = input_connection.first().bus.name
        elif num_inputs > 1:
            inflow_direction = [
                n for n in input_connection.values_list("bus__name", flat=True)
            ]

        outflow_direction = None
        num_outputs = output_connection.count()
        if num_outputs == 1:
            outflow_direction = output_connection.first().bus.name
        elif num_outputs > 1:
            outflow_direction = [
                n for n in output_connection.values_list("bus__name", flat=True)
            ]

        asset_efficiency = to_value_type(asset, "efficiency")

        optional_parameters = {}
        if asset.asset_type.asset_type == "chp":

            optional_parameters["beta"] = to_value_type(asset, "thermal_loss_rate")
            efficiency_el_wo_heat_extraction = asset_efficiency.value
            efficiency_th_max_heat_extraction = to_value_type(
                asset, "efficiency_multiple"
            ).value

            output_mapping = [
                ev for ev in output_connection.values_list("bus__type", flat=True)
            ]

            efficiencies = []
            outflow_direction = []
            # TODO: make sure the length is equal to the number of timesteps
            for energy_vector in ["Electricity", "Heat"]:
                if energy_vector in output_mapping:
                    # TODO get the case where get fails --> projects.models.base_models.ConnectionLink.DoesNotExist: ConnectionLink matching query does not exist
                    outflow_direction.append(
                        output_connection.get(bus__type=energy_vector).bus.name
                    )

                    efficiency = (
                        efficiency_el_wo_heat_extraction
                        if energy_vector == "Electricity"
                        else efficiency_th_max_heat_extraction
                    )

                    efficiencies.append(efficiency)

            if len(efficiencies) != 2:
                print(
                    "ERROR, a chp should have 1 electrical input and one heat output, thus 2 efficiencies!"
                )
                import pdb

                pdb.set_trace()

            asset_efficiency.value = efficiencies

        if asset.asset_type.asset_type == "heat_pump":
            cop = asset_efficiency.value
            input_mapping = [
                ev for ev in input_connection.values_list("bus__type", flat=True)
            ]

            efficiencies = []
            inflow_direction = []
            # TODO: make sure the length is equal to the number of timesteps
            for energy_vector in ["Electricity", "Heat"]:
                if energy_vector in input_mapping:
                    # TODO get the case where get fails
                    inflow_direction.append(
                        input_connection.get(bus__type=energy_vector).bus.name
                    )
                    if isinstance(cop, list):
                        cop = np.array(cop)
                        efficiency = (
                            (1 / cop).tolist()
                            if energy_vector == "Electricity"
                            else (1 - 1 / cop).tolist()
                        )
                    else:
                        efficiency = (
                            (1 / cop)
                            if energy_vector == "Electricity"
                            else (1 - 1 / cop)
                        )

                    efficiencies.append(efficiency)

            if len(efficiencies) == 0:
                print("ERROR, a heat pump should at least have one electrical input!")
                import pdb

                pdb.set_trace()
            elif len(efficiencies) == 1:
                efficiencies = efficiencies[0]
                inflow_direction = inflow_direction[0]

            asset_efficiency.value = efficiencies

        asset_dto = AssetDto(
            asset.asset_type.asset_type,
            asset.name,
            asset.unique_id,
            asset.asset_type.mvs_type,
            asset.asset_type.energy_vector,
            inflow_direction,
            outflow_direction,
            asset.dispatchable,
            to_value_type(asset, "age_installed"),
            to_value_type(asset, "crate"),
            to_value_type(asset, "soc_max"),
            to_value_type(asset, "soc_min"),
            to_value_type(asset, "capex_fix"),
            to_value_type(asset, "opex_var"),
            asset_efficiency,
            to_value_type(asset, "installed_capacity"),
            to_value_type(asset, "lifetime"),
            to_value_type(asset, "maximum_capacity"),
            to_value_type(asset, "energy_price"),
            to_value_type(asset, "feedin_tariff"),
            to_value_type(asset, "feedin_cap"),
            to_value_type(asset, "optimize_cap"),
            to_value_type(asset, "peak_demand_pricing"),
            to_value_type(asset, "peak_demand_pricing_period"),
            to_value_type(asset, "renewable_share"),
            to_value_type(asset, "renewable_asset"),
            to_value_type(asset, "capex_var"),
            to_value_type(asset, "opex_fix"),
            to_timeseries_data(asset, "input_timeseries"),
            asset.asset_type.unit,
            **optional_parameters
        )

        # map_to_dto(asset, asset_dto)

        # Get category of asset and append to appropriate category
        if asset.asset_type.asset_category == "energy_provider":
            energy_providers.append(asset_dto)
        elif asset.asset_type.asset_category == "energy_production":
            energy_production.append(asset_dto)
        elif asset.asset_type.asset_category == "energy_consumption":
            energy_consumption.append(asset_dto)
        elif asset.asset_type.asset_category == "energy_conversion":
            energy_conversion.append(asset_dto)
        # elif asset.asset_type.asset_category == 'energy_storage':
        #     energy_storage.append(asset_dto)

    # Iterate over constraints
    for constraint in constraint_list:
        constraint_dto = ConstraintDto(
            label=constraint.name,
            value=ValueTypeDto(unit=constraint.unit, value=constraint.value),
        )
        constraints.append(constraint_dto)

    # Iterate over busses
    for bus in bus_list:
        # Find all connections with bus
        connections_list = ConnectionLink.objects.filter(bus=bus)

        # Find all assets associated with the connections
        bus_asset_list = list(
            set([connection.asset.name for connection in connections_list])
        )

        bus_dto = BusDto(bus.name, bus.type, bus_asset_list)

        bus_dto_list.append(bus_dto)

    mvs_request_dto = MVSRequestDto(
        project_data_dto,
        economic_data_dto,
        simulation_settings,
        energy_providers,
        energy_consumption,
        energy_conversion,
        energy_production,
        energy_storage,
        bus_dto_list,
        constraints,
    )

    return mvs_request_dto


# can be used to map assets fields with asset dtos
def map_to_dto(model_obj, dto_obj):
    # Iterate over model attributes
    for f in model_obj._meta.get_fields():
        # For dto attributes that are user defined
        if hasattr(dto_obj, f.name):
            if ValueType.objects.all().filter(type=f.name).exists():
                setattr(dto_obj, f.name, to_value_type(model_obj, f.name))
            # For all other attributes
            else:
                setattr(dto_obj, f.name, getattr(model_obj, f.name))


def to_value_type(model_obj, field_name):
    value_type = ValueType.objects.filter(type=field_name).first()
    unit = value_type.unit if value_type is not None else None
    value = getattr(model_obj, field_name)

    if value is not None:
        # make sure the value is not a str if the unit is "factor"
        if unit == "factor" and isinstance(value, str):
            value = json.loads(value)
        return ValueTypeDto(unit, value)
    else:
        return None


def to_timeseries_data(model_obj, field_name):
    value_type = ValueType.objects.filter(type=field_name).first()
    unit = value_type.unit if value_type is not None else None
    value_list = (
        json.loads(getattr(model_obj, field_name))
        if getattr(model_obj, field_name) is not None
        else None
    )
    if value_list is not None:
        return TimeseriesDataDto(unit, value_list)
    else:
        return None
