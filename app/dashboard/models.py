import copy
import json
import jsonschema
import traceback
import logging
import numpy as np
import plotly.graph_objects as go


from django.utils.translation import ugettext_lazy as _
from django.shortcuts import get_object_or_404
from django.db import models
from dashboard.helpers import (
    KPI_PARAMETERS,
    KPI_PARAMETERS_ASSETS,
    KPI_helper,
    GRAPH_TIMESERIES,
    GRAPH_TIMESERIES_STACKED,
    GRAPH_CAPACITIES,
    GRAPH_BAR,
    GRAPH_PIE,
    GRAPH_LOAD_DURATION,
    GRAPH_SANKEY,
    GRAPH_PARAMETERS_SCHEMAS,
    GRAPH_SENSITIVITY_ANALYSIS,
    REPORT_TYPES,
    single_timeseries_to_json,
    simulation_timeseries_to_json,
    report_item_render_to_json,
    sensitivity_analysis_graph_render_to_json,
    format_storage_subasset_name,
)

from projects.models import Bus, Simulation, SensitivityAnalysis, ConnectionLink, Asset
from projects.constants import (
    MAP_EPA_MVS,
    STORAGE_SUB_CATEGORIES,
    INPUT_POWER,
    OUTPUT_POWER,
)
from projects.models import Simulation, Scenario

logger = logging.getLogger(__name__)

KPI_COSTS_TOOLTIPS = {
    "Replacement_costs_during_project_lifetime": "Costs for replacement of assets which occur over the project lifetime.",
    "annuity_om": "Annuity of the operation, maintenance and dispatch costs of the energy system, ie. Ballpoint number of the annual expenses for system operation.",
    "annuity_total": "Annuity of the net present costs (NPC) of the energy system.",
    "costs_cost_om": "Costs for fix annual operation and maintenance costs over the whole project lifetime, that do not depend on the assets dispatch but solely on installed capacity.",
    "costs_dispatch": "Dispatch costs over the whole project lifetime including all expenditures that depend on the dispatch of assets, ie. fuel costs, electricity consumption from the external grid, costs for operation and maintainance that depend on the thoughput of an asset.",
    "costs_investment_over_lifetime": "Investment costs over the whole project lifetime, including all replacement costs.",
    "costs_om_total": "Costs for annual operation and maintenance costs as well as dispatch of all assets of the energy system, for the whole project duration.",
    "costs_total": "Net present costs of the system for the whole project duration, includes all operation, maintainance and dispatch costs as well as the investment costs (including replacements).",
    "costs_upfront_in_year_zero": "The costs which will have to be paid upfront when project begin, ie. In year 0.",
    "levelized_cost_of_energy_of_asset": "Cost per kWh thoughput though an asset, based on the assets costs during the project lifetime as well as the total thoughput though the asset in the project lifetime. For generation assets, equivalent to the levelized cost of generation.",
}

KPI_COSTS_UNITS = {
    "Replacement_costs_during_project_lifetime": "currency",
    "annuity_om": "currency/annum",
    "annuity_total": "currency/annum",
    "costs_cost_om": "currency",
    "costs_dispatch": "currency",
    "costs_investment_over_lifetime": "currency",
    "costs_om_total": "currency/annum",
    "costs_total": "currency",
    "costs_upfront_in_year_zero": "currency",
    "levelized_cost_of_energy_of_asset": "currency/kWh",
}

