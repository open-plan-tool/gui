from datetime import datetime
import httpx as requests
import json
import numpy as np
import time

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


def mvs_simulation_request(data: dict, max_retries: int = 5, delay_seconds: int = 2):
    headers = {"content-type": "application/json"}
    payload = json.dumps(data)

    def _post_once():
        response = requests.post(
            MVS_POST_URL,
            data=payload,
            headers=headers,
            proxies=PROXY_CONFIG,
            verify=False,
        )
        response.raise_for_status()
        return response

    def _extract_token(resp_json: dict):
        # try common keys without changing upstream API expectations
        return resp_json.get("id")

    def _check(token: str):
        # return (ok: bool, status_code: int)
        try:
            r = requests.get(MVS_GET_URL + token, proxies=PROXY_CONFIG, verify=False)
            # if it’s a 500, we don’t raise — we want to see the 500 explicitly
            if r.status_code == 500:
                return False, 500
            r.raise_for_status()
            return True, r.status_code
        except requests.HTTPError as e:
            status = getattr(e.response, "status_code", None)
            # treat any other HTTP error as non-500 failure (don’t retry POST)
            return False, status or 0
        except Exception:
            return False, 0

    try:
        # initial attempt
        post_resp = _post_once()
        post_json = json.loads(post_resp.text)
        token = _extract_token(post_json)

        if not token:
            logger.info(
                "The simulation was sent successfully to MVS API (no token found to check)."
            )
            return post_json

        ok, code = _check(token)
        if ok or code != 500:
            logger.info("The simulation was sent successfully to MVS API.")
            return post_json

        # retry path only when immediate check returned 500
        for attempt in range(1, max_retries + 1):
            logger.warning(
                "Check returned 500; re-sending simulation (attempt %d/%d)...",
                attempt,
                max_retries,
            )
            time.sleep(delay_seconds)

            post_resp = _post_once()
            post_json = json.loads(post_resp.text)
            token = _extract_token(post_json)

            if not token:
                logger.info(
                    "Re-sent simulation successfully (no token found to check)."
                )
                return post_json

            ok, code = _check(token)
            if ok or code != 500:
                logger.info("Re-sent simulation successfully; check no longer 500.")
                return post_json

        logger.error(
            "Check kept returning 500 after %d retries; giving up.", max_retries
        )
        return None

    except requests.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        logger.error(f"Other error occurred: {err}")
        return None


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
