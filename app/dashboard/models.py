import copy
import json
import jsonschema
import traceback
import logging
import numpy as np
import plotly.graph_objects as go
import pandas as pd


from django.utils.translation import gettext_lazy as _
from django.shortcuts import get_object_or_404
from django.db import models
from django.db.models import Value, Q, F, Case, When
from django.db.models.functions import Concat, Replace
from dashboard.helpers import (
    KPI_PARAMETERS,
    KPI_PARAMETERS_ASSETS,
    KPI_helper,
    GRAPH_TIMESERIES,
    GRAPH_TIMESERIES_STACKED,
    GRAPH_CAPACITIES,
    GRAPH_BAR,
    GRAPH_COSTS,
    GRAPH_PIE,
    GRAPH_LOAD_DURATION,
    GRAPH_SANKEY,
    GRAPH_PARAMETERS_SCHEMAS,
    GRAPH_SENSITIVITY_ANALYSIS,
    REPORT_TYPES,
    COSTS_PER_ASSETS_STACKED,
    COSTS_PER_CATEGORY_STACKED,
    COSTS_PER_ASSETS,
    COSTS_PER_CATEGORY,
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
    ASSET_TYPE,
    ENERGY_VECTOR,
    MVS_TYPE,
)
from projects.models import Simulation, Scenario

logger = logging.getLogger(__name__)

KPI_COSTS = [
    "replacement_costs_during_project_lifetime",
    "annuity_om",
    "annuity_total",
    "costs_cost_om",
    "costs_dispatch",
    "costs_investment_over_lifetime",
    "costs_om_total",
    "costs_total",
    "costs_upfront_in_year_zero",
    "levelized_cost_of_energy_of_asset",
]
KPI_COSTS_UNITS = {
    kpi: KPI_PARAMETERS[kpi]["unit"] for kpi in KPI_COSTS if kpi in KPI_PARAMETERS
}
KPI_COSTS_TOOLTIPS = {
    kpi: KPI_PARAMETERS[kpi]["definition"] for kpi in KPI_COSTS if kpi in KPI_PARAMETERS
}
KPI_SCALARS = [
    "attributed_costsElectricity",
    "degree_of_autonomy",
    "levelized_costs_of_electricity_equivalent",
    "levelized_costs_of_electricity_equivalentElectricity",
    "onsite_energy_fraction",
    "onsite_energy_matching",
    "renewable_factor",
    "renewable_share_of_local_generation",
    "replacement_costs_during_project_lifetime",
    "specific_emissions_per_electricity_equivalent",
    "total_emissions",
    "total_internal_generation",
    "total_internal_non-renewable_generation",
    "total_internal_renewable_generation",
    "total_non-renewable_energy_use",
    "total_renewable_energy_use",
    "total_demandElectricity",
    "total_demand_electricity_equivalent",
    "total_excessElectricity",
    "total_excess_electricity_equivalent",
    "total_feedinElectricity",
    "total_feedin_electricity_equivalent",
    "levelized_costs_of_electricity_equivalentElectricity",
]

KPI_SCALAR_UNITS = {
    kpi: KPI_PARAMETERS[kpi]["unit"] for kpi in KPI_SCALARS if kpi in KPI_PARAMETERS
}
KPI_SCALAR_TOOLTIPS = {
    kpi: KPI_PARAMETERS[kpi]["definition"]
    for kpi in KPI_SCALARS
    if kpi in KPI_PARAMETERS
}


class KPIScalarResults(models.Model):
    scalar_values = models.TextField()  # to store the scalars dict
    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE)


class KPICostsMatrixResults(models.Model):
    cost_values = models.TextField()  # to store the scalars dict
    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE)


class OemofBusResults(pd.DataFrame):  # real results
    def __init__(self, results):

        js = json.loads(results)
        mindex = pd.MultiIndex.from_tuples(
            js["columns"],
            names=[
                "bus",
                "energy_vector",
                "direction",
                "asset",
                "asset_type",
                "oemof_type",
            ],
        )
        df = pd.DataFrame(data=js["data"], columns=mindex)

        ts_df = df.iloc[:-1]
        ts_index = pd.to_datetime(js["index"][:-1], unit="ms")
        investments = df.iloc[-1]
        ts_df.index = ts_index

        super().__init__(
            data=ts_df.T.to_dict(orient="split")["data"],
            index=mindex,
            columns=ts_df.index,
        )

        self["investments"] = investments
        self.sort_index(inplace=True)

    def to_json(self, **kwargs):
        kwargs["orient"] = "split"
        return self.T.to_json(**kwargs)

    def bus_flows(self):
        return self.loc[:, self.columns != "investments"]

    def asset_optimized_capacities(self):
        return self.loc[:, "investments"]

    def asset_optimized_capacity(self, asset_name):
        optimized_capacity = self.loc[
            self.index.get_level_values("asset") == asset_name, "investments"
        ].dropna()
        if len(optimized_capacity) == 1:
            optimized_capacity = optimized_capacity[0]
        return optimized_capacity