KPI_SCALAR_UNITS = {
    "Attributed costsElectricity": "currency",
    "Degree of autonomy": "fraction",
    "Levelized costs of electricity equivalent": "currency/kWh",
    "Levelized costs of electricity equivalentElectricity": "currency/kWh",
    "Onsite energy fraction": "fraction",
    "Onsite energy matching": "fraction",
    "Renewable factor": "fraction",
    "Renewable share of local generation": "fraction",
    "Replacement_costs_during_project_lifetime": "currency",
    "Specific emissions per electricity equivalent": "kg GHGeq/kWh",
    "Total emissions": "GHGeq/annum",
    "Total internal generation": "kWh/annum",
    "Total internal non-renewable generation": "kWh/annum",
    "Total internal renewable generation": "kWh/annum",
    "Total non-renewable energy use": "kWh/annum",
    "Total renewable energy use": "kWh/annum",
    "Total_demandElectricity": "kWh/annum",
    "Total_demandElectricity_electricity_equivalent": "kWh/annum",
    "Total_demand_electricity_equivalent": "kWh/annum",
    "Total_excessElectricity": "kWh/annum",
    "Total_excessElectricity_electricity_equivalent": "kWh/annum",
    "Total_excess_electricity_equivalent": "kWh/annum",
    "Total_feedinElectricity": "kWh/annum",
    "Total_feedinElectricity_electricity_equivalent": "kWh/annum",
    "Total_feedin_electricity_equivalent": "kWh/annum",
    "annuity_om": "currency/annum",
    "annuity_total": "currency/annum",
    "costs_cost_om": "currency",
    "costs_dispatch": "currency",
    "costs_investment_over_lifetime": "currency",
    "costs_om_total": "currency",
    "costs_total": "currency",
    "costs_upfront_in_year_zero": "currency",
}

KPI_SCALAR_TOOLTIPS = {
    "Attributed costsElectricity": "Costs attributed to supplying the electricity sectors demand, based on Net Present Costs of the energy system and the share of electricity compared to the overall system demand.",
    "Degree of autonomy": "A degree of autonomy close to zero shows high dependence on the DSO, while a degree of autonomy of 1 represents an autonomous or net-energy system and a degree of autonomy higher 1 a surplus-energy system",
    "Levelized costs of electricity equivalent": "Levelized cost of energy of the sector-coupled energy system, calculated from the systems annuity and the total system demand in electricity equivalent.",
    "Levelized costs of electricity equivalentElectricity": "Levelized cost of electricity, calculated from the levelized cost of energy and the share that the electricity demand has of the total energy demand of the system.",
    "Onsite energy fraction": "Onsite energy fraction is also referred to as self-consumption. It describes the fraction of all locally generated energy that is consumed by the system itself.",
    "Onsite energy matching": "The onsite energy matching is also referred to as self-sufficienct. It describes the fraction of the total demand that can be covered by the locally generated energy. Notice that the feed into the grid should only be positive. https://mvs-eland.readthedocs.io/en/latest/MVS_Outputs.html#onsite-energy-matching-oem",
    "Renewable factor": "Describes the share of the energy influx to the local energy system that is provided from renewable sources. This includes both local generation as well as consumption from energy providers.",
    "Renewable share of local generation": "The renewable share of local generation describes how much of the energy generated locally is produced from renewable sources. It does not take into account the consumption from energy providers.",
    "Replacement_costs_during_project_lifetime": "Costs for replacement of assets which occur over the project lifetime.",
    "Specific emissions per electricity equivalent": "Specific GHG emissions per supplied electricity equivalent",
    "Total emissions": "Total greenhouse gas emissions in kg.",
    "Total internal generation": "Aggregated amount of energy generated within the energy system",
    "Total internal non-renewable generation": "Aggregated amount of non-renewable energy generated within the energy system",
    "Total internal renewable generation": "Aggregated amount of renewable energy generated within the energy system",
    "Total non-renewable energy use": "Aggregated amount of non-renewable energy used within the energy system (ie. Including local generation and external supply).",
    "Total renewable energy use": "Aggregated amount of renewable energy used within the energy system (ie. Including local generation and external supply).",
    "Total_demandElectricity": "Demand of electricity in local energy system.",
    "Total_demandElectricity_electricity_equivalent": "Demand of electricity in local energy system, in electricity equivalent. This is equivalent to Electricity feed-in.",
    "Total_demand_electricity_equivalent": "System wide demand from all energy vectors, in electricity equivalent.",
    "Total_excessElectricity": "Excess of electricity / unused electricity in local energy system.",
    "Total_excessElectricity_electricity_equivalent": "Excess of electricity / unused electricity in local energy system, in electricity equivalent. This is equivalent to Excess electricity.",
    "Total_excess_electricity_equivalent": "System-wide excess of energy / unused energy, in electricity equivalent.",
    "Total_feedinElectricity": "Feed-in of electricity into external grid.",
    "Total_feedinElectricity_electricity_equivalent": "Feed-in of electricity into external grid, in electricity equivalent. This is equivalent to Electricity feed-in.",
    "Total_feedin_electricity_equivalent": "System wide feed-in into external grids from all energy vectors, in electricity equivalent.",
    "annuity_om": "Annuity of the operation, maintenance and dispatch costs of the energy system, ie. Ballpoint number of the annual expenses for system operation.",
    "annuity_total": "Annuity of the net present costs (NPC) of the energy system.",
    "costs_cost_om": "Costs for fix annual operation and maintenance costs over the whole project lifetime, that do not depend on the assets dispatch but solely on installed capacity.",
    "costs_dispatch": "Dispatch costs over the whole project lifetime including all expenditures that depend on the dispatch of assets, ie. fuel costs, electricity consumption from the external grid, costs for operation and maintainance that depend on the thoughput of an asset",
    "costs_investment_over_lifetime": "Investment costs over the whole project lifetime, including all replacement costs.",
    "costs_om_total": "Costs for annual operation and maintenance costs as well as dispatch of all assets of the energy system, for the whole project duration.",
    "costs_total": "Net present costs of the system for the whole project duration, includes all operation, maintainance and dispatch costs as well as the investment costs (including replacements).",
    "costs_upfront_in_year_zero": "The costs which will have to be paid upfront when project begin, ie. In year 0.",
}


