import uuid
import numpy as np
import datetime
from django.shortcuts import get_object_or_404
from projects.models import (
    Bus,
    AssetType,
    AssetTemplate,
    Scenario,
    ConnectionLink,
    Asset,
    Project,
    EconomicData,
    COPCalculator,
    Simulation,
    ParameterChangeTracker,
    AssetChangeTracker,
    Timeseries,
)
import json
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db.models import Value
from django.db.models.functions import Concat
from projects.forms import AssetCreateForm, BusForm, StorageForm
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _


# region sent db nodes to js
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)


def handle_bus_form_post(request, scen_id=0, asset_type_name="", asset_uuid=None):
    if asset_uuid:
        existing_bus = get_object_or_404(Bus, pk=asset_uuid)
        form = BusForm(request.POST, asset_type=asset_type_name, instance=existing_bus)
    else:
        form = BusForm(request.POST, asset_type=asset_type_name)

    scenario = get_object_or_404(Scenario, pk=scen_id)

    # make sure the name is not already used by another bus
    form.full_clean()
    qs = Bus.objects.filter(scenario=scenario, name=form.cleaned_data["name"]).exclude(
        pk=asset_uuid
    )
    if qs.exists():
        form.add_error(
            "name", _("There is already a bus with this name in the scenario")
        )
    if form.is_valid():
        bus = form.save(commit=False)
        bus.scenario = scenario
        try:
            bus.pos_x = float(form.data["pos_x"])
            bus.pos_y = float(form.data["pos_y"])
            bus.input_ports = int(float(form.data["input_ports"]))
            bus.output_ports = int(float(form.data["output_ports"]))
        except Exception as ex:
            logger.warning(
                f"Failed to set positioning for bus {bus.name} in scenario: {scen_id}."
            )
        bus.save()
        qs_sim = Simulation.objects.filter(scenario=scenario)
        if not asset_uuid and qs_sim.exists():
            AssetChangeTracker.objects.create(
                simulation=scenario.simulation, name=bus.name, action=1
            )
        return JsonResponse({"success": True, "asset_id": bus.id}, status=200)
    logger.warning(f"The submitted bus has erroneous field values.")

    form_html = get_template("asset/bus_create_form.html")
    return JsonResponse(
        {"success": False, "form_html": form_html.render({"form": form})}, status=422
    )


def track_asset_changes(scenario, param, form, existing_asset, new_value=None):
    if hasattr(existing_asset, param):
        old_value = existing_asset.get_field_value(param)
        if new_value is None:
            new_value = form.cleaned_data.get(param)
        # TODO problem by type of value
        # if a previous change does not exist, we create one instance
        # if it does exist, we update its value, or we discard the change
        # if the assigned value is the same as the old one
        if old_value != new_value:
            qs_param = ParameterChangeTracker.objects.filter(
                simulation=scenario.simulation,
                name=param,
                parameter_category="asset",
                asset=existing_asset,
            )
            if not qs_param.exists():
                if param in (
                    "efficiency",
                    "efficiency_multiple",
                    "energy_price",
                    "feedin_tariff",
                ):
                    kwargs = {"parameter_type": "vector"}
                else:
                    kwargs = {}
                pi = ParameterChangeTracker(
                    simulation=scenario.simulation,
                    name=param,
                    old_value=old_value,
                    new_value=new_value,
                    parameter_category="asset",
                    asset=existing_asset,
                    **kwargs,
                )
                pi.save()
            elif qs_param.count() == 1:
                pi = qs_param.get()
                old_value = pi.old_value
                if pi.parameter_type == "vector":
                    old_value = (old_value, None)

                if pi.name == "input_timeseries":
                    new_value = str(new_value)
                else:
                    old_value = form.fields[pi.name].clean(old_value)

                if new_value == old_value:
                    pi.delete()
                else:
                    qs_param.update(new_value=new_value)
            else:
                raise ValueError(
                    "There are too many parameters which should be singled out"
                )


