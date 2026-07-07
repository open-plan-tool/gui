from datetime import datetime
import httpx as requests
import json
import numpy as np
import datapackage as dp
from oemof.datapackage import datapackage
import tempfile
from pathlib import Path
from oemof.eesyplan.datapackage.results import import_results
from oemof.eesyplan.datapackage.energy_system import create_energy_system_from_dp
import pandas as pd
from oemof.eesyplan.components.buses.carrier import CarrierBus
from oemof.solph import Bus

# from requests.exceptions import HTTPError
from epa.settings import (
    PROXY_CONFIG,
    MVS_POST_URL,
    MVS_GET_URL,
    MVS_SA_POST_URL,
    MVS_SA_GET_URL,
    EZP_POST_URL,
    EZP_GET_URL,
    ROOT_DIR,
)
from dashboard.models import (
    FancyResults,
    AssetsResults,
    KPICostsMatrixResults,
    KPIScalarResults,
    FlowResults,
)
from projects.constants import DONE, PENDING, ERROR
import logging

from projects.models import Timeseries
from projects.helpers import validate_dp_results

logger = logging.getLogger(__name__)


def ezp_simulation_request(data: dict):
    headers = {"content-type": "application/json"}
    payload = json.dumps(data)
    try:
        response = requests.post(
            EZP_POST_URL,
            data=payload,
            headers=headers,
            proxies=PROXY_CONFIG,
            verify=False,
        )

        # If the response was successful, no Exception will be raised
        response.raise_for_status()
    except requests.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        logger.error(f"Other error occurred: {err}")
        return None
    else:
        logger.info("The simulation was sent successfully to MVS API.")
        return json.loads(response.text)


def ezp_simulation_check_status(token):
    try:
        response = requests.get(EZP_GET_URL + token, proxies=PROXY_CONFIG, verify=False)
        response.raise_for_status()
    except requests.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        logger.error(f"Other error occurred: {err}")
        return None
    else:
        logger.info("Success!")
        return json.loads(response.text)


def fetch_ezp_simulation_results(simulation):
    if simulation.status == PENDING:
        response = ezp_simulation_check_status(token=simulation.mvs_token)
        try:
            simulation.status = response["status"]
            simulation.mvs_version = response["simulation_version"]
            simulation.errors = (
                json.dumps(response["results"][ERROR])
                if simulation.status == ERROR
                else None
            )
            if simulation.status == DONE:
                simulation.results = json.dumps(response["results"])
                simulation.dp_results = json.dumps(response["results"]["raw_results"])

            # simulation.mvs_version = response["mvs_version"]
            logger.info(f"The simulation {simulation.id} is finished")
        except:
            simulation.status = ERROR
            simulation.results = None

        simulation.elapsed_seconds = (datetime.now() - simulation.start_date).seconds

        # Cancel simulation if it has been going on > 48h
        max_simulation_seconds = 48 * 60 * 60
        if simulation.elapsed_seconds > max_simulation_seconds:
            simulation.status = ERROR
            simulation.results = None

        simulation.end_date = (
            datetime.now() if simulation.status in [ERROR, DONE] else None
        )
        # TODO also save the dp without the timeseries within an attribute of the simulation object

        # validate_dp_results(simulation.dp_results)
        simulation.save()

    return simulation.status != PENDING


def get_component_type(es_dp, component):
    """

    Parameters
    ----------
    es_dp: datapackage object of the energy system
    component: a component of the energy system

    Returns
    -------
    The type of the component as given within the energy system's datapackage. If the component
    is a subnode its parent's type is returned instead.

    """
    component_label = component.label
    if hasattr(component, "parent"):
        if component.parent is not None:
            component_label = component.label[-1]

    for r in es_dp.resources:
        if "/elements/" in r.descriptor["path"]:
            df = pd.DataFrame.from_records(r.read(keyed=True))
            search_component = df.loc[df.name == component_label, "type"]
            if search_component.empty is False:
                return search_component.iloc[0]