class KPIScalarResults(models.Model):
    scalar_values = models.TextField()  # to store the scalars dict
    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE)


class KPICostsMatrixResults(models.Model):
    cost_values = models.TextField()  # to store the scalars dict
    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE)


class AssetsResults(models.Model):
    assets_list = models.TextField()  # to store the assets list
    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE)
    __asset_names = None
    __available_timeseries = None
    __asset_categories = None
    __busses_energy_vector = None

    @property
    def assets_dict(self):
        try:
            answer = json.loads(self.assets_list)
        except json.decoder.JSONDecodeError:
            answer = {}
        return answer

    @property
    def asset_names(self):
        if self.__asset_names is None:
            self.__asset_names = []
            asset_dict = self.assets_dict
            for category in asset_dict:
                for asset in asset_dict[category]:
                    self.__asset_names.append(asset["label"])
        return self.__asset_names

    @property
    def busses_energy_vector(self):
        if self.__busses_energy_vector is None:
            self.__busses_energy_vector = {
                b.name: b.type
                for b in Bus.objects.filter(scenario=self.simulation.scenario.id)
            }

        return self.__busses_energy_vector

    def energy_vector_busses(self, energy_vector=None):
        reverse_mapping = {}
        for k, v in self.busses_energy_vector.items():
            if v not in reverse_mapping:
                reverse_mapping[v] = k
            else:
                if isinstance(reverse_mapping[v], list) is False:
                    reverse_mapping[v] = [reverse_mapping[v]]
                reverse_mapping[v].append(k)
        if energy_vector is None:
            answer = reverse_mapping
        elif energy_vector in reverse_mapping:
            answer = reverse_mapping[energy_vector]
        else:
            raise KeyError(
                f"The energy vector {energy_vector} is not present in any of the busses of the system of scenario"
                f" '{self.simulation.scenario.name}' (scenario id: {self.simulation.scenario.id})"
            )

        return answer

    @property
    def available_timeseries(self):
        """Returns a dict which keys are asset labels and values are asset results only for timeseries asset

        An asset is deemed a timeseries when its results contain the key "flow"
        """
        if self.__available_timeseries is None:
            self.__available_timeseries = {}
            asset_dict = self.assets_dict
            for category in asset_dict:
                for asset in asset_dict[category]:
                    if category == "energy_storage":
                        for sub_cat in STORAGE_SUB_CATEGORIES:
                            storage_subasset = asset.get(sub_cat)
                            if storage_subasset is None:
                                storage_subasset = asset.get(
                                    MAP_EPA_MVS.get(sub_cat, sub_cat)
                                )
                            if storage_subasset is not None:
                                storage_subasset[
                                    "category"
                                ] = format_storage_subasset_name(category, sub_cat)
                                storage_subasset["type_oemof"] = asset["type_oemof"]
                                storage_subasset["energy_vector"] = asset[
                                    "energy_vector"
                                ]

                                self.__available_timeseries[
                                    format_storage_subasset_name(
                                        asset["label"], sub_cat
                                    )
                                ] = storage_subasset
                    else:
                        if (
                            "flow" in asset
                            and "_consumption_period" not in asset["label"]
                        ):
                            asset["category"] = category
                            qs = ConnectionLink.objects.filter(
                                asset__name=asset["label"],
                                scenario=self.simulation.scenario,
                                flow_direction="A2B",
                            ).values_list("bus__name", "bus__type")
                            if qs.exists():
                                asset["output_busses"] = {c[0]: c[1] for c in qs}
                            self.__available_timeseries[asset["label"]] = asset
        else:
            print("\n\nNOT reloading __available_timeseries\n\n")
        return self.__available_timeseries

    @property
    def asset_categories(self):
        if self.__asset_categories is None:
            self.__asset_categories = tuple(self.assets_dict.keys())
        return self.__asset_categories

    def single_asset_results(self, asset_name, asset_category=None):
        """Provided the name of an asset, return the results linked to this asset"""

        if self.__available_timeseries is None:
            asset_dict = self.assets_dict
            answer = None
            if asset_category is not None:
                categories = [asset_category]
            else:
                categories = self.asset_categories

            for category in categories:
                for asset in asset_dict[category]:
                    if category == "energy_storage":
                        for sub_cat in ("input_power", "output_power", "capacity"):
                            if asset_name == format_storage_subasset_name(
                                asset["label"], sub_cat
                            ):
                                storage_subasset = asset.get(sub_cat)
                                if storage_subasset is None:
                                    storage_subasset = asset.get(
                                        MAP_EPA_MVS.get(sub_cat, sub_cat)
                                    )
                                if storage_subasset is not None:
                                    if answer is None:
                                        answer = storage_subasset
                                        answer[
                                            "category"
                                        ] = format_storage_subasset_name(
                                            category, sub_cat
                                        )
                                        answer["energy_vector"] = asset["energy_vector"]
                                        break
                                    else:
                                        raise ValueError(
                                            f"Asset named {asset_name} appears twice in simulations results, this should not be possible"
                                        )
                    else:
                        if asset_name == asset["label"]:
                            if answer is None:
                                answer = asset
                                answer["category"] = category
                                break
                            else:
                                raise ValueError(
                                    f"Asset named {asset_name} appears twice in simulations results, this should not be possible"
                                )
        else:
            answer = self.__available_timeseries.get(asset_name)
        return answer

    def single_asset_type_oemof(self, asset_name, asset_category=None):
        """Provided the user name of the asset, return the type_oemof linked to this asset"""
        if self.__available_timeseries is None:
            asset_results = self.single_asset_results(asset_name, asset_category)

        else:
            asset_results = self.__available_timeseries.get(asset_name)

        if "type_oemof" in asset_results:
            answer = asset_results["type_oemof"]
        else:
            answer = None
        return answer

    def single_asset_timeseries(
        self, asset_name, asset_category=None, energy_vector=None
    ):
        """Provided the user name of the asset, return the timeseries linked to this asset"""

        asset_results = self.single_asset_results(asset_name, asset_category)

        answer = None

        if "flow" in asset_results:
            # find the energy vector of the bus in case of CHP which have multiple outputs
            flow_value = asset_results["flow"]["value"]
            if asset_results["type_oemof"] == "extractionTurbineCHP":
                if energy_vector is not None:
                    bus_name = self.energy_vector_busses(energy_vector)
                    if bus_name in flow_value:
                        flow_value = flow_value[bus_name]
                    else:
                        flow_value = None

            if flow_value is not None:
                answer = single_timeseries_to_json(
                    value=flow_value,
                    unit=asset_results["flow"]["unit"],
                    label=asset_name,
                    asset_type=asset_results["type_oemof"],
                    asset_category=asset_results["category"],
                )

        # if an energy_vector is provided return the timeseries only if the energy_vector type of the asset matches
        if energy_vector is not None:
            if (
                energy_vector not in asset_results.get("output_busses", {}).keys()
                and asset_results["energy_vector"] != energy_vector
            ):
                answer = None

        return answer