def handle_storage_unit_form_post(
    request, scen_id=0, asset_type_name="", asset_uuid=None
):

    input_output_mapping = {
        "inputs": request.POST.get("inputs", "").split(","),
        "outputs": request.POST.get("outputs", "").split(","),
    }

    form = StorageForm(
        request.POST,
        request.FILES,
        asset_type=asset_type_name,
        input_output_mapping=input_output_mapping,
    )
    scenario = get_object_or_404(Scenario, id=scen_id)

    # make sure the name is not already used by another asset
    form.full_clean()
    qs = Asset.objects.filter(
        scenario=scenario, name=form.cleaned_data["name"]
    ).exclude(unique_id=asset_uuid)
    if qs.exists():
        form.add_error(
            "name", _("There is already a storage with this name in the scenario")
        )

    if form.is_valid():
        try:
            # First delete all existing associated storage assets from the db
            if asset_uuid:
                existing_asset = get_object_or_404(Asset, unique_id=asset_uuid)
                # existing_asset.delete()  # deletes also automatically all children using models.CASCADE
                ess_asset = existing_asset
                ess_capacity_asset = Asset.objects.get(
                    parent_asset=ess_asset, asset_type__asset_type="capacity"
                )
                ess_charging_power_asset = Asset.objects.get(
                    parent_asset=ess_asset, asset_type__asset_type="charging_power"
                )
                ess_discharging_power_asset = Asset.objects.get(
                    parent_asset=ess_asset, asset_type__asset_type="discharging_power"
                )
                new_name = form.cleaned_data.pop("name", None)
                if new_name is not None:
                    ess_asset.name = new_name
                    ess_capacity_asset.name = f"{ess_asset.name} capacity"
                    ess_charging_power_asset.name = f"{ess_asset.name} input power"
                    ess_discharging_power_asset.name = f"{ess_asset.name} output power"
                    ess_asset.save()
            else:
                # Create the ESS Parent Asset

                ess_asset = Asset.objects.create(
                    name=form.cleaned_data.pop("name"),
                    asset_type=get_object_or_404(
                        AssetType, asset_type=f"{asset_type_name}"
                    ),
                    pos_x=float(form.data["pos_x"]),
                    pos_y=float(form.data["pos_y"]),
                    unique_id=asset_uuid
                    or str(
                        uuid.uuid4()
                    ),  # if exising asset create an asset with the exact same unique_id else generate a new one
                    scenario=scenario,
                )

                # Create the ess charging power
                ess_charging_power_asset = Asset(
                    name=f"{ess_asset.name} input power",
                    asset_type=get_object_or_404(
                        AssetType, asset_type="charging_power"
                    ),
                    scenario=scenario,
                    parent_asset=ess_asset,
                )
                # Create the ess discharging power
                ess_discharging_power_asset = Asset(
                    name=f"{ess_asset.name} output power",
                    asset_type=get_object_or_404(
                        AssetType, asset_type="discharging_power"
                    ),
                    scenario=scenario,
                    parent_asset=ess_asset,
                )
                # Create the ess capacity
                ess_capacity_asset = Asset(
                    name=f"{ess_asset.name} capacity",
                    asset_type=get_object_or_404(AssetType, asset_type="capacity"),
                    scenario=scenario,
                    parent_asset=ess_asset,
                )

            qs_sim = Simulation.objects.filter(scenario=scenario)
            # Populate all subassets
            for param, value in form.cleaned_data.items():

                if asset_uuid and qs_sim.exists():
                    track_asset_changes(
                        scenario, param, form, existing_asset=ess_capacity_asset
                    )
                setattr(ess_capacity_asset, param, value)

                # split efficiency between charge and discharge
                if param == "efficiency":
                    value = np.sqrt(float(value))
                # for the charge and discharge set all costs to 0
                if param in ["capex_fix", "capex_var", "opex_fix"]:
                    value = 0

                # set dispatch price to 0 only for charging power
                if param == "opex_var":
                    if ess_charging_power_asset.has_parameter(param):
                        setattr(ess_charging_power_asset, param, 0)
                else:
                    if ess_charging_power_asset.has_parameter(param):
                        if asset_uuid and qs_sim.exists():
                            track_asset_changes(
                                scenario,
                                param,
                                form,
                                existing_asset=ess_charging_power_asset,
                                new_value=value,
                            )
                        setattr(ess_charging_power_asset, param, value)

                if ess_discharging_power_asset.has_parameter(param):
                    if asset_uuid and qs_sim.exists():
                        track_asset_changes(
                            scenario,
                            param,
                            form,
                            existing_asset=ess_discharging_power_asset,
                            new_value=value,
                        )
                    setattr(ess_discharging_power_asset, param, value)

            ess_capacity_asset.save()
            ess_charging_power_asset.save()
            ess_discharging_power_asset.save()
            if not asset_uuid and qs_sim.exists():
                AssetChangeTracker.objects.create(
                    simulation=scenario.simulation, name=ess_asset.name, action=1
                )
            return JsonResponse(
                {"success": True, "asset_id": ess_asset.unique_id}, status=200
            )
        except Exception as ex:
            logger.warning(
                f"Failed to create storage asset {ess_asset.name} in scenario: {scen_id}."
            )
            return JsonResponse({"success": False, "exception": ex}, status=422)

    logger.warning(f"The submitted asset has erroneous field values.")
    form_html = get_template("asset/storage_asset_create_form.html").render(
        {
            "form": form,
            "templates": get_available_templates(
                asset_type_name, scenario.project, request.user
            ),
        }
    )
    return JsonResponse({"success": False, "form_html": form_html}, status=422)


