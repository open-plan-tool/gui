from datetime import datetime
import httpx as requests
import json
import numpy as np

# from requests.exceptions import HTTPError
from epa.settings import (
    PROXY_CONFIG,
    MVS_POST_URL,
    MVS_GET_URL,
    MVS_SA_POST_URL,
    MVS_SA_GET_URL,
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

logger = logging.getLogger(__name__)


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
        simulation.end_date = (
            datetime.now() if response["status"] in [ERROR, DONE] else None
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
