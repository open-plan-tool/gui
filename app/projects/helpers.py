import json
import os
import csv
from django.contrib.staticfiles.storage import staticfiles_storage
from projects.dtos import convert_to_dto
from projects.constants import MAP_MVS_EPA
from dashboard.helpers import KPIFinder

PARAMETERS = {}
if os.path.exists(staticfiles_storage.path("MVS_parameters_list.csv")) is True:
    with open(staticfiles_storage.path("MVS_parameters_list.csv"), encoding='utf-8') as csvfile:
        csvreader = csv.reader(csvfile, delimiter=",", quotechar='"')
        for i, row in enumerate(csvreader):
            if i == 0:
                hdr = row
                label_idx = hdr.index("label")
            else:
                label = row[label_idx]
                label = MAP_MVS_EPA.get(label, label)
                PARAMETERS[label] = {}
                for k, v in zip(hdr, row):
                    if k == "sensitivity_analysis":
                        v = bool(int(v))
                    PARAMETERS[label][k] = v

parameters_helper = KPIFinder(param_info_dict=PARAMETERS, unit_header=":Unit:")


# Helper method to clean dict data from empty values
def remove_empty_elements(d):
    def empty(x):
        return x is None or x == {} or x == []

    if not isinstance(d, (dict, list)):
        return d
    elif isinstance(d, list):
        return [v for v in (remove_empty_elements(v) for v in d) if not empty(v)]
    else:
        return {
            k: v
            for k, v in ((k, remove_empty_elements(v)) for k, v in d.items())
            if not empty(v)
        }


# Helper to convert Scenario data to MVS importable json
def format_scenario_for_mvs(scenario_to_convert):
    mvs_request_dto = convert_to_dto(scenario_to_convert)
    dumped_data = json.loads(
        json.dumps(mvs_request_dto.__dict__, default=lambda o: o.__dict__)
    )

    # format the constraints in MVS format directly, thus avoiding the need to maintain MVS-EPA
    # parser in multi-vector-simulator package
    constraint_dict = {}
    for constraint in dumped_data["constraints"]:
        constraint_dict[constraint["label"]] = constraint["value"]
    dumped_data["constraints"] = constraint_dict

    # Remove None values
    return remove_empty_elements(dumped_data)


def sensitivity_analysis_payload(
    variable_parameter_name="",
    variable_parameter_range="",
    variable_parameter_ref_val="",
    output_parameter_names=None,
):
    """format the parameters required to request a sensitivity analysis in a specific JSON"""
    if output_parameter_names is None:
        output_parameter_names = []
    return {
        "sensitivity_analysis_settings": {
            "variable_parameter_name": variable_parameter_name,
            "variable_parameter_range": variable_parameter_range,
            "variable_parameter_ref_val": variable_parameter_ref_val,
            "output_parameter_names": output_parameter_names,
        }
    }


SA_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["server_info", "mvs_version", "id", "status", "results"],
    "properties": {
        "server_info": {"type": "string"},
        "mvs_version": {"type": "string"},
        "id": {"type": "string"},
        "status": {"type": "string"},
        "results": {
            "type": "object",
            "required": ["reference_simulation_id", "sensitivity_analysis_steps"],
            "properties": {
                "reference_simulation_id": {"type": "string"},
                "sensitivity_analysis_steps": {
                    "type": "array",
                    "items": {"type": "object"},
                },
            },
            "additionalProperties": False,
        },
        "ref_sim_id": {"type": "string"},
        "sensitivity_analysis_ids": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}


# Used to proof the json objects stored as text in the db
SA_OUPUT_NAMES_SCHEMA = {"type": "array", "items": {"type": "string"}}


def sa_output_values_schema_generator(output_names):
    return {
        "type": "object",
        "required": output_names,
        "properties": {
            output_name: {
                "type": "object",
                "required": ["value", "path"],
                "properties": {
                    "value": {
                        "oneOf": [
                            {"type": "null"},
                            {
                                "type": "array",
                                "items": {
                                    "anyOf": [{"type": "number"}, {"type": "null"}]
                                },
                            },
                        ]
                    },
                    "path": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ]
                    },
                },
            }
            for output_name in output_names
        },
        "additionalProperties": False,
    }