def handle_asset_form_post(request, scen_id=0, asset_type_name="", asset_uuid=None):

    # collect the information about the connected nodes in the GUI
    input_output_mapping = {
        "inputs": json.loads(request.POST.get("inputs", "[]")),
        "outputs": json.loads(request.POST.get("outputs", "[]")),
    }

    if asset_uuid:
        existing_asset = get_object_or_404(Asset, unique_id=asset_uuid)
        form = AssetCreateForm(
            request.POST,
            request.FILES,
            asset_type=asset_type_name,
            instance=existing_asset,
            scenario_id=scen_id,
            input_output_mapping=input_output_mapping,
        )
    else:
        form = AssetCreateForm(
            request.POST,
            request.FILES,
            asset_type=asset_type_name,
            scenario_id=scen_id,
            input_output_mapping=input_output_mapping,
        )

    asset_type = get_object_or_404(AssetType, asset_type=asset_type_name)
    scenario = get_object_or_404(Scenario, pk=scen_id)

    # make sure the name is not already used by another asset
    form.full_clean()
    qs = Asset.objects.filter(
        scenario=scenario, name=form.cleaned_data["name"]
    ).exclude(unique_id=asset_uuid)
    if qs.exists():
        form.add_error(
            "name", _("There is already an asset with this name in the scenario")
        )

    if form.is_valid():
        qs_sim = Simulation.objects.filter(scenario=scenario)
        if asset_uuid:
            existing_asset = get_object_or_404(Asset, unique_id=asset_uuid)

            if qs_sim.exists():
                for param in form.cleaned_data:
                    track_asset_changes(scenario, param, form, existing_asset)

        asset = form.save(commit=False)
        asset.scenario = scenario
        asset.asset_type = asset_type
        try:
            asset.pos_x = float(form.data["pos_x"])
            asset.pos_y = float(form.data["pos_y"])
        except Exception as ex:
            logger.warning(
                f"Failed to set positioning for asset {asset.name} in scenario: {scen_id}."
            )
        asset.save()
        if not asset_uuid and qs_sim.exists():
            AssetChangeTracker.objects.create(
                simulation=scenario.simulation, name=asset.name, action=1
            )
        # will apply for he
        cop_calculator_id = request.POST.get("copId", "")
        if asset_type_name == "heat_pump" and cop_calculator_id != "":
            existing_cop = get_object_or_404(COPCalculator, id=cop_calculator_id)
            existing_cop.asset = asset
            existing_cop.save()

        return JsonResponse({"success": True, "asset_id": asset.unique_id}, status=200)
    logger.warning(f"The submitted asset has erroneous field values.")

    form_html = get_template("asset/asset_create_form.html").render(
        {
            "form": form,
            "templates": get_available_templates(
                asset_type_name, scenario.project, request.user
            ),
        }
    )
    return JsonResponse({"success": False, "form_html": form_html}, status=422)