def parse_ezp_results(simulation, response_results):
    data = json.loads(response_results)

    # Extract figures and raw results
    simulation.figures = data.get("figures", None)
    res = data.get("raw_results", None)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        # TODO use temp dir then
        # destination_path = Path(".").resolve() / "test_processing_res"
        # es_path = Path(".").resolve() / "test_processing_es"
        destination_path = temp_dir / "test_processing_res"

        res_path = datapackage.rebuild_dp_from_json(
            res, destination_path, overwrite=True
        )

        scenario = simulation.scenario
        rebuilt_dp = scenario.rebuild_datapackage()

        with tempfile.TemporaryDirectory(prefix="dp_") as td:
            temp_path = Path(td)
            dp_path = datapackage.rebuild_dp_from_json(rebuilt_dp, temp_path)
            es = create_energy_system_from_dp(dp_path)

            ezp_results = import_results(res_path, es)
            es_dp = dp.Package(str(dp_path / "datapackage.json"))

            qs = FancyResults.objects.filter(simulation=simulation)
            if qs.exists():
                raise ValueError("Already existing FancyResults")
            else:
                if "invest" in ezp_results:
                    invest = ezp_results["invest"]
                else:
                    invest = None

                for i, fl in enumerate(ezp_results["flow"]):
                    print(i, fl)
                    if isinstance(fl[0], CarrierBus) or isinstance(fl[0], Bus):
                        bus = fl[0]
                        component = fl[1]
                        direction = "in"
                    elif isinstance(fl[1], CarrierBus) or isinstance(fl[1], Bus):
                        bus = fl[1]
                        component = fl[0]
                        direction = "out"

                    print(component, direction, bus)

                    flow_data = ezp_results["flow"][fl].values
                    total_flow = flow_data.sum()

                    opt_capacity = None
                    if invest is not None:
                        if fl in invest.columns:
                            opt_capacity = invest.loc[0, fl]

                    # print(component.__dict__.keys())
                    print(component.label)
                    comp_type = str(type(component))
                    print(comp_type)

                    kwargs = {
                        "bus": bus.label,
                        "energy_vector": (
                            bus.carrier if hasattr(bus, "carrier") else "None"
                        ),
                        "direction": direction,
                        "asset": component.label,
                        # TODO this is now not working because of tuple labels of subcomponents
                        "asset_type": get_component_type(
                            es_dp, component
                        ),  # get it from datapackage
                        # TODO one need to allow the types in MVS_TYPE
                        "oemof_type": comp_type.split(".")[-1],  # get it from mapping
                        "flow_data": flow_data.tolist(),
                        "total_flow": total_flow,
                        "optimized_capacity": opt_capacity,
                        "simulation": simulation,
                    }
                    fr = FancyResults(**kwargs)
                    fr.save()
    # asset_key_list = []

    # TODO simply need to write the kpi_scalar dataframe from ezp_results here
    # Write Scalar KPIs to db

    qs = KPIScalarResults.objects.filter(simulation=simulation)
    if qs.exists():
        kpi_scalar = qs.first()
        kpi_scalar.scalar_values = json.dumps({})  # json.dumps(data["kpi"]["scalars"])
        kpi_scalar.save()
    else:
        KPIScalarResults.objects.create(
            scalar_values=json.dumps(json.dumps({})),
            simulation=simulation,
            # scalar_values=json.dumps(data["kpi"]["scalars"]), simulation=simulation
        )
    # TODO simply need to write the kpi_cost_matrix dataframe from ezp_results here
    # Write Cost Matrix KPIs to db
    qs = KPICostsMatrixResults.objects.filter(simulation=simulation)
    if qs.exists():
        kpi_costs = qs.first()
        kpi_costs.cost_values = json.dumps({})  # json.dumps(data["kpi"]["cost_matrix"])
        kpi_costs.save()
    else:
        KPICostsMatrixResults.objects.create(
            cost_values=json.dumps({}),
            simulation=simulation,
            # cost_values=json.dumps(data["kpi"]["cost_matrix"]), simulation=simulation
        )

    # TODO not very important, only for comparison amongst several scenarii
    # # Write Assets to db
    # data_subdict = {
    #     category: v for category, v in data.items() if category in asset_key_list
    # }
    # qs = AssetsResults.objects.filter(simulation=simulation)
    # if qs.exists():
    #     asset_results = qs.first()
    #     asset_results.asset_list = json.dumps(data_subdict)
    #     asset_results.save()
    # else:
    #     AssetsResults.objects.create(
    #         assets_list=json.dumps(data_subdict), simulation=simulation
    #     )

    simulation.results = "processed"
    simulation.save()
    return response_results


def mvs_simulation_request(data: dict):
    headers = {"content-type": "application/json"}
    payload = json.dumps(data)

    try:
        response = requests.post(
            MVS_POST_URL,
            data=payload,
            headers=headers,
            proxies=PROXY_CONFIG,
            verify=False,
        )

        # If the response was successful, no Exception will be raised
        response.raise_for_status()
    except requests.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        logger.error(f"Other error occurred: {err}")
        return None
    else:
        logger.info("The simulation was sent successfully to MVS API.")
        return json.loads(response.text)


def mvs_simulation_check_status(token):
    try:
        response = requests.get(MVS_GET_URL + token, proxies=PROXY_CONFIG, verify=False)
        response.raise_for_status()
    except requests.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        logger.error(f"Other error occurred: {err}")
        return None
    else:
        logger.info("Success!")
        return json.loads(response.text)