def parse_manytomany_object_list(object_list, model):
    """given one occurence or list of model instances or id of model instances returns a list of model instances"""
    if not isinstance(object_list, list):
        object_list = [object_list]

    if len(object_list) > 0:
        if isinstance(object_list[0], int):
            object_list = [s for s in model.objects.filter(id__in=object_list)]
    return object_list


def graph_timeseries(simulations, y_variables):
    simulations_results = []

    for sim in simulations:
        y_values = []
        assets_results_obj = AssetsResults.objects.get(simulation=sim)
        asset_timeseries = assets_results_obj.available_timeseries
        for y_var in y_variables:
            if y_var in asset_timeseries:
                single_ts_json = assets_results_obj.single_asset_timeseries(y_var)
                if single_ts_json["asset_type"] == "sink" or single_ts_json[
                    "asset_category"
                ] == format_storage_subasset_name("energy_storage", "input_power"):
                    single_ts_json["value"] = (
                        -np.array(single_ts_json["value"])
                    ).tolist()
                if single_ts_json["asset_type"] == "extractionTurbineCHP":
                    for bus in single_ts_json["value"]:
                        new_ts = single_ts_json.copy()
                        new_ts["value"] = single_ts_json["value"][bus]
                        new_ts["label"] = single_ts_json["label"] + "_" + bus
                        y_values.append(new_ts)

                else:
                    y_values.append(single_ts_json)
        simulations_results.append(
            simulation_timeseries_to_json(
                scenario_name=sim.scenario.name,
                scenario_id=sim.scenario.id,
                scenario_timeseries=y_values,
                scenario_timestamps=sim.scenario.get_timestamps(),
            )
        )
    return simulations_results