def load_scenario_topology_from_db(scen_id):
    bus_nodes_list = db_bus_nodes_to_list(scen_id)
    asset_nodes_list = db_asset_nodes_to_list(scen_id)
    connection_links_list = db_connection_links_to_list(scen_id)
    return {
        "busses": bus_nodes_list,
        "assets": asset_nodes_list,
        "links": connection_links_list,
    }


def db_bus_nodes_to_list(scen_id):
    all_db_busses = Bus.objects.filter(scenario_id=scen_id)
    bus_nodes_list = list()
    for db_bus in all_db_busses:
        db_bus_dict = {
            "name": "bus",
            "pos_x": db_bus.pos_x,
            "pos_y": db_bus.pos_y,
            "input_ports": db_bus.input_ports,
            "output_ports": db_bus.output_ports,
            "data": {
                "name": db_bus.name,
                "bustype": db_bus.type,
                "databaseId": db_bus.id,
                "parent_asset_id": (
                    db_bus.parent_asset_id if db_bus.parent_asset_id else ""
                ),
                "portMapping": {
                    "input_1": ["input_1", db_bus.type],
                    "output_1": ["output_1", db_bus.type],
                },
            },
        }
        bus_nodes_list.append(db_bus_dict)
    return bus_nodes_list


def db_asset_nodes_to_list(scen_id):
    all_db_assets = Asset.objects.filter(scenario_id=scen_id)
    # dont return children assets (i.e. for storage assets)
    no_storage_children_assets = all_db_assets.filter(parent_asset_id=None)
    asset_nodes_list = list()
    for db_asset in no_storage_children_assets:
        asset_type_obj = get_object_or_404(AssetType, pk=db_asset.asset_type_id)
        db_asset_dict = {
            "name": asset_type_obj.asset_type,
            "pos_x": db_asset.pos_x,
            "pos_y": db_asset.pos_y,
            "input_ports": asset_type_obj.n_inputs,
            "output_ports": asset_type_obj.n_outputs,
            "data": {
                "name": db_asset.name,
                "unique_id": db_asset.unique_id,
                "parent_asset_id": (
                    db_asset.parent_asset_id if db_asset.parent_asset_id else ""
                ),
                "portMapping": asset_type_obj.connection_ports,
            },
        }
        asset_nodes_list.append(db_asset_dict)
    return asset_nodes_list