class FancyResults(models.Model):
    bus = models.CharField(max_length=60)
    energy_vector = models.CharField(max_length=20, choices=ENERGY_VECTOR)
    direction = models.CharField(max_length=3, default="in", blank=False)
    asset = models.CharField(
        max_length=60
    )  # models.ForeignKey(Asset, on_delete=models.CASCADE)
    asset_type = models.CharField(max_length=60, choices=ASSET_TYPE)
    oemof_type = models.CharField(max_length=60, choices=MVS_TYPE, default=None)
    flow_data = models.TextField()
    total_flow = models.FloatField(null=True, blank=False)
    optimized_capacity = models.FloatField(null=True, blank=False)
    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE, default=None)

    def save(self, *args, **kwargs):
        # for oemof 0.5.1 the last index is None for all timeseries
        if self.flow_data[-1] is None:
            self.flow_data = self.flow_data[:-1]
        try:
            self.total_flow = np.array(self.flow_data).sum()
        except TypeError:
            logging.error(
                f"The flow data of the asset {self.asset} have some NaN value"
            )
            import pdb

            pdb.set_trace()
        super().save(*args, **kwargs)


class FlowResults(models.Model):
    flow_data = models.TextField()  # to store the assets list
    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE)
    __df_flows = None
    __df_capacities = None

    @property
    def df_flows(self):
        if self.__df_flows is None:
            self.__df_flows = OemofBusResults(self.flow_data).bus_flows()

        return self.__df_flows

    def asset_optimized_capacity(self, asset_name):
        if self.__df_capacities is None:
            self.__df_capacities = OemofBusResults(self.flow_data)
        return self.__df_capacities.asset_optimized_capacity(asset_name)

    @property
    def busses(self):
        """returns a mapping of the bus to their energy_vectors"""
        return {
            k: v
            for k, v in zip(
                self.df_flows.index.get_level_values("bus"),
                self.df_flows.index.get_level_values("energy_vector"),
            )
        }

    def single_bus_flows(self, bus_name):
        df_bus = self.df_flows.loc[bus_name]
        energy_vector = df_bus.index.get_level_values("energy_vector").unique()[0]
        # TODO label charge and discharge for storages
        df_bus.index = df_bus.index.droplevel(
            ["asset_type", "energy_vector", "oemof_type"]
        )
        df = pd.concat(
            [
                df_bus.loc[df_bus.index.get_level_values("direction") == "in"].T,
                df_bus.loc[df_bus.index.get_level_values("direction") == "out"].T * -1,
            ],
            axis=1,
        )
        df.name = bus_name

        df.energy_vector = energy_vector

        return df

    def single_bus_flows_figure(self, bus_name):
        df = self.single_bus_flows(bus_name)
        fig = go.Figure(
            data=[
                go.Scatter(
                    x=df.index.tolist(),
                    y=df.loc[:, col].values.tolist(),
                    name=col[1],
                    stackgroup=col[0],
                )
                for col in df.columns
            ],
            layout=dict(
                title=f"{bus_name} ({df.energy_vector})", hovermode="x unified"
            ),
        )

        return fig.to_dict()

    def all_flows(self, include_hidden_assets=False, asset_list=None):
        df = self.df_flows
        # df = df.loc[
        #     (
        #         (df.index.get_level_values("direction") == "out")
        #         & (df.index.get_level_values("oemof_type") == "transformer")
        #     )
        #     == False
        # ]

        if asset_list is not None:
            include_hidden_assets = True

        if include_hidden_assets is False:
            df = df.loc[
                (
                    df.index.get_level_values("asset").str.contains("@")
                    | df.index.get_level_values("asset").str.contains("_excess")
                )
                == False
            ]

        if asset_list is not None:
            df = df.loc[df.index.get_level_values("asset").isin(asset_list)]

        df.index = df.index.droplevel(["asset_type", "energy_vector", "bus"])
        df = df.T

        # Label charge and discharge of storage components
        col_names = []
        for col in df.columns:
            if col[2] == "storage":
                suffix = "charge" if col[0] == "out" else "discharge"
                col_names.append(f"{col[1]} {suffix}")
            elif col[2] == "transformer":
                suffix = "inflow" if col[0] == "out" else "outflow"
                col_names.append(f"{col[1]} ({suffix})")
            else:
                col_names.append(col[1])

        df.columns = col_names

        return df

    def all_flows_figure(
        self,
        include_hidden_assets=False,
        asset_list=None,
        title="All timeseries",
        df=None,
    ):
        if df is None:
            df = self.all_flows(include_hidden_assets, asset_list)
        fig = go.Figure(
            data=[
                go.Scatter(x=df.index.tolist(), y=df.loc[:, col].values, name=col)
                for col in df.columns
            ],
            layout=dict(title=title, hovermode="x unified", yaxis_title="Power (kW)"),
        )
        # import pdb;pdb.set_trace()
        return fig.to_json()

    # def all_bus_flows_figure(self, exclude=None):
    #     if exclude is None:
    #         exclude = []
    #     df = self.single_bus_flows(bus_name)
    #     fig = go.Figure(
    #         data=[
    #             go.Scatter(
    #                 x=df.index, y=df.loc[:, col].values, name=col[1], stackgroup=col[0]
    #             )
    #             for col in df.columns
    #         ],
    #         layout=dict(
    #             title=f"{bus_name} ({df.energy_vector})", hovermode="x unified"
    #         ),
    #     )
    #
    #     return fig.to_dict()

    def energy_sector_flows(
        self, energy_vector, include_hidden_assets=False, asset_list=None
    ):
        df = self.df_flows.loc[
            (self.df_flows.index.get_level_values("energy_vector") == energy_vector)
        ]

        if asset_list is not None:
            include_hidden_assets = True

        if include_hidden_assets is False:
            df = df.loc[
                (
                    df.index.get_level_values("asset").str.contains("@")
                    | df.index.get_level_values("asset").str.contains("_excess")
                )
                == False
            ]

        if asset_list is not None:
            df = df.loc[df.index.get_level_values("asset").isin(asset_list)]

        # ignore the flows which are 0 everywhere
        df = df[df.sum(axis=1).values != 0]  # .sum(axis=1).values

        df.index = df.index.droplevel(["asset_type", "energy_vector", "bus"])
        df = df.T

        # Label inflow and outflow of transformer components
        col_names = []
        for col in df.columns:
            if col[2] != "transformer":
                col_names.append(col[1])
            else:
                suffix = "inflow" if col[0] == "out" else "outflow"
                col_names.append(f"{col[1]} ({suffix})")

        df.columns = col_names

        # TDB if we keep it (if we discard one of the in or out flow of transformer component
        # If a transformers appears twice we keep only the flow which goes from
        # for asset_name in df.loc[df.index.get_level_values("oemof_type") == "transformer"].index.get_level_values("asset").unique():
        #    if len(df.loc[df_ev.index.get_level_values("asset") == asset_name]) > 1:
        #        idx_to_drop = (df.index.get_level_values("asset") == asset_name) & (df.index.get_level_values("direction") == "out")
        #        #df.drop(index=df[idx_to_drop].index, inplace=True)
        #
        # df.loc[idx_to_drop].rename({asset_name: asset_name + "out"})
        return df

    def energy_sector_flows_figure(
        self,
        energy_vector,
        include_hidden_assets=False,
        asset_list=None,
        title="All timeseries",
        df=None,
    ):
        if df is None:
            df = self.energy_sector_flows(
                energy_vector, include_hidden_assets, asset_list
            )
        fig = go.Figure(
            data=[
                go.Scatter(x=df.index, y=df.loc[:, col].values, name=col)
                for col in df.columns
            ],
            layout=dict(
                title=f"{title} {energy_vector}",
                hovermode="x unified",
                yaxis_title="Power (kW)",
            ),
        )

        return fig.to_json()

    def load_duration_figure(self, energy_vector):
        df_consumption = (
            self.df_flows.loc[
                (self.df_flows.index.get_level_values("direction") == "out")
                & (
                    self.df_flows.index.get_level_values("energy_vector")
                    == energy_vector
                )
            ]
            .groupby(level="asset_type")
            .sum()
            .T
        )

        # df_consumption["excess"] *= 0
        df_consumption = df_consumption.sum(axis=1)
        df_production = (
            self.df_flows.loc[
                (self.df_flows.index.get_level_values("direction") == "in")
                & (
                    self.df_flows.index.get_level_values("energy_vector")
                    == energy_vector
                )
            ]
            .groupby(level="asset_type")
            .sum()
            .T
        )
        percentage = np.linspace(0, 100, df_production.index.size)
        fig = go.Figure(
            data=[
                go.Scatter(
                    x=percentage.tolist(),
                    y=df_production.loc[:, col]
                    .sort_values(ascending=False)
                    .values.tolist(),
                    name=col,
                    stackgroup="production",
                )
                for col in df_production.columns
            ]
            + [
                go.Scatter(
                    x=percentage.tolist(),
                    y=df_consumption.sort_values(ascending=False).values.tolist(),
                    name="demand",
                )
            ],
            layout=dict(
                title=f"Load duration curve for {energy_vector}", hovermode="x unified"
            ),
        )

        return fig.to_json()

    # TODO use Fancy results for it
    def sankey(self, energy_vector):
        if isinstance(energy_vector, list) is False:
            energy_vector = [energy_vector]
        if energy_vector is not None:
            labels = []
            sources = []
            targets = []
            values = []
            colors = []

            for bus_name in self.busses:
                if "@" not in bus_name:
                    bus_label = bus_name
                    labels.append(bus_label)
                    colors.append("blue")
                    df_bus = self.df_flows.loc[bus_label]
                    asset_to_bus_names = []
                    bus_to_asset_names = []

                    bus_inputs = df_bus.loc[
                        df_bus.index.get_level_values("direction") == "in"
                    ].index.get_level_values("asset")
                    for component in bus_inputs:

                        asset_to_bus_names.append(component)

                    bus_outputs = df_bus.loc[
                        df_bus.index.get_level_values("direction") == "out"
                    ].index.get_level_values("asset")
                    for component in bus_outputs:
                        bus_to_asset_names.append(component)

                    for component_label in asset_to_bus_names:
                        # draw link from the component to the bus
                        if component_label not in labels:
                            labels.append(component_label)
                            colors.append("green")

                        sources.append(labels.index(component_label))
                        targets.append(labels.index(bus_label))

                        val = df_bus.loc[
                            (df_bus.index.get_level_values("direction") == "in")
                            & (
                                df_bus.index.get_level_values("asset")
                                == component_label
                            )
                        ].T.sum()[0]

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

                        val = df_bus.loc[
                            (df_bus.index.get_level_values("direction") == "out")
                            & (
                                df_bus.index.get_level_values("asset")
                                == component_label
                            )
                        ].T.sum()

                        val = val[0]

                        if val == 0:
                            val = 1e-6
                        values.append(val)

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
        return fig.to_json()


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
                                storage_subasset["category"] = (
                                    format_storage_subasset_name(category, sub_cat)
                                )
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
                            and "@" not in asset["label"]
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
                                        answer["category"] = (
                                            format_storage_subasset_name(
                                                category, sub_cat
                                            )
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
            asset_type = asset_results["type_oemof"]
            if (
                asset_results["type_oemof"] == "extractionTurbineCHP"
                or asset_results.get("asset_type") == "chp_fixed_ratio"
            ):
                if energy_vector is not None:
                    bus_name = self.energy_vector_busses(energy_vector)
                    if bus_name in flow_value:
                        flow_value = flow_value[bus_name]
                    else:
                        flow_value = None
                    asset_name = asset_name + "_" + energy_vector
                asset_type = "chp"

            if flow_value is not None:
                answer = single_timeseries_to_json(
                    value=flow_value,
                    unit=asset_results["flow"]["unit"],
                    label=asset_name,
                    asset_type=asset_type,
                    asset_category=asset_results["category"],
                )

        # if an energy_vector is provided return the timeseries only if the energy_vector type of the asset matches
        if energy_vector is not None:
            if (
                energy_vector not in asset_results.get("output_busses", {}).values()
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


def graph_timeseries(simulations, y_variables=None):
    simulations_results = []
    for sim in simulations:
        qs = FancyResults.objects.filter(simulation=sim, total_flow__gt=0)

        if y_variables is None:
            qs = qs.exclude(Q(asset__contains="@"))
        else:
            qs = qs.filter(asset__in=y_variables)

        qs = qs.annotate(
            label=Case(
                When(
                    Q(oemof_type="storage") & Q(direction="out"),
                    then=Concat("asset", Value(" charge")),
                ),
                When(
                    Q(oemof_type="storage") & Q(direction="in"),
                    then=Concat("asset", Value(" discharge")),
                ),
                When(
                    Q(oemof_type="transformer") & Q(direction="out"),
                    then=Concat("asset", Value(" (inflow)")),
                ),
                When(
                    Q(oemof_type="transformer") & Q(direction="in"),
                    then=Concat("asset", Value(" (outflow)")),
                ),
                default="asset",
            ),
            group=Case(
                When(Q(oemof_type="storage") & Q(direction="out"), then=Value(-1)),
                When(Q(oemof_type="transformer") & Q(direction="out"), then=Value(-1)),
                When(Q(oemof_type="sink"), then=Value(-1)),
                default=Value(1),
            ),
            unit=Value("kW"),
            value=F("flow_data"),
        )
        # FilteredRelation() objects
        y_values = []
        # TODO asset_type filtering here
        for y_val in qs.order_by("-group", "oemof_type", "-asset_type").values(
            "value", "label", "total_flow", "unit", "group"
        ):
            y_val["value"] = (
                y_val["group"] * np.array(json.loads(y_val["value"]))
            ).tolist()
            y_values.append(y_val)

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

        qs = FancyResults.objects.filter(
            simulation=simulation, total_flow__gt=0, energy_vector=energy_vector
        )
        if y_variables is None:
            qs = qs.exclude(Q(asset__contains="@"))
        else:
            qs = qs.filter(asset__in=y_variables)

        qs = qs.annotate(
            label=Case(
                When(
                    Q(oemof_type="storage") & Q(direction="out"),
                    then=Concat("asset", Value(" charge")),
                ),
                When(
                    Q(oemof_type="storage") & Q(direction="in"),
                    then=Concat("asset", Value(" discharge")),
                ),
                When(
                    Q(oemof_type="transformer") & Q(direction="out"),
                    then=Concat("asset", Value(" (inflow)")),
                ),
                When(
                    Q(oemof_type="transformer") & Q(direction="in"),
                    then=Concat("asset", Value(" (outflow)")),
                ),
                default="asset",
            ),
            unit=Value("kW"),
            value=F("flow_data"),
            fill=Case(
                When(Q(oemof_type="sink"), then=Value("none")),
                When(Q(oemof_type="storage") & Q(direction="out"), then=Value("none")),
                When(
                    Q(asset_type__in=("heat_pump", "chp_fixed_ratio", "chp"))
                    & Q(direction="out"),
                    then=Value("none"),
                ),
                default=Value("tonexty"),
            ),
            group=Case(
                When(
                    Q(oemof_type="storage") & Q(direction="out"), then=Value("demand")
                ),
                When(
                    Q(asset_type__in=("heat_pump", "chp_fixed_ratio", "chp"))
                    & Q(direction="out"),
                    then=Value("demand"),
                ),
                When(
                    Q(oemof_type="sink"),  # & Q(asset_type__contains="demand"),
                    then=Value("demand"),
                ),
                default=Value("production"),
            ),
            mode=Case(
                When(Q(oemof_type="storage") & Q(direction="out"), then=Value("lines")),
                When(
                    Q(oemof_type="sink"),  # & Q(asset_type__contains="demand"),
                    then=Value("lines"),
                ),
                When(
                    Q(asset_type__in=("heat_pump", "chp_fixed_ratio", "chp"))
                    & Q(direction="out"),
                    then=Value("lines"),
                ),
                default=Value("none"),
            ),
            plot_order=Case(
                When(
                    Q(oemof_type="sink") & Q(label__contains="_excess"), then=Value(1)
                ),
                When(Q(oemof_type__contains="ess"), then=Value(3)),
                When(
                    Q(oemof_type="sink") & Q(label__contains="_feedin"), then=Value(2)
                ),
                When(Q(oemof_type="sink"), then=Value(4)),
                default=Value(0),
            ),
        )
        y_values = []
        # set the stacked lines order, first demand, then storages and finally dsos
        for y_val in qs.order_by("mode", "plot_order").values(
            "value", "label", "total_flow", "unit", "fill", "group", "mode"
        ):
            y_val["value"] = json.loads(y_val["value"])
            y_values.append(y_val)

        simulations_results.append(
            simulation_timeseries_to_json(
                scenario_name=simulation.scenario.name,
                scenario_id=simulation.scenario.id,
                scenario_timeseries=y_values[::-1],
                scenario_timestamps=simulation.scenario.get_timestamps(),
            )
        )
    return simulations_results


def graph_capacities(simulations, y_variables):
    simulations_results = []
    multi_scenario = False
    if len(simulations) > 1:
        multi_scenario = True

    if y_variables is None:
        y_variables = (
            Asset.objects.filter(scenario__simulation__in=simulations)
            .exclude(
                Q(asset_type__asset_type__contains="dso")
                | Q(asset_type__asset_type__contains="demand")
                | Q(asset_type__asset_type__in=["charging_power", "capacity"])
            )
            .filter(installed_capacity__isnull=False)
            .annotate(
                label=Case(
                    When(
                        Q(asset_type__asset_type="discharging_power"),
                        then=Replace("name", Value(" output power"), Value("")),
                    ),
                    default="name",
                )
            )
            .order_by("label")
            .distinct()
            .values_list("label", flat=True)
        )
    for simulation in simulations:
        y_values = (
            []
        )  # stores the capacity, both installed and optimized in separate dicts, of each individual asset/ component
        x_values = []  # stores the label of the corresponding asset

        installed_capacity_dict = {
            "capacity": [],
            "name": (
                _("Installed Capacity")
                if multi_scenario is False
                else _("Inst. Cap.") + f"{simulation.scenario.name}"
            ),
        }
        optimized_capacity_dict = {
            "capacity": [],
            "name": (
                _("Optimized Capacity")
                if multi_scenario is False
                else _("Opt. Cap.") + f"{simulation.scenario.name}"
            ),
        }

        # read information about the installed capacity
        qs1 = (
            Asset.objects.filter(scenario__simulation=simulation)
            .exclude(
                Q(asset_type__asset_type__contains="dso")
                | Q(asset_type__asset_type__contains="demand")
                | Q(asset_type__asset_type__in=["charging_power", "capacity"])
            )
            .filter(installed_capacity__isnull=False)
            .annotate(
                label=Case(
                    When(
                        Q(asset_type__asset_type="discharging_power"),
                        then=Replace("name", Value(" output power"), Value("")),
                    ),
                    default="name",
                )
            )
            .order_by("label")
        )

        # read information about the optimized capacity
        qs2 = (
            FancyResults.objects.filter(simulation=simulation)
            .exclude(
                (Q(oemof_type="storage") & Q(direction="out"))
                | Q(asset_type="capacity")
            )
            .annotate(label=Case(default="asset"))
            .filter(
                label__in=qs1.values_list("label", flat=True),
                optimized_capacity__isnull=False,
            )
            .order_by("label")
        )
        ic = {
            item[0]: item[1]
            for item in qs1.filter(label__in=y_variables).values_list(
                "label", "installed_capacity"
            )
        }
        oc = {
            item[0]: item[1]
            for item in qs2.filter(label__in=y_variables).values_list(
                "label", "optimized_capacity"
            )
        }

        for asset_name in y_variables:

            if asset_name in ic:
                installed_cap = ic[asset_name]
            else:
                installed_cap = 0

            if asset_name in oc:
                optimized_cap = oc[asset_name]
            else:
                optimized_cap = 0

            if optimized_cap + installed_cap > 0:
                x_values.append(asset_name)
                installed_capacity_dict["capacity"].append(installed_cap)
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


def get_costs(simulation, y_variables=None):
    simulations_results = []
    if y_variables is None:
        y_variables = (
            Asset.objects.filter(scenario__simulation=simulation)
            .filter(installed_capacity__isnull=False)
            .annotate(label=Case(default="name"))
            .order_by("label")
            .distinct()
            .values_list("label", flat=True)
        )

    # read information about the installed capacity
    qs1 = (
        Asset.objects.filter(scenario__simulation=simulation)
        .annotate(label=Case(default="name"))
        .order_by("label")
    )

    # read information about the optimized capacity
    qs2 = (
        FancyResults.objects.filter(simulation=simulation)
        .annotate(
            label=Case(
                When(
                    Q(oemof_type="storage") & Q(direction="out"),
                    then=Concat("asset", Value(" input power")),
                ),
                When(
                    Q(oemof_type="storage") & Q(direction="in"),
                    then=Concat("asset", Value(" output power")),
                ),
                When(
                    Q(oemof_type="storage") & Q(asset_type="capacity"),
                    then=Concat("asset", Value(" capacity")),
                ),
                default="asset",
            )
        )
        .order_by("label")
    )

    qs1 = qs1.filter(label__in=y_variables).values(
        "label",
        "installed_capacity",
        "capex_fix",
        "capex_var",
        "opex_fix",
        "opex_var",
        "lifetime",
        "energy_price",
        "parent_asset__name",
    )

    records = []
    for el in qs1:
        qs_asset_results = qs2.filter(label=el["label"])
        if qs_asset_results.count() == 1:
            el.update(
                qs_asset_results.values(
                    "optimized_capacity", "total_flow", "direction"
                ).get()
            )
        elif qs_asset_results.count() > 1:
            qs_asset_results = qs_asset_results.filter(optimized_capacity__isnull=False)
            if qs_asset_results.count() == 1:
                el.update(
                    qs_asset_results.values(
                        "optimized_capacity", "total_flow", "direction"
                    ).get()
                )
            elif qs_asset_results.count() > 1:
                # TODO bug here online with Lübben
                raise ValueError("should not have too much labels")
        records.append(el)

    wacc = simulation.scenario.project.economic_data.discount
    df = pd.DataFrame.from_records(records)

    # assign optimized capacity to storage components
    storages = df.parent_asset__name.dropna().unique()
    for ess in storages:

        opt_cap = df.loc[
            (df.parent_asset__name == ess) & (df.direction == "out"),
            "optimized_capacity",
        ]

        if opt_cap.empty is False:
            df.loc[
                (df.parent_asset__name == ess) & (df.direction.isna() == True),
                "optimized_capacity",
            ] = df.loc[
                (df.parent_asset__name == ess) & (df.direction == "out"),
                "optimized_capacity",
            ].values[
                0
            ]

    df = df.fillna(0)

    def annualize_capex(capex, wacc, lifetime):
        ann_capex = (
            capex * (wacc * (1 + wacc) ** lifetime) / ((1 + wacc) ** lifetime - 1)
        )
        return ann_capex

    # TODO costs for batteries are skewed as battery capacity does not exists in fancy results
    # TODO costs for dso not implemented yet
    df["capex_total"] = df.apply(
        lambda x: annualize_capex(
            ((x.installed_capacity + x.optimized_capacity) * x.capex_var),
            wacc,
            x.lifetime,
        ),
        axis=1,
    )

    df["opex_fix_total"] = df.apply(
        lambda x: (x.installed_capacity + x.optimized_capacity) * x.opex_fix, axis=1
    )
    df["opex_var_total"] = df.apply(lambda x: x.total_flow * x.opex_var, axis=1)

    # nur für dso ...
    df["fuel_costs_total"] = df.apply(lambda x: x.total_flow * x.energy_price, axis=1)

    # TODO fuel costs

    df = df[
        [
            "label",
            "capex_total",
            "opex_fix_total",
            "opex_var_total",
            "fuel_costs_total",
            "parent_asset__name",
        ]
    ].set_index("label")

    # merge the costs of the storages together
    for ess in storages:
        agr = (
            df.loc[(df.parent_asset__name == ess)].groupby(["parent_asset__name"]).sum()
        )
        df = pd.concat([df, agr])
        df.drop(df.loc[(df.parent_asset__name == ess)].index, inplace=True)
    df.drop(columns=["parent_asset__name"], inplace=True)

    # drop dataframe rows where all values are 0 (can happen for inverter in diesel only scenario)
    df = df.loc[~(df == 0).all(axis=1)]
    return df


def graph_costs(
    simulations, y_variables=None, arrangement=COSTS_PER_CATEGORY
):  # COSTS_PER_CATEGORY
    simulations_results = []
    multi_scenario = False
    if len(simulations) > 1:
        multi_scenario = True

    if arrangement in [COSTS_PER_ASSETS_STACKED, COSTS_PER_CATEGORY_STACKED]:
        x_values = [
            x
            for x in Scenario.objects.filter(simulation__in=simulations).values_list(
                "name", flat=True
            )
        ]
        y_values = []

    for simulation in simulations:
        df = get_costs(simulation, y_variables)

        if arrangement == COSTS_PER_ASSETS:
            x_values = df.index.values.tolist()
            y_values = []
            for i in range(len(df.columns)):
                name = df.iloc[:, i].name.replace("_total", "")
                y = df.iloc[:, i].values.tolist()
                y_values.append(
                    {
                        "base": (
                            df.iloc[:, :i].sum(axis=1).values.tolist()
                            if i > 0
                            else None
                        ),
                        "value": y,
                        "text": [name for j in range(len(x_values))],
                        "name": (
                            name
                            if multi_scenario is False
                            else name + f" {simulation.scenario.name}"
                        ),
                        "hover": "<b>%{text}, </b><br><br>Block value: %{customdata:.2f}$<br>Stacked value: %{y:.2f}$<extra> %{x}</extra>",
                        "customdata": y,
                        # https://stackoverflow.com/questions/59057881/python-plotly-how-to-customize-hover-template-on-with-what-information-to-show
                    }
                )

        elif arrangement == COSTS_PER_CATEGORY:
            x_values = df.columns.tolist()
            y_values = []
            for i in range(len(df.index)):
                name = df.iloc[i, :].name
                y = df.iloc[i, :].values.tolist()
                y_values.append(
                    {
                        "base": (
                            df.iloc[:i, :].sum(axis=0).values.tolist()
                            if i > 0
                            else None
                        ),
                        "value": y,
                        "text": [name for j in range(len(x_values))],
                        "name": (
                            name
                            if multi_scenario is False
                            else name + f" {simulation.scenario.name}"
                        ),
                        "hover": "<b>%{text}</b><br><br>Block value: %{customdata:.2f}$<br>Stacked value: %{y:.2f}$",
                        "customdata": y,
                    }
                )

        elif arrangement == COSTS_PER_CATEGORY_STACKED:
            y_values.append(df.sum(axis=1))
        elif arrangement == COSTS_PER_ASSETS_STACKED:
            y_values.append(df.sum(axis=0))

        if arrangement in [COSTS_PER_ASSETS, COSTS_PER_CATEGORY]:
            simulations_results.append(
                simulation_timeseries_to_json(
                    scenario_name=simulation.scenario.name,
                    scenario_id=simulation.scenario.id,
                    scenario_timeseries=y_values,
                    scenario_timestamps=x_values,
                )
            )

    if arrangement in [COSTS_PER_CATEGORY_STACKED, COSTS_PER_ASSETS_STACKED]:
        df = pd.concat(y_values, axis=1).fillna(0)
        for i, asset in enumerate(df.index):
            simulations_results.append(
                simulation_timeseries_to_json(
                    scenario_name=asset,
                    scenario_id=None,
                    scenario_timeseries=df.loc[asset].values.tolist(),
                    scenario_timestamps=x_values,
                )
            )
    return simulations_results


def graph_sankey(simulation, energy_vector, timestep=None):

    # for DSO results
    dso_period_suffix = "_period (@)"

    ts = timestep
    if isinstance(energy_vector, list) is False:
        energy_vector = [energy_vector]
    if energy_vector is not None:
        labels = []
        sources = []
        targets = []
        values = []
        colors = []

        sim = simulation

        chp_qs = Asset.objects.filter(
            scenario=sim.scenario, asset_type__asset_type__in=("chp", "chp_fixed_ratio")
        )
        if chp_qs.exists():
            chp_in_flow = {a.name: {"value": 0, "bus": ""} for a in chp_qs}
        else:
            chp_in_flow = {}

        qs = FancyResults.objects.filter(simulation=sim)

        for bus in Bus.objects.filter(scenario__simulation=sim, type__in=energy_vector):
            bus_label = bus.name
            labels.append(bus_label)
            colors.append("blue")

            if ts is None:
                asset_to_bus_names = qs.filter(
                    bus=bus.name, direction="in"
                ).values_list("asset", "total_flow")
            else:
                asset_to_bus_names = qs.filter(
                    bus=bus.name, direction="in"
                ).values_list("asset", "flow_data")

            for component_label, val in asset_to_bus_names:

                if dso_period_suffix in component_label:
                    component_label = component_label.replace(dso_period_suffix, "")
                    if ts is None:
                        val = (
                            qs.filter(asset=component_label)
                            .values_list("total_flow")
                            .get()[0]
                        )
                    else:
                        val = (
                            qs.filter(asset=component_label)
                            .values_list("flow_data")
                            .get()[0]
                        )

                # draw link from the component to the bus
                if component_label not in labels:
                    labels.append(component_label)
                    colors.append("green")

                sources.append(labels.index(component_label))
                targets.append(labels.index(bus_label))

                if ts is not None:
                    val = json.loads(val)
                    val = val[ts]

                if component_label in chp_in_flow:
                    chp_in_flow[component_label]["value"] += val

                # if val == 0:
                #     val = 1e-9
                values.append(val)
            if ts is None:
                bus_to_asset_names = qs.filter(
                    bus=bus.name, direction="out"
                ).values_list("asset", "total_flow")
            else:
                bus_to_asset_names = qs.filter(
                    bus=bus.name, direction="out"
                ).values_list("asset", "flow_data")

            for component_label, val in bus_to_asset_names:
                # draw link from the bus to the component

                if dso_period_suffix in component_label:
                    component_label = component_label.replace(dso_period_suffix, "")
                    if ts is None:
                        val = (
                            qs.filter(asset=component_label)
                            .values_list("total_flow")
                            .get()[0]
                        )
                    else:
                        val = (
                            qs.filter(asset=component_label)
                            .values_list("flow_data")
                            .get()[0]
                        )

                if component_label not in labels:
                    labels.append(component_label)
                    colors.append("red")

                sources.append(labels.index(bus_label))
                targets.append(labels.index(component_label))

                if component_label in chp_in_flow:
                    chp_in_flow[component_label]["bus"] = bus_label

                if ts is not None:
                    val = json.loads(val)
                    val = val[ts]

                # if val == 0:
                #     val = 1e-9
                values.append(val)

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
    GRAPH_COSTS: graph_costs,
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

        n_simulations = len(self.simulations.all())
        qs = FancyResults.objects.filter(simulation__in=self.simulations.all())

        if qs.count() == 0 or qs.count() < n_simulations:
            fig_json = {
                "layout": {
                    "title": "Some simulations haven't been ran since the update of open-plan-tool. Please consider running the simulation from the last step of the scenario again"
                }
            }
            return fig_json

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
                    simulations=self.simulations.all().order_by("scenario__id"),
                    y_variables=y_variables,
                )

        if self.report_type == GRAPH_COSTS:
            y_variables = parameters.get("y", None)

            if y_variables is not None:
                return graph_costs(
                    simulations=self.simulations.all().order_by("scenario__id"),
                    y_variables=y_variables,
                )

        if self.report_type == GRAPH_SANKEY:
            energy_vector = parameters.get("energy_vector", None)

            return graph_sankey(
                simulation=self.simulations.get(), energy_vector=energy_vector
            )

        if self.report_type == GRAPH_LOAD_DURATION:
            energy_vector = parameters.get("energy_vector", None)

            simulation = self.simulations.get()
            # if isinstance(energy_vector, list) is False:
            #     energy_vector = [energy_vector]
            if energy_vector is not None:

                sim = simulation
                qs = FlowResults.objects.filter(simulation=sim)
                if qs.exists():
                    flow_results = qs.get()
                    fig_dict = flow_results.load_duration_figure(energy_vector)
                else:
                    fig_dict = {
                        "layout": {"title": "There is an error with this graph."}
                    }

                return fig_dict


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