def graph_timeseries_stacked(simulations, y_variables, energy_vector):
    simulations_results = []

    for simulation in simulations:
        y_values = []
        assets_results_obj = AssetsResults.objects.get(simulation=simulation)
        asset_timeseries = assets_results_obj.available_timeseries
        for y_var in y_variables:
            if y_var in asset_timeseries:
                single_ts_json = assets_results_obj.single_asset_timeseries(
                    y_var, energy_vector=energy_vector
                )
                if single_ts_json is not None:
                    if single_ts_json["asset_type"] == "sink" or single_ts_json[
                        "asset_category"
                    ] == format_storage_subasset_name("energy_storage", "input_power"):
                        single_ts_json["fill"] = "none"
                    else:
                        single_ts_json["fill"] = "tonexty"
                    y_values.append(single_ts_json)
        simulations_results.append(
            simulation_timeseries_to_json(
                scenario_name=simulation.scenario.name,
                scenario_id=simulation.scenario.id,
                scenario_timeseries=y_values,
                scenario_timestamps=simulation.scenario.get_timestamps(),
            )
        )
    return simulations_results


def graph_capacities(simulations, y_variables):
    simulations_results = []
    multi_scenario = False
    if len(simulations) > 1:
        multi_scenario = True
    for simulation in simulations:
        y_values = (
            []
        )  # stores the capacity, both installed and optimized in seperate dicts, of each individual asset/ component
        x_values = []  # stores the label of the corresponding asset

        assets_results_obj = AssetsResults.objects.get(simulation=simulation)

        results_dict = json.loads(simulation.results)

        kpi_scalar_matrix = results_dict["kpi"]["scalar_matrix"]

        # TODO link unit to unit in asset["installed_capacity"]["unit"] or asset["optimized_add_cap"]["unit"]
        installed_capacity_dict = {
            "capacity": [],
            "name": _("Installed Capacity") + " (kW)"
            if multi_scenario is False
            else _("Inst. Cap.") + f"{simulation.scenario.name} (kW)",
        }
        optimized_capacity_dict = {
            "capacity": [],
            "name": _("Optimized Capacity") + " (kW)"
            if multi_scenario is False
            else _("Opt. Cap.") + f"{simulation.scenario.name} (kW)",
        }
        for y_var in y_variables:

            if "@" not in y_var:
                asset = assets_results_obj.single_asset_results(asset_name=y_var)
                x_values.append(y_var)
                if asset is not None:
                    installed_cap = asset["installed_capacity"]["value"]
                else:
                    installed_cap = 0
                installed_capacity_dict["capacity"].append(installed_cap)
                if y_var in kpi_scalar_matrix:
                    optimized_capacity_dict["capacity"].append(
                        kpi_scalar_matrix[y_var]["optimized_add_cap"]
                    )
                else:
                    optimized_cap = 0
                    if asset is not None:
                        if "optimized_add_cap" in asset:
                            optimized_cap = asset["optimized_add_cap"]["value"]
                    optimized_capacity_dict["capacity"].append(optimized_cap)
        y_values.append(installed_capacity_dict)
        y_values.append(optimized_capacity_dict)

        simulations_results.append(
            simulation_timeseries_to_json(
                scenario_name=simulation.scenario.name,
                scenario_id=simulation.scenario.id,
                scenario_timeseries=y_values,
                scenario_timestamps=x_values,
            )
        )
    return simulations_results