def db_connection_links_to_list(scen_id):
    all_db_connection_links = ConnectionLink.objects.filter(scenario_id=scen_id)
    connections_list = list()
    for db_connection in all_db_connection_links:
        asset_connection_port = db_connection.asset_connection_port
        flow_direction = db_connection.flow_direction
        if asset_connection_port == "no_mapping":
            logging.warning(
                "A connection had no mapping to asset port, probably old scenario, assigning a mapping ..."
            )

            energy_vector = db_connection.bus.type
            asset_type = db_connection.asset.asset_type
            if flow_direction == "A2B":
                asset_connection_port = "output_1"
                if asset_type.n_outputs > 1:
                    qs = asset_type.ports.filter(
                        energy_vector=energy_vector, direction="output"
                    )
                    if qs.exists():
                        asset_connection_port = qs.first().port_key
                    else:
                        logging.warning(
                            f"No output port with energy carrier for {energy_vector} found within the port mapping of the component {db_connection.asset.name}"
                        )

            elif flow_direction == "B2A":
                asset_connection_port = "input_1"
                if asset_type.n_inputs > 1:
                    qs = asset_type.ports.filter(
                        energy_vector=energy_vector, direction="input"
                    )
                    if qs.exists():
                        asset_connection_port = qs.first().port_key
                    else:
                        logging.warning(
                            f"No input port with energy carrier for {energy_vector} found within the port mapping of the component {db_connection.asset.name}"
                        )
            logging.warning(
                f"... the asset {db_connection.asset.name} port to connect to the bus {db_connection.bus.name} was set to {asset_connection_port}"
            )
        db_connection_dict = {
            "bus_id": db_connection.bus_id,
            "asset_id": db_connection.asset.unique_id,
            "flow_direction": flow_direction,
            "bus_connection_port": db_connection.bus_connection_port,
            "asset_connection_port": asset_connection_port,
        }
        connections_list.append(db_connection_dict)
    return connections_list


# endregion db_nodes_to_js


# region Scenario Duplicate
def duplicate_scenario_objects(obj_list, scenario, asset_mapping_dict=None):
    """
    Implement the Node Level (Assets and Busses) duplication of the scenario.
    The functionality is utilized in the scenario search page for each project in the UI of EPA.
    :param obj_list: list of objects to duplicate, can be either bus objects list of assets list
    :param scenario: the scenario under which the assets will be created
    :param asset_mapping_dict: specifically for the case of busses which are part of a storage asset,
    the parent ESS asset id is required. This value is passed with a mapping dict.
    :return: a map dictionary between old and new nodes (assets or busses) ids.
    """

    storage_subasset_list = list()
    mapping_dict = dict()

    for obj in obj_list:
        old_id = obj.id

        if hasattr(obj, "unique_id"):  # i.e. it's an asset
            obj.unique_id = str(uuid.uuid4())
        obj.id = None
        obj.scenario = scenario
        obj.save()
        mapping_dict[old_id] = obj.id
        if obj.parent_asset:
            storage_subasset_list.append(obj)

    # now properly update the parent id of all new storage assets
    for obj in storage_subasset_list:
        obj.parent_asset_id = (
            asset_mapping_dict[obj.parent_asset_id]
            if type(obj) == Bus
            else mapping_dict[obj.parent_asset_id]
        )
        obj.save()

    return mapping_dict


def duplicate_scenario_connections(connections_list, scenario, asset_map, bus_map):
    for connection in connections_list:
        old_asset_id = connection.asset_id
        old_bus_id = connection.bus_id
        connection.id = None
        connection.asset_id = asset_map[old_asset_id]
        connection.bus_id = bus_map[old_bus_id]
        connection.scenario = scenario
        connection.save()


# endregion
def load_project_from_dict(model_data, user=None):
    """Create a new project for a user

    Parameters
    ----------
    model_data: dict
        output produced by the export() method of the Project model
    user: users.models.CustomUser
        the user which loads the scenario
    """
    scenario_set = model_data.pop("scenario_set_data", None)

    model_data["user"] = user
    economic_data = EconomicData(**model_data["economic_data"])
    economic_data.save()
    model_data["economic_data"] = economic_data
    project = Project(**model_data)
    project.save()

    if scenario_set is not None:
        for scenario_data in scenario_set:
            load_scenario_from_dict(scenario_data, user, project)

    return project.id