def mvs_sa_check_status(token):
    try:
        response = requests.get(
            MVS_SA_GET_URL + token, proxies=PROXY_CONFIG, verify=False
        )
        response.raise_for_status()
    except requests.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        logger.error(f"Other error occurred: {err}")
        return None
    else:
        logger.info("Success!")
        return json.loads(response.text)


def fetch_mvs_simulation_results(simulation):
    if simulation.status == PENDING:
        response = mvs_simulation_check_status(token=simulation.mvs_token)
        try:
            simulation.status = response["status"]
            simulation.errors = (
                json.dumps(response["results"][ERROR])
                if simulation.status == ERROR
                else None
            )
            simulation.results = (
                parse_mvs_results(simulation, response["results"])
                if simulation.status == DONE
                else None
            )
            simulation.mvs_version = response["mvs_version"]
            logger.info(f"The simulation {simulation.id} is finished")
        except:
            simulation.status = ERROR
            simulation.results = None

        simulation.elapsed_seconds = (datetime.now() - simulation.start_date).seconds

        # Cancel simulation if it has been going on > 48h
        max_simulation_seconds = 48 * 60 * 60
        if simulation.elapsed_seconds > max_simulation_seconds:
            simulation.status = ERROR
            simulation.results = None

        simulation.end_date = (
            datetime.now() if simulation.status in [ERROR, DONE] else None
        )
        simulation.save()

    return simulation.status != PENDING


def fetch_mvs_sa_results(simulation):
    if simulation.status == PENDING:
        response = mvs_sa_check_status(token=simulation.mvs_token)

        simulation.parse_server_response(response)

        if simulation.status == DONE:
            logger.info(f"The simulation {simulation.id} is finished")

    return simulation.status != PENDING


def parse_mvs_results(simulation, response_results):
    data = json.loads(response_results)
    asset_key_list = [
        "energy_consumption",
        "energy_conversion",
        "energy_production",
        "energy_providers",
        "energy_storage",
    ]

    if not set(asset_key_list).issubset(data.keys()):
        raise KeyError("There are missing keys from the received dictionary.")

    # Write Scalar KPIs to db
    qs = KPIScalarResults.objects.filter(simulation=simulation)
    if qs.exists():
        kpi_scalar = qs.first()
        kpi_scalar.scalar_values = json.dumps(data["kpi"]["scalars"])
        kpi_scalar.save()
    else:
        KPIScalarResults.objects.create(
            scalar_values=json.dumps(data["kpi"]["scalars"]), simulation=simulation
        )
    # Write Cost Matrix KPIs to db
    qs = KPICostsMatrixResults.objects.filter(simulation=simulation)
    if qs.exists():
        kpi_costs = qs.first()
        kpi_costs.cost_values = json.dumps(data["kpi"]["cost_matrix"])
        kpi_costs.save()
    else:
        KPICostsMatrixResults.objects.create(
            cost_values=json.dumps(data["kpi"]["cost_matrix"]), simulation=simulation
        )
    # Write Assets to db
    data_subdict = {
        category: v for category, v in data.items() if category in asset_key_list
    }
    qs = AssetsResults.objects.filter(simulation=simulation)
    if qs.exists():
        asset_results = qs.first()
        asset_results.asset_list = json.dumps(data_subdict)
        asset_results.save()
    else:
        AssetsResults.objects.create(
            assets_list=json.dumps(data_subdict), simulation=simulation
        )

    qs = FancyResults.objects.filter(simulation=simulation)
    if qs.exists():
        raise ValueError("Already existing FancyResults")
    else:
        # TODO add safety here with json schema
        # Raw results is a panda dataframe which was saved to json using "split"
        if "raw_results" in data:
            results = data["raw_results"]
            js = json.loads(results)
            js_data = np.array(js["data"])

            hdrs = [
                "bus",
                "energy_vector",
                "direction",
                "asset",
                "asset_type",
                "oemof_type",
                "flow_data",
                "optimized_capacity",
            ]

            # each columns already contains the values of the hdrs except for flow_data and optimized_capacity
            # we append those values here
            for i, col in enumerate(js["columns"]):
                col.append(js_data[:-1, i].tolist())
                col.append(js_data[-1, i])

                kwargs = {hdr: item for hdr, item in zip(hdrs, col)}
                kwargs["simulation"] = simulation
                fr = FancyResults(**kwargs)
                fr.save()

    return response_results


def mvs_sensitivity_analysis_request(data: dict):
    headers = {"content-type": "application/json"}
    payload = json.dumps(data)

    try:
        response = requests.post(
            MVS_SA_POST_URL,
            data=payload,
            headers=headers,
            proxies=PROXY_CONFIG,
            verify=False,
        )

        # If the response was successful, no Exception will be raised
        response.raise_for_status()
    except requests.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        logger.error(f"Other error occurred: {err}")
        return None
    else:
        logger.info("The simulation was sent successfully to MVS API.")
        return json.loads(response.text)