def graph_sankey(simulation, energy_vector):
    if isinstance(energy_vector, list) is False:
        energy_vector = [energy_vector]
    if energy_vector is not None:
        labels = []
        sources = []
        targets = []
        values = []
        colors = []

        sim = simulation
        ar = AssetsResults.objects.get(simulation=sim)
        results_ts = ar.available_timeseries
        qs = ConnectionLink.objects.filter(scenario__simulation=sim)

        chp_qs = Asset.objects.filter(
            scenario=sim.scenario, asset_type__asset_type__in=("chp", "chp_fixed_ratio")
        )
        if chp_qs.exists():
            chp_in_flow = {a.name: {"value": 0, "bus": ""} for a in chp_qs}
        else:
            chp_in_flow = {}

        for bus in Bus.objects.filter(scenario__simulation=sim, type__in=energy_vector):
            bus_label = bus.name
            labels.append(bus_label)
            colors.append("blue")
            # from asset to bus
            bus_inputs = qs.filter(flow_direction="A2B", bus=bus)
            asset_to_bus_names = []
            bus_to_asset_names = []

            for component in bus_inputs:
                # special case of providers which are bus input and output at the same time
                if component.asset.is_provider is True:
                    asset_to_bus_names.append(component.asset.name + "_consumption")
                    bus_to_asset_names.append(component.asset.name + "_feedin")
                elif component.asset.is_storage is True:
                    asset_to_bus_names.append(
                        format_storage_subasset_name(component.asset.name, OUTPUT_POWER)
                    )
                else:
                    asset_to_bus_names.append(component.asset.name)

            bus_outputs = qs.filter(flow_direction="B2A", bus=bus)
            for component in bus_outputs:
                if component.asset.is_storage is True:
                    bus_to_asset_names.append(
                        format_storage_subasset_name(component.asset.name, INPUT_POWER)
                    )
                else:

                    bus_to_asset_names.append(component.asset.name)

            for component_label in asset_to_bus_names:
                # draw link from the component to the bus
                if component_label not in labels:
                    labels.append(component_label)
                    colors.append("green")

                sources.append(labels.index(component_label))
                targets.append(labels.index(bus_label))

                flow_value = results_ts[component_label]["flow"]["value"]
                if bus_label in flow_value:
                    flow_value = flow_value[bus_label]

                val = np.sum(flow_value)
                if component_label in chp_in_flow:
                    chp_in_flow[component_label]["value"] += val

                if val == 0:
                    val = 1e-6

                values.append(val)

            for component_label in bus_to_asset_names:
                # draw link from the bus to the component
                if component_label not in labels:
                    labels.append(component_label)
                    colors.append("red")

                sources.append(labels.index(bus_label))
                targets.append(labels.index(component_label))

                val = np.sum(results_ts[component_label]["flow"]["value"])

                if component_label in chp_in_flow:
                    chp_in_flow[component_label]["bus"] = bus_label

                # If the asset has multiple inputs, multiply the output flow by the efficiency
                input_busses = results_ts[component_label].get("inflow_direction")
                if input_busses is not None:
                    if isinstance(input_busses, list):

                        bus_index = input_busses.index(bus_label)
                        efficiency = results_ts[component_label]["efficiency"]["value"][
                            bus_index
                        ]
                        if isinstance(efficiency, list):
                            flow = np.array(
                                results_ts[component_label]["flow"]["value"]
                            ) * np.array(efficiency)
                            val = np.sum(flow)
                        else:
                            val = (
                                val
                                * results_ts[component_label]["efficiency"]["value"][
                                    bus_index
                                ]
                            )

                if val == 0:
                    val = 1e-6
                values.append(val)

        for component_label in chp_in_flow:
            sources.append(labels.index(chp_in_flow[component_label]["bus"]))
            targets.append(labels.index(component_label))
            values.append(chp_in_flow[component_label]["value"])
        # TODO display the installed capacity, max capacity and optimized_add_capacity on the nodes if applicable
        fig = go.Figure(
            data=[
                go.Sankey(
                    node=dict(
                        pad=15,
                        thickness=20,
                        line=dict(color="black", width=0.5),
                        label=labels,
                        hovertemplate="Node has total value %{value}<extra></extra>",
                        color=colors,
                    ),
                    link=dict(
                        source=sources,  # indices correspond to labels
                        target=targets,
                        value=values,
                        hovertemplate="Link from node %{source.label}<br />"
                        + "to node%{target.label}<br />has value %{value}"
                        + "<br />and data <extra></extra>",
                    ),
                )
            ]
        )

        fig.update_layout(font_size=10)
        return fig.to_dict()