def load_scenario_from_dict(model_data, user, project=None):
    """Create a new scenario for a user within a given project

    Parameters
    ----------
    model_data: dict
        output produced by the export() method of the Scenario model
    user: users.models.CustomUser
        the user which loads the scenario
    project: projects.models.Project
        bind the scenario to a project if not None.
        If None and 'project' field not in model_data an error is raised
    """
    assets = model_data.pop("assets")
    busses = model_data.pop("busses")

    if project is None:
        if "project" in model_data:
            project_data = model_data.pop("project")
            load_project_from_dict(project_data, user)
        else:
            raise ValueError("Project of a scenario cannot be None")
    else:
        if "project" in model_data:
            project_data = model_data.pop("project")

    scenario = Scenario(**model_data)
    scenario.project = project
    scenario.save()

    # push the children asset at the end of the list to make sure we create the parents first
    assets.sort(key=lambda asset_data: 1 if "parent_asset" in asset_data else 0)

    for asset_data in assets:
        if "parent_asset" in asset_data:
            asset_data["parent_asset"] = Asset.objects.get(
                name=asset_data["parent_asset"], scenario=scenario
            )
        asset_type = asset_data.pop("asset_info")
        asset_data["asset_type"] = AssetType.objects.get(
            asset_type=asset_type["asset_type"]
        )

        COP_parameters = asset_data.pop("COP_parameters", None)

        input_timeseries = asset_data.get("input_timeseries", None)

        if input_timeseries is not None:
            if isinstance(input_timeseries, int):
                input_ts = Timeseries.objects.filter(id=input_timeseries)
                if input_ts.exists():
                    asset_data["input_timeseries"] = input_ts
                else:
                    logger.error(
                        f"No timeseries with id {input_timeseries} has been found for asset {asset_data['name']}, skipping it"
                    )
                    asset_data.pop("input_timeseries")
            elif isinstance(input_timeseries, dict):
                # format the date timestamps as datetime objects
                for k in ("start_date", "end_date"):
                    if k in input_timeseries and input_timeseries[k] is not None:
                        input_timeseries[k] = datetime.datetime.strptime(
                            input_timeseries[k], "%Y-%m-%d %H:%M:%S"
                        )
                input_ts, created = Timeseries.objects.get_or_create(
                    user=user, **input_timeseries
                )
                input_ts.save()
                asset_data["input_timeseries"] = input_ts
            elif isinstance(input_timeseries, str):
                try:
                    input_ts, created = Timeseries.objects.get_or_create(
                        values=json.loads(input_timeseries),
                        user=user,
                        scenario=scenario,
                        ts_type=asset_type["mvs_type"],
                        name=f"{asset_data['name']}_ts",
                    )
                    asset_data["input_timeseries"] = input_ts
                except json.decoder.JSONDecodeError:
                    pass
            else:
                logger.error(
                    f"The timeseries for asset {asset_data['name']} is neither an existing Timeseries instance's id nor a dict with Timeserie's attributes"
                )
                asset_data.pop("input_timeseries")

        asset = Asset(**asset_data)
        asset.scenario = scenario
        asset.save()

        if COP_parameters is not None:
            COP_parameters["asset"] = asset
            COP_parameters["scenario"] = scenario
            cop_parameters = COPCalculator(**COP_parameters)
            cop_parameters.save()

    for bus_data in busses:
        bus_inputs = bus_data.pop("inputs")
        bus_outputs = bus_data.pop("outputs")
        bus = Bus(**bus_data)
        bus.scenario = scenario
        bus.save()
        for link_data in bus_inputs + bus_outputs:
            asset_name = link_data.pop("asset")
            new_connection = ConnectionLink(**link_data)
            new_connection.scenario = scenario
            new_connection.bus = bus
            new_connection.asset = scenario.asset_set.get(name=asset_name)
            new_connection.save()

    return scenario.id


class NodeObject:
    def __init__(self, node_data=None):
        self.name = node_data["name"]  # asset type name : e.g. bus, pv_plant, etc
        self.data = node_data["data"]  # name: eg. demand_01, parent_asset_id, unique_id
        self.db_obj_id = self.uuid_2_db_id(node_data)
        self.group_id = (
            node_data["data"]["parent_asset_id"]
            if "parent_asset_id" in node_data["data"]
            else None
        )
        self.node_obj_type = "bus" if self.name == "bus" else "asset"
        self.inputs = node_data["inputs"]
        self.outputs = node_data["outputs"]
        self.pos_x = node_data["pos_x"]
        self.pos_y = node_data["pos_y"]

    def __str__(self):
        return "\n".join(
            [
                "name: " + self.name,
                "db_id: " + str(self.db_obj_id),
                "group_id: " + str(self.group_id),
                "node type: " + str(self.node_obj_type),
            ]
        )

    @staticmethod
    def uuid_2_db_id(data):
        if "db_id" in data and data["db_id"]:
            if isinstance(data["db_id"], int):
                return data["db_id"]
            elif isinstance(data["db_id"], str):
                asset = Asset.objects.filter(unique_id=data["db_id"]).first()
                return asset.id if asset else None
            else:
                return None
        else:
            return None

    def create_connection_links(self, scen_id):
        """Create connections between a bus and the assets connected as inputs and outputs

        Parameters
        ----------
        scen_id

        Returns
        -------

        """
        # TODO here with the exception of load scenario from dict is the only place where ConnectionLink are created
        if self.node_obj_type == "bus":
            bus_obj = get_object_or_404(Bus, pk=self.db_obj_id)
            for asset_connection in self.outputs:
                if isinstance(asset_connection["to"]["id"], str):  # i.e. unique_id
                    ConnectionLink.objects.create(
                        bus=bus_obj,
                        asset=get_object_or_404(
                            Asset, unique_id=asset_connection["to"]["id"]
                        ),
                        flow_direction="B2A",
                        bus_connection_port=asset_connection["port"],
                        asset_connection_port=asset_connection["to"]["port"],
                        scenario=get_object_or_404(Scenario, pk=scen_id),
                    )
            for asset_connection in self.inputs:
                if isinstance(asset_connection["to"]["id"], str):  # i.e. unique_id
                    ConnectionLink.objects.create(
                        bus=bus_obj,
                        asset=get_object_or_404(
                            Asset, unique_id=asset_connection["to"]["id"]
                        ),
                        flow_direction="A2B",
                        bus_connection_port=asset_connection["port"],
                        asset_connection_port=asset_connection["to"]["port"],
                        scenario=get_object_or_404(Scenario, pk=scen_id),
                    )
        else:
            logger.debug(
                f"The node with asset type {self.name} is not a bus, therefore no connection will be created"
            )
        logger.debug(
            f"Nodes interconnection links for {self.name} '{self.data['name']}' were created successfully in scenario: {scen_id}."
        )

    def assign_asset_to_proper_group(self, node_to_db_mapping):
        """Seems to be unused here"""
        try:
            if self.node_obj_type == "asset":
                asset = get_object_or_404(Asset, pk=self.db_obj_id)
                asset.parent_asset_id = (
                    node_to_db_mapping[self.group_id]["db_obj_id"]
                    if self.group_id
                    else None
                )
                asset.save()
            else:  # i.e. "bus"
                bus = get_object_or_404(Bus, pk=self.db_obj_id)
                bus.parent_asset_id = (
                    node_to_db_mapping[self.group_id]["db_obj_id"]
                    if self.group_id
                    else None
                )
                bus.save()
        except KeyError:
            return {"success": False, "obj_type": self.node_obj_type}
        except ValidationError:
            return {"success": False, "obj_type": self.node_obj_type}
        else:
            return {"success": True, "obj_type": self.node_obj_type}