# These graphs are related to the graphs in static/js/report_items.js
REPORT_GRAPHS = {
    GRAPH_TIMESERIES: graph_timeseries,
    GRAPH_TIMESERIES_STACKED: graph_timeseries_stacked,
    GRAPH_CAPACITIES: graph_capacities,
    GRAPH_BAR: "Bar chart",
    GRAPH_PIE: "Pie chart",
    GRAPH_LOAD_DURATION: "Load duration curve",
    GRAPH_SANKEY: graph_sankey,
}

# # TODO change the form from this model to adapt the choices depending on single scenario/compare scenario or sensitivity
class ReportItem(models.Model):
    title = models.CharField(max_length=120, default="", blank=True)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    simulations = models.ManyToManyField(Simulation)
    parameters = models.TextField(
        default="", blank=True
    )  # to store the parameter lists
    initial_simulations = None

    def __init__(self, *args, **kwargs):
        if "simulations" in kwargs:
            self.initial_simulations = kwargs.pop("simulations")
            self.initial_simulations = parse_manytomany_object_list(
                self.initial_simulations
            )
        super().__init__(*args, **kwargs)

    #
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.initial_simulations is not None:
            self.simulations.add(*self.initial_simulations)

    def update_simulations(self, list_simulation):
        list_simulation = parse_manytomany_object_list(list_simulation, Simulation)
        if list_simulation:
            self.simulations.clear()
            self.simulations.add(*list_simulation)

    @property
    def parameters_dict(self):
        try:
            answer = json.loads(self.parameters)
        except json.decoder.JSONDecodeError:
            answer = {}
        return answer

    @property
    def project_id(self):
        return (
            self.simulations.all()
            .values_list("scenario__project", flat=True)
            .distinct()
            .get()
        )

    def proof_parameters_follow_schema(self, parameter_dict=None):
        if parameter_dict is None:
            parameter_dict = self.parameters_dict

        jschema = GRAPH_PARAMETERS_SCHEMAS[self.report_type]
        try:
            jsonschema.validate(parameter_dict, jschema)
            answer = True
        except jsonschema.exceptions.ValidationError:
            answer = False
            logger.warning(
                f"jsonschema validation error! Report item: {self.id} ({self.title}). Thrown Exception: {traceback.format_exc()}."
            )
        return answer

    def safely_assign_parameters(self, parameter_dict):
        if self.proof_parameters_follow_schema(parameter_dict) is True:
            self.parameters = json.dumps(parameter_dict)

    @property
    def render_json(self):
        return report_item_render_to_json(
            report_item_id=f"reportItem{self.project_id}-{self.id}",
            data=self.fetch_parameters_values(),
            title=self.title,
            report_item_type=self.report_type,
        )

    def fetch_parameters_values(self):
        parameters = json.loads(self.parameters)
        # TODO : adjust for other report types
        if self.report_type == GRAPH_TIMESERIES:
            y_variables = parameters.get("y", None)
            if y_variables is not None:
                return graph_timeseries(
                    simulations=self.simulations.all(), y_variables=y_variables
                )

        if self.report_type == GRAPH_TIMESERIES_STACKED:
            y_variables = parameters.get("y", None)
            if y_variables is not None:
                return graph_timeseries_stacked(
                    simulations=self.simulations.all(),
                    y_variables=y_variables,
                    energy_vector=parameters.get("energy_vector"),
                )

        if self.report_type == GRAPH_CAPACITIES:
            y_variables = parameters.get("y", None)

            if y_variables is not None:
                return graph_capacities(
                    simulations=self.simulations.all(), y_variables=y_variables
                )

        if self.report_type == GRAPH_SANKEY:
            energy_vector = parameters.get("energy_vector", None)

            return graph_sankey(
                simulation=self.simulations.get(), energy_vector=energy_vector
            )