def update_deleted_objects_from_database(scenario_id, topo_node_list):
    """Delete Database Scenario Related Objects which are not in the topology before inserting or updating data."""
    all_scenario_assets = Asset.objects.filter(scenario_id=scenario_id)
    # dont include storage unit children assets
    scenario_assets_ids_excluding_storage_children = all_scenario_assets.filter(
        parent_asset=None
    ).values_list("id", flat=True)
    all_scenario_busses_ids = Bus.objects.filter(scenario_id=scenario_id).values_list(
        "id", flat=True
    )

    # lists the DB ids of the assets and busses coming from the topology
    topology_asset_ids = list()
    topology_busses_ids = list()
    # TODO fix this complicated logic with duplicate od DB with NodeObject ...
    asset_node_positions = {}
    bus_node_positions = {}
    for node in topo_node_list:
        if node.name != "bus" and node.db_obj_id:
            topology_asset_ids.append(node.db_obj_id)
            asset_node_positions[node.db_obj_id] = dict(
                pos_x=node.pos_x, pos_y=node.pos_y
            )
        elif node.name == "bus" and node.db_obj_id:
            topology_busses_ids.append(node.db_obj_id)
            bus_node_positions[node.db_obj_id] = dict(
                pos_x=node.pos_x, pos_y=node.pos_y
            )

    scenario = get_object_or_404(Scenario, id=scenario_id)
    qs_sim = Simulation.objects.filter(scenario=scenario)

    # deletes asset or bus which DB id is not in the topology anymore (was removed by user)
    for asset_id in scenario_assets_ids_excluding_storage_children:

        qs = Asset.objects.filter(id=asset_id)
        if asset_id not in topology_asset_ids:
            logger.debug(
                f"Deleting asset {asset_id} of scenario {scenario_id} which was removed from the topology by the user."
            )
            if qs_sim.exists():
                for name in qs.values_list("name", flat=True):
                    # TODO export asset dto to be able to undo the changes
                    AssetChangeTracker.objects.create(
                        simulation=scenario.simulation, name=name, action=0
                    )
            qs.delete()

        else:
            qs.update(**asset_node_positions[asset_id])

    for bus_id in all_scenario_busses_ids:

        qs = Bus.objects.filter(id=bus_id)
        if bus_id not in topology_busses_ids:
            logger.debug(
                f"Deleting bus {bus_id} of scenario {scenario_id} which was removed from the topology by the user."
            )
            if qs_sim.exists():
                for name in qs.values_list("name", flat=True):
                    # TODO export asset dto to be able to undo the changes
                    AssetChangeTracker.objects.create(
                        simulation=scenario.simulation, name=name, action=0
                    )
            qs.delete()
        else:
            qs.update(**bus_node_positions[bus_id])


def create_ESS_objects(all_ess_assets_node_list, scen_id):
    ess_obj_list = list()

    charging_power_asset_id = AssetType.objects.get(asset_type="charging_power")
    discharging_power_asset_id = AssetType.objects.get(asset_type="discharging_power")
    capacity_asset_id = AssetType.objects.get(asset_type="capacity")

    scenario_connection_links = ConnectionLink.objects.filter(scenario_id=scen_id)
    cap_scenario_connection_links = scenario_connection_links.filter(
        asset__asset_type=capacity_asset_id
    )
    charge_scenario_connection_links = scenario_connection_links.filter(
        asset__asset_type=charging_power_asset_id
    )
    discharge_scenario_connection_links = scenario_connection_links.filter(
        asset__asset_type=discharging_power_asset_id
    )

    for asset in all_ess_assets_node_list:
        if asset.name == "capacity":
            # check if there is a connection link to a bus
            pass


def get_available_templates(asset_type_name, project, user):
    # collect available templates
    asset_templates = AssetTemplate.objects.filter(
        asset_type__asset_type=asset_type_name
    ).order_by("created_ts")
    # project templates
    project_templates = asset_templates.filter(
        visibility="project", project=project
    ).annotate(display_name=Concat("name", Value(" (prj)")))
    # account templates
    account_templates = asset_templates.filter(
        visibility="account", created_by=user
    ).annotate(display_name=Concat("name", Value(" (acc)")))
    # global templates
    global_templates = asset_templates.filter(visibility="global").annotate(
        display_name=Concat("name", Value(" (std)"))
    )
    return AssetTemplate.objects.none().union(
        project_templates, account_templates, global_templates
    )