def get_project_reportitems(project):
    """Given a project, return the ReportItem instances linked to that project"""
    qs = (
        project.scenario_set.filter(simulation__isnull=False)
        .filter(simulation__reportitem__isnull=False)
        .values_list("simulation__reportitem", flat=True)
        .distinct()
    )
    return ReportItem.objects.filter(id__in=[ri for ri in qs])


class SensitivityAnalysisGraph(models.Model):
    title = models.CharField(max_length=120, default="", blank=True)
    report_type = models.CharField(
        default=GRAPH_SENSITIVITY_ANALYSIS,
        max_length=len(GRAPH_SENSITIVITY_ANALYSIS),
        editable=False,
    )
    analysis = models.ForeignKey(SensitivityAnalysis, on_delete=models.CASCADE)
    y = models.CharField(
        max_length=50,
        choices=[
            (v, _(KPI_PARAMETERS_ASSETS[v]["verbose"])) for v in KPI_PARAMETERS_ASSETS
        ],
    )

    @property
    def variable_unit(self):
        return self.analysis.variable_unit.replace(
            "currency", self.analysis.scenario.get_currency()
        )

    @property
    def y_unit(self):
        unit = KPI_helper.get_doc_unit(self.y)
        return unit.replace("currency", self.analysis.scenario.get_currency())

    @property
    def render_json(self):
        return sensitivity_analysis_graph_render_to_json(
            sa_id=f"saItem{self.analysis.scenario.project.id}-{self.id}",
            data=[self.analysis.graph_data(self.y)],
            title=self.title,
            x_label=f"{self.analysis.variable_name_verbose} [{self.variable_unit}]",
            y_label=f"{KPI_helper.get_doc_verbose(self.y)} [{self.y_unit}]",
        )


def get_project_sensitivity_analysis(project):
    """Given a project, return the ReportItem instances linked to that project"""
    qs = (
        project.scenario_set.filter(simulation__isnull=False)
        .filter(sensitivityanalysis__isnull=False)
        .values_list("sensitivityanalysis", flat=True)
        .distinct()
    )
    return SensitivityAnalysis.objects.filter(id__in=[sa_id for sa_id in qs])


def get_project_sensitivity_analysis_graphs(project):
    """Given a project, return the ReportItem instances linked to that project"""
    qs = (
        project.scenario_set.filter(simulation__isnull=False)
        .filter(simulation__results__isnull=False)
        .filter(sensitivityanalysis__sensitivityanalysisgraph__isnull=False)
        .values_list("sensitivityanalysis__sensitivityanalysisgraph", flat=True)
        .distinct()
    )
    return SensitivityAnalysisGraph.objects.filter(id__in=[sa_id for sa_id in qs])
