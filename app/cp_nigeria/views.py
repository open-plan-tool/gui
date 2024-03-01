import io

from django.contrib.auth.decorators import login_required
import json
import logging
import pandas as pd
import os
import base64
from django.http import JsonResponse
from jsonview.decorators import json_view
from django.utils.translation import gettext_lazy as _
from django.shortcuts import *
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db.models import Q, F, Avg, Max
from epa.settings import MVS_GET_URL, MVS_LP_FILE_URL
from .forms import *
from .helpers import *
from business_model.forms import *
from projects.requests import fetch_mvs_simulation_results
from projects.models import *
from projects.views import project_duplicate, project_delete
from business_model.models import *
from cp_nigeria.models import ConsumerGroup
from cp_nigeria.helpers import ReportHandler
from projects.forms import UploadFileForm, ProjectShareForm, ProjectRevokeForm, UseCaseForm
from projects.services import RenewableNinjas
from projects.constants import DONE, PENDING, ERROR
from projects.views import request_mvs_simulation, simulation_cancel
from business_model.helpers import B_MODELS
from dashboard.models import KPIScalarResults, KPICostsMatrixResults, FancyResults
from dashboard.helpers import KPI_PARAMETERS

logger = logging.getLogger(__name__)


STEP_MAPPING = {
    "choose_location": 1,
    "grid_conditions": 2,
    "demand_profile": 3,
    "scenario_setup": 4,
    "business_model": 5,
    "economic_params": 6,
    "simulation": 7,
    "outputs": 8,
}

CPN_STEP_VERBOSE = {
    "choose_location": _("Choose location"),
    "grid_conditions": _("Grid conditions"),
    "demand_profile": _("Demand load profile selection"),
    "scenario_setup": _("Supply system setup"),
    "economic_params": _("Economic parameters"),
    "simulation": _("Simulation"),
    "business_model": _("Business Model"),
    "outputs": _("Outputs"),
}

# sorts the step names based on the order defined in STEP_MAPPING (for ribbon)
CPN_STEP_VERBOSE = [CPN_STEP_VERBOSE[k] for k, v in sorted(STEP_MAPPING.items(), key=lambda x: x[1])]


@require_http_methods(["GET"])
def home_cpn(request):
    return render(request, "cp_nigeria/index_cpn.html")


@login_required
@require_http_methods(["GET"])
def projects_list_cpn(request, proj_id=None):
    combined_projects_list = (
        Project.objects.filter(Q(user=request.user) | Q(viewers__user__email=request.user.email))
        .distinct()
        .order_by("date_created")
        .reverse()
    )
    # combined_projects_list = Project.objects.filter(
    #     (Q(user=request.user) | Q(viewers__user=request.user)) & Q(country="NIGERIA")
    # ).distinct()

    scenario_upload_form = UploadFileForm(labels=dict(name=_("New scenario name"), file=_("Scenario file")))
    project_upload_form = UploadFileForm(labels=dict(name=_("New project name"), file=_("Project file")))
    project_share_form = ProjectShareForm()
    project_revoke_form = ProjectRevokeForm(proj_id=proj_id)
    usecase_form = UseCaseForm(usecase_qs=UseCase.objects.all(), usecase_url=reverse("usecase_search"))

    return render(
        request,
        "cp_nigeria/project_display.html",
        {
            "project_list": combined_projects_list,
            "proj_id": proj_id,
            "scenario_upload_form": scenario_upload_form,
            "project_upload_form": project_upload_form,
            "project_share_form": project_share_form,
            "project_revoke_form": project_revoke_form,
            "usecase_form": usecase_form,
            "translated_text": {
                "showScenarioText": _("Show scenarios"),
                "hideScenarioText": _("Hide scenarios"),
            },
        },
    )


@login_required
@require_http_methods(["POST"])
def cpn_project_delete(request, proj_id):
    project_delete(request, proj_id)
    return HttpResponseRedirect(reverse("projects_list_cpn"))


@login_required
@require_http_methods(["POST"])
def cpn_project_duplicate(request, proj_id):
    """Duplicates the selected project along with its associated scenarios"""
    project = get_object_or_404(Project, pk=proj_id)
    answer = project_duplicate(request, proj_id)
    new_proj_id = answer.url.split("/")[-1]
    options, created = Options.objects.get_or_create(project__id=proj_id)
    if created is False:
        options.pk = None
        options.project = Project.objects.get(pk=new_proj_id)
        options.save()
    cg_qs = ConsumerGroup.objects.filter(project__id=proj_id)
    for cg in cg_qs:
        cg.pk = None
        cg.project = Project.objects.get(pk=new_proj_id)
        cg.save()
    bm, created = BusinessModel.objects.get_or_create(scenario=project.scenario)
    if created is False:
        bm.pk = None
        bm.scenario = Project.objects.get(pk=new_proj_id).scenario
        bm.save()
    ed, created = EquityData.objects.get_or_create(scenario=project.scenario)
    if created is False:
        ed.pk = None
        ed.scenario = Project.objects.get(pk=new_proj_id).scenario
        ed.save()
    return HttpResponseRedirect(reverse("projects_list_cpn", args=[new_proj_id]))


@login_required
@require_http_methods(["GET", "POST"])
def cpn_grid_conditions(request, proj_id, scen_id, step_id=STEP_MAPPING["grid_conditions"]):
    # TODO in the future, pre-load the questions instead of written out in the template
    project = get_object_or_404(Project, id=proj_id)

    if (project.user != request.user) and (
        project.viewers.filter(user__email=request.user.email, share_rights="edit").exists() is False
    ):
        raise PermissionDenied

    page_information = "Please include information about your connection to the grid."

    bm_qs = BusinessModel.objects.filter(scenario=project.scenario)
    if bm_qs.exists():
        grid_condition = bm_qs.get().grid_condition
    else:
        grid_condition = ""

    return render(
        request,
        "cp_nigeria/steps/business_model_tree.html",
        {
            "proj_id": proj_id,
            "proj_name": project.name,
            "grid_condition": grid_condition,
            "step_id": step_id,
            "scen_id": scen_id,
            "step_list": CPN_STEP_VERBOSE,
            "page_information": page_information,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def cpn_scenario_create(request, proj_id=None, step_id=STEP_MAPPING["choose_location"]):
    qs_project = Project.objects.filter(id=proj_id)

    proj_name = ""
    if qs_project.exists():
        project = qs_project.get()
        if (project.user != request.user) and (
            project.viewers.filter(user__email=request.user.email, share_rights="edit").exists() is False
        ):
            raise PermissionDenied

    else:
        project = None

    if request.method == "POST":
        if project is not None:
            form = ProjectForm(request.POST, instance=project)
            economic_data = EconomicProjectForm(request.POST, instance=project.economic_data)
        else:
            form = ProjectForm(request.POST)
            economic_data = EconomicProjectForm(request.POST)
        if form.is_valid() and economic_data.is_valid():
            economic_data = economic_data.save()
            project = form.save(user=request.user, commit=False)
            project.economic_data = economic_data
            project.save()

            options, _ = Options.objects.get_or_create(project=project)
            options.community = form.cleaned_data["community"]
            options.save()

            return HttpResponseRedirect(reverse("cpn_steps", args=[project.id, step_id + 1]))

    elif request.method == "GET":
        if project is not None:
            scenario = Scenario.objects.filter(project=project).last()
            form = ProjectForm(
                instance=project,
                initial={"start_date": scenario.start_date, "duration": project.economic_data.duration},
            )
            economic_data = EconomicProjectForm(instance=project.economic_data)
            qs_options = Options.objects.filter(project=project)
            if qs_options.exists():
                form["community"].initial = qs_options.get(project=project).community

        else:
            form = ProjectForm()
            economic_data = EconomicProjectForm()
    page_information = "Please input basic project information, such as name, location and duration. You can input geographical data by clicking on the desired project location on the map."
    if project is not None:
        proj_name = project.name
    return render(
        request,
        "cp_nigeria/steps/scenario_create.html",
        {
            "form": form,
            "economic_data": economic_data,
            "proj_id": proj_id,
            "proj_name": proj_name,
            "step_id": step_id,
            "step_list": CPN_STEP_VERBOSE,
            "page_information": page_information,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def cpn_demand_params(request, proj_id, step_id=STEP_MAPPING["demand_profile"]):
    project = get_object_or_404(Project, id=proj_id)

    if (project.user != request.user) and (
        project.viewers.filter(user__email=request.user.email, share_rights="edit").exists() is False
    ):
        raise PermissionDenied

    options = get_object_or_404(Options, project=project)

    # TODO change DB default value to 1
    # TODO include the possibility to display the "expected_consumer_increase", "expected_demand_increase" fields
    # with option advanced_view set by user choice
    if request.method == "POST":
        qs_demand = Asset.objects.filter(
            scenario=project.scenario, asset_type__asset_type="demand", name="electricity_demand"
        )

        shs_form = SHSTiersForm(request.POST)
        if shs_form.is_valid():
            options.shs_threshold = shs_form.cleaned_data["shs_threshold"]
            options.save()

        formset_qs = ConsumerGroup.objects.filter(project=project)

        formset = ConsumerGroupFormSet(request.POST, queryset=formset_qs, initial=[{"number_consumers": 1}])

        for form in formset:
            # set timeseries queryset so form doesn't throw a validation error
            if f"{form.prefix}-consumer_type" in form.data:
                try:
                    consumer_type_id = int(form.data.get(f"{form.prefix}-consumer_type"))
                    form.fields["timeseries"].queryset = DemandTimeseries.objects.filter(
                        consumer_type_id=consumer_type_id
                    )
                except (ValueError, TypeError):
                    pass
            if form.is_valid():
                # update consumer group if already in database and create new entry if not
                if len(form.cleaned_data) == 0:
                    continue
                try:
                    group_id = form.cleaned_data["id"].id
                    consumer_group = ConsumerGroup.objects.get(id=group_id)
                    if form.cleaned_data["DELETE"] is True:
                        consumer_group.delete()
                    else:
                        for field_name, field_value in form.cleaned_data.items():
                            if field_name == "id":
                                continue
                            setattr(consumer_group, field_name, field_value)
                            consumer_group.save()

                # AttributeError gets thrown when form id field is empty -> not yet in db
                except AttributeError:
                    if form.cleaned_data["DELETE"] is True:
                        continue

                    consumer_group = form.save(commit=False)
                    consumer_group.project = project
                    consumer_group.save()

        if formset.is_valid():
            # update demand if exists
            if qs_demand.exists():
                total_demand = get_aggregated_demand(project)
                demand = qs_demand.get()
                demand.input_timeseries = json.dumps(total_demand)
                demand.save()

            step_id = STEP_MAPPING["demand_profile"] + 1
            return HttpResponseRedirect(reverse("cpn_steps", args=[proj_id, step_id]))

    elif request.method == "GET":
        formset_qs = ConsumerGroup.objects.filter(project=proj_id)
        shs_form = SHSTiersForm(initial={"shs_threshold": options.shs_threshold})

        if options.community is not None and not formset_qs.exists():
            cg_qs = ConsumerGroup.objects.filter(community=options.community)
            new_cgs = []
            for cg in cg_qs:
                cg.pk = None
                cg.community = None
                cg.project = project
                new_cgs.append(cg)

            ConsumerGroup.objects.bulk_create(new_cgs)
            formset_qs = ConsumerGroup.objects.filter(project=proj_id)

        formset = ConsumerGroupFormSet(queryset=formset_qs, initial=[{"number_consumers": 1}])

        for form, obj in zip(formset, formset_qs):
            for field in form.fields:
                if field != "DELETE":
                    form[field].initial = getattr(obj, field)
                if field == "timeseries":
                    consumer_type_id = getattr(obj, "consumer_type").id
                    form.fields[field].queryset = DemandTimeseries.objects.filter(consumer_type_id=consumer_type_id)

    page_information = "Please input user group data. This includes user type information about households, enterprises and facilities and predicted energy demand tiers as collected from survey data or available information about the community."
    household_tiers = json.dumps([tier[1] for tier in HOUSEHOLD_TIERS])

    return render(
        request,
        "cp_nigeria/steps/scenario_demand.html",
        {
            "formset": formset,
            "shs_form": shs_form,
            "proj_id": proj_id,
            "proj_name": project.name,
            "step_id": step_id,
            "scen_id": project.scenario.id,
            "step_list": CPN_STEP_VERBOSE,
            "page_information": page_information,
            "household_tiers": household_tiers,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def cpn_scenario(request, proj_id, step_id=STEP_MAPPING["scenario_setup"]):
    project = get_object_or_404(Project, id=proj_id)

    if (project.user != request.user) and (
        project.viewers.filter(user__email=request.user.email, share_rights="edit").exists() is False
    ):
        raise PermissionDenied

    scenario = project.scenario

    if request.method == "GET":
        page_information = "Select the energy system components you would like to include in the simulation. The system can be comprised of a diesel generator, a PV-system, and a battery system (storage) in any combination."

        qs_options = Options.objects.filter(project=project)
        if qs_options.exists():
            options = qs_options.get()
            es_schema_name = options.schema_name
            grid_availability = options.main_grid

        else:
            es_schema_name = None
            grid_availability = False

        total_demand, peak_demand, daily_demand = get_demand_indicators(project)

        context = {
            "proj_id": proj_id,
            "proj_name": project.name,
            "step_id": step_id,
            "scen_id": scenario.id,
            "step_list": CPN_STEP_VERBOSE,
            "es_assets": [],
            "es_schema_name": es_schema_name,
            "page_information": page_information,
            "grid_availability": grid_availability,
            "peak_demand": peak_demand,
            "daily_demand": daily_demand,
        }

        asset_type_name = "bess"

        qs = Asset.objects.filter(scenario=scenario.id, asset_type__asset_type=asset_type_name)

        if qs.exists():
            existing_ess_asset = qs.get()
            ess_asset_children = Asset.objects.filter(parent_asset=existing_ess_asset.id)
            ess_capacity_asset = ess_asset_children.get(asset_type__asset_type="capacity")
            ess_charging_power_asset = ess_asset_children.get(asset_type__asset_type="charging_power")
            ess_discharging_power_asset = ess_asset_children.get(asset_type__asset_type="discharging_power")
            # also get all child assets
            context["es_assets"].append(asset_type_name)
            context["form_bess"] = BessForm(
                proj_id=project.id,
                instance=ess_capacity_asset,
            )
        else:
            context["form_bess"] = BessForm(proj_id=project.id)

        for asset_type_name, form in zip(["dso", "pv_plant", "diesel_generator"], [MainGridForm, PVForm, DieselForm]):
            qs = Asset.objects.filter(scenario=scenario.id, asset_type__asset_type=asset_type_name)

            if qs.exists():
                existing_asset = qs.get()
                context["es_assets"].append(asset_type_name)
                context[f"form_{asset_type_name}"] = form(instance=existing_asset, proj_id=project.id)

            else:
                context[f"form_{asset_type_name}"] = form(proj_id=project.id)

        return render(request, "cp_nigeria/steps/scenario_components.html", context)

    if request.method == "POST":
        asset_forms = dict(bess=BessForm, pv_plant=PVForm, diesel_generator=DieselForm, dso=MainGridForm)
        # collect the assets selected by the user
        user_assets = request.POST.getlist("es_choice", [])

        grid_availability = request.POST.get("grid_availability", "off")
        grid_availability = True if grid_availability == "on" else False

        # Options
        options, _ = Options.objects.get_or_create(project=project)
        options.user_case = json.dumps(user_assets)
        options.main_grid = grid_availability
        options.save()

        qs = Bus.objects.filter(scenario=scenario, type="Electricity")

        if qs.filter(Q(name__contains="ac") & Q(name__contains="dc")).exists():
            ac_bus = qs.get(name="ac_bus")
            dc_bus = qs.get(name="dc_bus")
        else:
            qs.delete()
            ac_bus = Bus(type="Electricity", scenario=scenario, name="ac_bus")
            dc_bus = Bus(type="Electricity", scenario=scenario, name="dc_bus")

        ac_bus.pos_x = 700
        ac_bus.pos_y = 100
        dc_bus.pos_x = 700
        dc_bus.pos_y = 450
        ac_bus.save()
        dc_bus.save()

        # Delete potential existing rectifiers
        Asset.objects.filter(
            scenario=scenario, asset_type=AssetType.objects.get(asset_type="transformer_station_in"), name="rectifier"
        ).delete()

        inverter, created = Asset.objects.get_or_create(
            scenario=scenario,
            asset_type=AssetType.objects.get(asset_type="transformer_station_in"),
            name="inverter",
        )
        if created is True:
            inverter.age_installed = 0
            inverter.installed_capacity = 0
            inverter.capex_fix = 0
            inverter.capex_var = 415
            inverter.opex_fix = 8.3
            inverter.opex_var = 0
            inverter.lifetime = project.economic_data.duration
            inverter.optimize_cap = True
            inverter.efficiency = 0.95

        inverter.pos_x = dc_bus.pos_x + 175
        inverter.pos_y = dc_bus.pos_y
        inverter.save()

        ConnectionLink.objects.get_or_create(
            bus=dc_bus, bus_connection_port="output_1", asset=inverter, flow_direction="B2A", scenario=scenario
        )
        ConnectionLink.objects.get_or_create(
            bus=ac_bus, bus_connection_port="input_1", asset=inverter, flow_direction="A2B", scenario=scenario
        )

        asset_type_name = "demand"

        demand, created = Asset.objects.get_or_create(
            scenario=scenario, asset_type=AssetType.objects.get(asset_type=asset_type_name), name="electricity_demand"
        )
        demand.pos_x = 900
        demand.pos_y = ac_bus.pos_y
        demand.save()
        if created is True:
            total_demand = get_aggregated_demand(project)
            demand.input_timeseries = json.dumps(total_demand)
            demand.save()

        peak_demand = round(np.array(json.loads(demand.input_timeseries)).max(), 1)

        ConnectionLink.objects.get_or_create(
            bus=ac_bus, bus_connection_port="output_1", asset=demand, flow_direction="B2A", scenario=scenario
        )

        for i, asset_name in enumerate(user_assets):
            qs = Asset.objects.filter(
                scenario=scenario, asset_type__asset_type=asset_name if asset_name != "bess" else "capacity"
            )
            if qs.exists():
                form = asset_forms[asset_name](request.POST, instance=qs.first(), proj_id=project.id)

            else:
                form = asset_forms[asset_name](request.POST, proj_id=project.id)

            if form.is_valid():
                asset_type = get_object_or_404(AssetType, asset_type=asset_name)

                asset = form.save(commit=False)
                # TODO the form save should do some specific things to save the storage correctly
                asset.scenario = scenario

                if asset_name != "bess":
                    asset.asset_type = asset_type
                else:
                    asset.asset_type = get_object_or_404(AssetType, asset_type="capacity")

                if asset_name == "diesel_generator":
                    asset.pos_x = 400
                    asset.pos_y = 200

                    # set the maximum diesel generator capacity to the peak demand
                    asset.maximum_capacity = peak_demand
                    asset.save()

                    bus_diesel, _ = Bus.objects.get_or_create(type="Gas", scenario=scenario, name="diesel_bus")
                    bus_diesel.pos_x = 225
                    bus_diesel.pos_y = asset.pos_y
                    bus_diesel.save()

                    equity_data_qs = EquityData.objects.filter(scenario=scenario)
                    if equity_data_qs.exists():
                        equity_data = equity_data_qs.get()
                        diesel_price_kWh = equity_data.compute_average_fuel_price(
                            initial_fuel_price=asset.opex_var_extra, project_duration=project.economic_data.duration
                        )
                    else:
                        diesel_price_kWh = asset.opex_var_extra

                    dso_diesel, created = Asset.objects.get_or_create(
                        renewable_share=0,
                        peak_demand_pricing_period=1,
                        peak_demand_pricing=0,
                        scenario=scenario,
                        asset_type=AssetType.objects.get(asset_type="gas_dso"),
                        name="diesel_fuel",
                    )
                    dso_diesel.feedin_tariff = 0
                    dso_diesel.energy_price = diesel_price_kWh
                    dso_diesel.pos_x = 50
                    dso_diesel.pos_y = asset.pos_y
                    dso_diesel.save()
                    # connect the diesel generator to the diesel bus and the electricity bus
                    ConnectionLink.objects.get_or_create(
                        bus=bus_diesel,
                        bus_connection_port="input_1",
                        asset=dso_diesel,
                        flow_direction="A2B",
                        scenario=scenario,
                    )
                    ConnectionLink.objects.get_or_create(
                        bus=bus_diesel,
                        bus_connection_port="output_1",
                        asset=asset,
                        flow_direction="B2A",
                        scenario=scenario,
                    )

                    # connect the asset to the electricity bus
                    ConnectionLink.objects.get_or_create(
                        bus=ac_bus, bus_connection_port="input_1", asset=asset, flow_direction="A2B", scenario=scenario
                    )

                if asset_name == "dso":
                    asset.pos_x = 50
                    asset.pos_y = 50
                    asset.save()

                    # delete existing direct connection from dso to ac_bus
                    ConnectionLink.objects.filter(
                        bus=ac_bus,
                        bus_connection_port="input_1",
                        asset=asset,
                        flow_direction="A2B",
                        scenario=scenario,
                    ).delete()

                    bus_dso, _ = Bus.objects.get_or_create(type="Electricity", scenario=scenario, name="dso_bus")
                    bus_dso.pos_x = 225
                    bus_dso.pos_y = asset.pos_y
                    bus_dso.save()

                    dso_availability, created = Asset.objects.get_or_create(
                        scenario=scenario,
                        asset_type=AssetType.objects.get(asset_type="transformer_station_in"),
                        name="dso_availability",
                    )
                    if created is True:
                        dso_availability.age_installed = 0
                        dso_availability.installed_capacity = 0
                        # 300 USD * 774 --> NGN
                        dso_availability.capex_fix = 232200 * peak_demand
                        dso_availability.capex_var = 0
                        dso_availability.opex_fix = 0
                        dso_availability.opex_var = 0
                        dso_availability.lifetime = 100
                        dso_availability.optimize_cap = True
                        dso_availability.efficiency = 1

                    if grid_availability is True:
                        pass  # TODO here affect the efficiency based on user input

                    dso_availability.pos_x = 400
                    dso_availability.pos_y = asset.pos_y
                    dso_availability.save()

                    # connect the asset to the electricity bus
                    ConnectionLink.objects.get_or_create(
                        bus=ac_bus,
                        bus_connection_port="input_1",
                        asset=dso_availability,
                        flow_direction="A2B",
                        scenario=scenario,
                    )
                    ConnectionLink.objects.get_or_create(
                        bus=bus_dso,
                        bus_connection_port="output_1",
                        asset=dso_availability,
                        flow_direction="B2A",
                        scenario=scenario,
                    )
                    ConnectionLink.objects.get_or_create(
                        bus=bus_dso,
                        bus_connection_port="input_1",
                        asset=asset,
                        flow_direction="A2B",
                        scenario=scenario,
                    )
                    # else:
                    #     # delete potential dso availability transformer and bus
                    #     bus_dso = Bus.objects.filter(scenario=scenario, name="dso_bus").delete()
                    #     dso_availability = Asset.objects.filter(
                    #         scenario=scenario,
                    #         name="dso_availability",
                    #     ).delete()
                    #     ConnectionLink.objects.get_or_create(
                    #         bus=ac_bus,
                    #         bus_connection_port="input_1",
                    #         asset=asset,
                    #         flow_direction="A2B",
                    #         scenario=scenario,
                    #     )

                if asset_name == "pv_plant":
                    asset.pos_x = 350
                    asset.pos_y = 350
                    asset.save()
                    if options.community is not None:
                        community = options.community
                        asset.input_timeseries = community.pv_timeseries.values
                        asset.save()
                    else:
                        if asset.input_timeseries == []:
                            qs_pv = Timeseries.objects.filter(scenario=project.scenario)
                            if qs_pv.exists():
                                values = qs_pv.get().values
                            else:
                                values = get_pv_output(project.id)
                            asset.input_timeseries = json.dumps(values)
                            asset.save()

                    # connect the asset to the electricity bus
                    ConnectionLink.objects.get_or_create(
                        bus=dc_bus, bus_connection_port="input_1", asset=asset, flow_direction="A2B", scenario=scenario
                    )

                if asset_name == "bess":
                    ess_asset, _ = Asset.objects.get_or_create(
                        name="battery",
                        asset_type=get_object_or_404(AssetType, asset_type=asset_name),
                        scenario=scenario,
                    )
                    qs_ac = Asset.objects.filter(parent_asset=asset)
                    # Create the ess charging power
                    ess_charging_power_asset, _ = Asset.objects.get_or_create(
                        name=f"{ess_asset.name} input power",
                        asset_type=get_object_or_404(AssetType, asset_type="charging_power"),
                        scenario=scenario,
                        parent_asset=ess_asset,
                    )
                    # Create the ess discharging power
                    ess_discharging_power_asset, _ = Asset.objects.get_or_create(
                        name=f"{ess_asset.name} output power",
                        asset_type=get_object_or_404(AssetType, asset_type="discharging_power"),
                        scenario=scenario,
                        parent_asset=ess_asset,
                    )
                    # Create the ess capacity
                    ess_capacity_asset = asset
                    ess_capacity_asset.name = f"{ess_asset.name} capacity"
                    ess_capacity_asset.parent_asset = ess_asset
                    # remove name property from the form
                    form.cleaned_data.pop("name", None)
                    # Populate all subassets properties
                    for param, value in form.cleaned_data.items():
                        setattr(ess_capacity_asset, param, value)

                        # split efficiency between charge and discharge
                        if param == "efficiency":
                            value = np.sqrt(float(value))
                        # for the charge and discharge set all costs to 0
                        if param in ["capex_fix", "capex_var", "opex_fix"]:
                            value = 0

                        if ess_discharging_power_asset.has_parameter(param):
                            setattr(ess_discharging_power_asset, param, value)

                        # set dispatch price to 0 only for charging power
                        if param == "opex_var":
                            value = 0
                        if ess_charging_power_asset.has_parameter(param):
                            setattr(ess_charging_power_asset, param, value)

                    ess_capacity_asset.save()
                    ess_charging_power_asset.save()
                    ess_discharging_power_asset.save()

                    ess_asset.pos_x = 700
                    ess_asset.pos_y = dc_bus.pos_y + 150
                    ess_asset.save()

                    # connect the battery to the electricity bus
                    ConnectionLink.objects.get_or_create(
                        bus=dc_bus,
                        bus_connection_port="input_1",
                        asset=ess_asset,
                        flow_direction="A2B",
                        scenario=scenario,
                    )
                    ConnectionLink.objects.get_or_create(
                        bus=dc_bus,
                        bus_connection_port="output_1",
                        asset=ess_asset,
                        flow_direction="B2A",
                        scenario=scenario,
                    )

        if len(user_assets) == 0:
            inverter.delete()
        # Remove unselected assets
        for asset in Asset.objects.filter(
            scenario=scenario.id, asset_type__asset_type__in=["bess", "pv_plant", "diesel_generator", "dso"]
        ):
            if asset.asset_type.asset_type not in user_assets:
                if asset.asset_type.asset_type == "diesel_generator":
                    Asset.objects.filter(scenario=scenario, asset_type__asset_type="gas_dso").delete()
                    Bus.objects.filter(scenario=scenario, type="Gas").delete()
                elif asset.asset_type.asset_type == "dso":
                    Asset.objects.filter(
                        scenario=scenario,
                        asset_type__asset_type="transformer_station_in",
                        name="dso_availability",
                    ).delete()
                asset.delete()

        return HttpResponseRedirect(reverse("cpn_steps", args=[proj_id, step_id + 1]))


@login_required
@require_http_methods(["GET", "POST"])
def cpn_constraints(request, proj_id, step_id=STEP_MAPPING["economic_params"]):
    project = get_object_or_404(Project, id=proj_id)

    if (project.user != request.user) and (
        project.viewers.filter(user__email=request.user.email, share_rights="edit").exists() is False
    ):
        raise PermissionDenied

    scenario = project.scenario
    page_information = (
        "Please review the following values which are suggested for tariff evaluations based on the model you chose."
    )

    # TODO if the energy supply options did not select any component warn the user
    qs_options = Options.objects.filter(project=project)
    if qs_options.exists():
        options = qs_options.get()
        es_schema_name = options.schema_name
        if es_schema_name == "":
            messages.warning(
                request,
                "You haven't selected any component to your energy system. Please select at least one and click on the 'next' button below.",
            )
            return HttpResponseRedirect(reverse("cpn_steps", args=[proj_id, STEP_MAPPING["scenario_setup"]]))

    context = {
        "proj_id": proj_id,
        "proj_name": project.name,
        "step_id": step_id,
        "scen_id": scenario.id,
        "es_schema_name": es_schema_name,
        "step_list": CPN_STEP_VERBOSE,
        "page_information": page_information,
    }

    if request.method == "POST":
        form = EconomicDataForm(request.POST, instance=project.economic_data, prefix="economic")
        try:
            equity_data = EquityData.objects.get(scenario=scenario)
            equity_form = EquityDataForm(request.POST, instance=equity_data, prefix="equity")
        except EquityData.DoesNotExist:
            equity_data = None
            equity_form = EquityDataForm(request.POST, prefix="equity")

        form_errors = False
        if form.is_valid():
            form.save()
        else:
            form_errors = True

        if equity_form.is_valid():
            equity_data = equity_form.save(commit=False)
            equity_data.debt_start = scenario.start_date.year
            equity_data.scenario = scenario
            equity_data.save()

            # compute the new price and set it to the diesel dso
            if options.has_diesel is True:
                diesel_generator = Asset.objects.get(scenario=scenario, asset_type__asset_type="diesel_generator")
                new_diesel_price_kWh = equity_data.compute_average_fuel_price(
                    initial_fuel_price=diesel_generator.opex_var_extra, project_duration=project.economic_data.duration
                )

                dso_diesel = Asset.objects.get(
                    scenario=scenario,
                    asset_type__asset_type="gas_dso",
                    name="diesel_fuel",
                )
                dso_diesel.energy_price = new_diesel_price_kWh
                dso_diesel.save()

        else:
            form_errors = True

        if form_errors is False:
            answer = HttpResponseRedirect(reverse("cpn_steps", args=[proj_id, step_id + 1]))
        else:
            # TODO this seems to redirect to wrong page is the form is wrong
            qs_bm = BusinessModel.objects.filter(scenario=project.scenario)

            try:
                equity_data = EquityData.objects.get(scenario=scenario)
                equity_form = EquityDataForm(instance=equity_data, prefix="equity")
            except EquityData.DoesNotExist:
                initial = {}
                if qs_bm.exists():
                    initial = qs_bm.first().default_economic_model_values
                equity_form = EquityDataForm(prefix="equity", initial=initial)

            demand, total_demand, peak_demand, daily_demand = get_demand_indicators(with_timeseries=True)

            qs_pv = Asset.objects.filter(scenario=project.scenario, asset_type__asset_type="pv_plant")
            if qs_pv.exists():
                pv_timeseries = json.loads(qs_pv.get().input_timeseries)
            else:
                pv_timeseries = None

            if qs_bm.exists():
                bm = qs_bm.get()
                model_name = B_MODELS[bm.model_name]["Verbose"]
            else:
                model_name = None

            context.update(
                {
                    "form": form,
                    "equity_form": equity_form,
                    "timestamps": [
                        i for i in range(len(demand))
                    ],  # json.dumps(project.scenario.get_timestamps(json_format=True)),
                    "demand": demand,
                    "pv_timeseries": pv_timeseries,
                    "daily_demand": daily_demand,
                    "peak_demand": peak_demand,
                    "model_name": model_name,
                }
            )

            answer = render(
                request,
                "cp_nigeria/steps/scenario_system_params.html",
                context,
            )
    elif request.method == "GET":
        form = EconomicDataForm(
            instance=project.economic_data, initial={"capex_fix": scenario.capex_fix}, prefix="economic"
        )
        qs_bm = BusinessModel.objects.filter(scenario=project.scenario)

        initial = {}
        if qs_bm.exists():
            bm = qs_bm.first()
            qs_bm_questionnaire = BMAnswer.objects.filter(business_model=bm)

            if qs_bm_questionnaire.exists():
                bm_equity_question = qs_bm_questionnaire.get(question__id=24)
                initial = bm_equity_question.default_economic_model_values
            else:
                initial = bm.default_economic_model_values

        try:
            equity_data = EquityData.objects.get(scenario=scenario)
            equity_form = EquityDataForm(instance=equity_data, prefix="equity", default=initial)
        except EquityData.DoesNotExist:
            equity_form = EquityDataForm(prefix="equity", initial=initial)

        if qs_bm.exists():
            bm = qs_bm.get()
            model_name = B_MODELS[bm.model_name]["Verbose"]
        else:
            model_name = None

        context.update(
            {
                "form": form,
                "equity_form": equity_form,
                "model_name": model_name,
            }
        )

        answer = render(
            request,
            "cp_nigeria/steps/scenario_system_params.html",
            context,
        )
    return answer


@login_required
@require_http_methods(["GET", "POST"])
def cpn_review(request, proj_id, step_id=STEP_MAPPING["simulation"]):
    project = get_object_or_404(Project, id=proj_id)

    if (project.user != request.user) and (
        project.viewers.filter(user__email=request.user.email, share_rights="edit").exists() is False
    ):
        raise PermissionDenied

    if request.method == "GET":
        html_template = "cp_nigeria/steps/simulation/no-status.html"
        context = {
            "scenario": project.scenario,
            "scen_id": project.scenario.id,
            "proj_id": proj_id,
            "proj_name": project.name,
            "step_id": step_id,
            "step_list": CPN_STEP_VERBOSE,
            "MVS_GET_URL": MVS_GET_URL,
            "MVS_LP_FILE_URL": MVS_LP_FILE_URL,
        }

        qs = Simulation.objects.filter(scenario=project.scenario)

        if qs.exists():
            simulation = qs.first()

            if simulation.status == PENDING:
                fetch_mvs_simulation_results(simulation)

            context.update(
                {
                    "sim_id": simulation.id,
                    "simulation_status": simulation.status,
                    "secondsElapsed": simulation.elapsed_seconds,
                    "rating": simulation.user_rating,
                    "mvs_token": simulation.mvs_token,
                }
            )

            if simulation.status == ERROR:
                context.update({"simulation_error_msg": simulation.errors})
                html_template = "cp_nigeria/steps/simulation/error.html"
            elif simulation.status == PENDING:
                html_template = "cp_nigeria/steps/simulation/pending.html"
            elif simulation.status == DONE:
                html_template = "cp_nigeria/steps/simulation/success.html"

        else:
            print("no simulation existing")

        return render(request, html_template, context)
    return None


@login_required
@require_http_methods(["GET", "POST"])
def cpn_model_choice(request, proj_id, step_id=STEP_MAPPING["business_model"]):
    project = get_object_or_404(Project, id=proj_id)

    if (project.user != request.user) and (
        project.viewers.filter(user__email=request.user.email, share_rights="edit").exists() is False
    ):
        raise PermissionDenied
    context = {
        "scenario": project.scenario,
        "scen_id": project.scenario.id,
        "proj_id": proj_id,
        "proj_name": project.name,
        "step_id": step_id,
        "step_list": CPN_STEP_VERBOSE,
    }

    html_template = "cp_nigeria/steps/scenario_model_choice.html"

    if request.method == "GET":
        bm, created = BusinessModel.objects.get_or_create(
            scenario=project.scenario, defaults={"scenario": project.scenario}
        )
        context["form"] = ModelSuggestionForm(instance=bm)
        context["bm"] = bm
        context["score"] = bm.total_score

        recommended = context["form"].fields["model_name"].initial
        if recommended is not None:
            context["recommended_model"] = recommended
            context["form"] = ModelSuggestionForm(instance=bm, initial={"model_name": recommended})
        answer = render(request, html_template, context)

    if request.method == "POST":
        bm = BusinessModel.objects.get(scenario=project.scenario)
        form = ModelSuggestionForm(request.POST, instance=bm)
        if form.is_valid():
            form.save()
            answer = HttpResponseRedirect(reverse("cpn_steps", args=[proj_id, STEP_MAPPING["business_model"] + 1]))
        else:
            answer = HttpResponseRedirect(reverse("cpn_steps", args=[proj_id, STEP_MAPPING["business_model"] + 1]))

    return answer


@login_required
@require_http_methods(["GET", "POST"])
def cpn_model_suggestion(request, bm_id):
    bm = get_object_or_404(BusinessModel, pk=bm_id)
    proj_id = bm.scenario.project.id
    return HttpResponseRedirect(reverse("cpn_model_choice", args=[proj_id]))


@login_required
@require_http_methods(["GET", "POST"])
def cpn_complex_outputs(request, proj_id, step_id=STEP_MAPPING["outputs"]):
    return cpn_outputs(request, proj_id, step_id=step_id, complex=True)


@login_required
@require_http_methods(["GET", "POST"])
def cpn_outputs(request, proj_id, step_id=STEP_MAPPING["outputs"], complex=False):
    project = get_object_or_404(Project, id=proj_id)
    options = get_object_or_404(Options, project=project)

    if (project.user != request.user) and (
        project.viewers.filter(user__email=request.user.email, share_rights="edit").exists() is False
    ):
        raise PermissionDenied
    user_scenarios = [project.scenario]

    bm = BusinessModel.objects.get(scenario__project=project)
    model = bm.model_name
    if complex is True:
        html_template = "cp_nigeria/steps/scenario_outputs.html"
    else:
        html_template = "cp_nigeria/steps/scenario_outputs_light.html"
    qs_options = Options.objects.filter(project=project)
    if qs_options.exists():
        es_schema_name = qs_options.get().schema_name
    else:
        es_schema_name = None

    project_summary = opt_caps = capex_by_category = cgs_df = capex_df = capex_assumptions = senior_debt = None
    cash_flow = losses = tariff = financial_kpis = comparison_kpi_df = system_costs = replacement_loan_table = None
    om_costs_over_lifetime = tariff_ngn = None

    ft = FinancialTool(project)
    tariff = ft.tariff

    ed = EquityData.objects.get(scenario=project.scenario)
    ed.estimated_tariff = tariff
    ed.save()

    if complex is True:
        # Initialize financial tool to calculate financial flows and test output graphs
        opt_caps = ft.system_params[ft.system_params["category"].str.contains("capacity")].copy()
        opt_caps.drop(columns=["growth_rate", "label"], inplace=True)
        opt_caps = opt_caps.pivot(columns="category", index="supply_source")
        opt_caps.columns = [col[1] for col in opt_caps.columns]
        units = {"pv_plant": "kWp", "battery": "kWh", "inverter": "kVA", "diesel_generator": "kW"}
        opt_caps.index = [f"{index} ({units[index]})" for index in opt_caps.index]

        capex_df = ft.capex
        capex_by_category = pd.DataFrame(capex_df.groupby("Category")["Total costs [NGN]"].sum())

        system_costs = ft.system_params[
            ft.system_params["category"].isin(["capex_initial", "opex_total", "fuel_costs_total"])
        ].copy()
        system_costs.drop(columns=["growth_rate", "label"], inplace=True)
        system_costs = system_costs.pivot(columns="category", index="supply_source")
        system_costs.columns = [col[1] for col in system_costs.columns]

        capex_assumptions = {}
        for cat in capex_df.Category.unique():
            sub_capex = capex_df.loc[capex_df.Category == cat]
            sub_capex = sub_capex[["Description", "Qty", "USD/Unit", "Total costs [USD]", "Total costs [NGN]"]]
            sub_capex.set_index("Description", inplace=True)
            sub_capex.fillna(0, inplace=True)
            sub_capex.loc["Total", ["Total costs [USD]", "Total costs [NGN]"]] = sub_capex[
                ["Total costs [USD]", "Total costs [NGN]"]
            ].sum()
            sub_capex.fillna("", inplace=True)
            capex_assumptions[cat] = sub_capex

        revenue_flows = ft.revenue_over_lifetime(custom_tariff=tariff)
        revenue_flows.index = revenue_flows.index.droplevel(1)
        losses = ft.losses_over_lifetime(custom_tariff=tariff)
        replacement_loan_table = ft.replacement_loan_table
        om_costs_over_lifetime = ft.om_costs_over_lifetime
        exchange_rate = ft.exchange_rate
        tariff_ngn = tariff * exchange_rate
        senior_debt = ft.initial_loan_table
        cash_flow = ft.cash_flow_over_lifetime(custom_tariff=tariff)
        cash_flow.loc["DSCR"] = cash_flow.loc["Cash flow from operating activity"] / (
            losses.loc["Equity interest"] + losses.loc["Debt interest"] + senior_debt.loc["Principal"]
        )
        financial_kpis = ft.financial_kpis
        # calculate the financial KPIs with 0% grant
        ft.remove_grant()
        no_grant_tariff = ft.tariff
        no_grant_kpis = ft.financial_kpis

        comparison_kpi_df = pd.DataFrame([financial_kpis, no_grant_kpis], index=["with_grant", "without_grant"]).T
        comparison_kpi_df.loc["tariff"] = {
            "with_grant": tariff * ft.exchange_rate,
            "without_grant": no_grant_tariff * ft.exchange_rate,
        }

        help_texts = {
            "total_investments": help_icon("All upfront investment costs"),
            "total_equity": help_icon("Total equity help text"),
            "total_grant": help_icon("Total grant help text"),
            "initial_loan_amount": help_icon("Initial loan needed to cover the initial investment costs"),
            "replacement_loan_amount": help_icon("Amount needed to replace the system components"),
        }

        for k in help_texts:
            financial_kpis[f"{k} {help_texts[k]}"] = financial_kpis.pop(k)

        aggregated_cgs = get_aggregated_cgs(project)
        cgs_df = pd.DataFrame.from_dict(aggregated_cgs, orient="index")
        cgs_df.loc["total mini-grid"] = cgs_df[cgs_df["supply_source"] == "mini_grid"].sum()
        cgs_df.drop(columns=["supply_source"], inplace=True)
        cgs_df.rename(columns={"total_demand": "total_demand"}, inplace=True)
        project_summary = get_project_summary(project)
    currency_symbol = project.economic_data.currency_symbol
    context = {
        "proj_id": proj_id,
        "project_summary": project_summary,
        "opt_caps": opt_caps,
        "capex_by_category": capex_by_category,
        "scen_id": project.scenario.id,
        "scenario_list": user_scenarios,
        "model_description": B_MODELS[model]["Description"],
        "model_name": B_MODELS[model]["Verbose"],
        "model_image": B_MODELS[model]["Graph"],
        "model_image_resp": B_MODELS[model]["Responsibilities"],
        "cgs_df": cgs_df,
        "es_schema_name": es_schema_name,
        "proj_name": project.name,
        "step_id": step_id,
        "step_list": CPN_STEP_VERBOSE,
        "capex_df": capex_df,
        "capex_assumptions": capex_assumptions,
        "senior_debt": senior_debt,
        "replacement_debt": replacement_loan_table,
        "cash_flow": cash_flow,
        "opex_costs": om_costs_over_lifetime,
        "losses": losses,
        "tariff_NGN": tariff_ngn,
        "tariff_USD": tariff,
        "financial_kpis": financial_kpis,
        "comparison_kpi_df": comparison_kpi_df,
        "system_costs": system_costs,
        "currency_symbol": currency_symbol,
    }

    return render(request, html_template, context)


# TODO for later create those views instead of simply serving the html templates
CPN_STEPS = {
    "choose_location": cpn_scenario_create,
    "grid_conditions": cpn_grid_conditions,
    "demand_profile": cpn_demand_params,
    "scenario_setup": cpn_scenario,
    "economic_params": cpn_constraints,
    "simulation": cpn_review,
    "business_model": cpn_model_choice,
    "outputs": cpn_outputs,
}

# sorts the order in which the views are served in cpn_steps (defined in STEP_MAPPING)
CPN_STEPS = [CPN_STEPS[k] for k, v in sorted(STEP_MAPPING.items(), key=lambda x: x[1]) if k in CPN_STEPS]


@login_required
@require_http_methods(["GET", "POST"])
def cpn_steps(request, proj_id, step_id=None):
    if step_id is None:
        return HttpResponseRedirect(reverse("cpn_steps", args=[proj_id, 1]))

    return CPN_STEPS[step_id - 1](request, proj_id, step_id)


@login_required
@require_http_methods(["GET"])
def cpn_simulation_cancel(request, proj_id):
    project = get_object_or_404(Project, id=proj_id)

    if (project.user != request.user) and (request.user not in project.viewers.all()):
        raise PermissionDenied

    simulation_cancel(request, project.scenario.id)

    return HttpResponseRedirect(reverse("cpn_steps", args=[project.id, STEP_MAPPING["simulation"]]))


@login_required
@require_http_methods(["GET", "POST"])
def cpn_simulation_request(request, proj_id=0):
    project = get_object_or_404(Project, id=proj_id)

    if (project.user != request.user) and (request.user not in project.viewers.all()):
        raise PermissionDenied

    request_mvs_simulation(request, project.scenario.id)

    return HttpResponseRedirect(reverse("cpn_steps", args=[project.id, STEP_MAPPING["simulation"]]))


def get_pv_output(proj_id):
    project = Project.objects.get(id=proj_id)
    coordinates = {"lat": project.latitude, "lon": project.longitude}
    location = RenewableNinjas()
    location.get_pv_output(coordinates)
    pv_ts, _ = Timeseries.objects.get_or_create(scenario=project.scenario, open_source=True, ts_type="source")

    pv_ts.values = np.squeeze(location.data.values).tolist()
    pv_ts.start_time = location.data.index[0]
    pv_ts.end_time = location.data.index[-1]
    pv_ts.time_step = 60
    pv_ts.save()

    return pv_ts.values


@login_required
@json_view
@require_http_methods(["GET", "POST"])
def get_community_details(request):
    community_id = request.GET.get("community_id")
    if community_id == "":
        data = {"name": "", "latitude": "", "longitude": ""}
    else:
        community = Community.objects.get(pk=community_id)
        data = {"name": community.name, "latitude": community.lat, "longitude": community.lon}
    return JsonResponse(data)


@login_required
@json_view
@require_http_methods(["POST"])
def ajax_consumergroup_form(request, scen_id=None, user_group_id=None):
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        # TODO change DB default value to 1
        # TODO include the possibility to display the "expected_consumer_increase", "expected_demand_increase" fields
        # with option advanced_view set by user choice
        form_ug = ConsumerGroupForm(initial={"number_consumers": 1}, advanced_view=False)
        return render(
            request,
            "cp_nigeria/steps/consumergroup_form.html",
            context={"form": form_ug, "scen_id": scen_id, "unique_id": request.POST.get("ug_id")},
        )
    return None


@login_required
@json_view
@require_http_methods(["GET", "POST"])
def ajax_bmodel_infos(request):
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        model = request.GET.get("model_choice")

        return render(
            request,
            "cp_nigeria/steps/b_models.html",
            context={
                "model_description": B_MODELS[model]["Description"],
                "model_name": B_MODELS[model]["Verbose"],
                "model_image": B_MODELS[model]["Graph"],
                "model_image_resp": B_MODELS[model]["Responsibilities"],
                "model_advantages": B_MODELS[model]["Advantages"],
                "model_disadvantages": B_MODELS[model]["Disadvantages"],
            },
        )
    return None


@login_required
@json_view
@require_http_methods(["GET", "POST"])
def ajax_load_timeseries(request):
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        consumer_type_id = request.GET.get("consumer_type")
        timeseries_qs = DemandTimeseries.objects.filter(consumer_type_id=consumer_type_id)
        return render(
            request, "cp_nigeria/steps/timeseries_dropdown_options.html", context={"timeseries_qs": timeseries_qs}
        )
    return None


@login_required
@json_view
@require_http_methods(["POST"])
def ajax_update_graph(request):
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        timeseries_id = request.POST.get("timeseries")
        timeseries = DemandTimeseries.objects.get(id=timeseries_id)
        timeseries_values = timeseries.get_values_with_unit("kWh")[:168]

        return JsonResponse({"timeseries_values": timeseries_values})

    return JsonResponse({"error": request})


@login_required
@json_view
@require_http_methods(["POST"])
def ajax_shs_tiers(request):
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        shs_tier = request.POST.get("shs_tier")
        excluded_tiers = get_shs_threshold(shs_tier)

        return JsonResponse({"excluded_tiers": excluded_tiers})

    return JsonResponse({"error": request})


@login_required
@json_view
@require_http_methods(["GET"])
def cpn_kpi_results(request, proj_id=None):
    project = get_object_or_404(Project, id=proj_id)
    options = get_object_or_404(Options, project=project)

    if (project.user != request.user) and (
        project.viewers.filter(user__email=request.user.email, share_rights="edit").exists() is False
    ):
        raise PermissionDenied

    qs = Simulation.objects.filter(scenario=project.scenario)
    if qs.exists():
        sim = qs.get()
        kpi_scalar_results_obj = KPIScalarResults.objects.get(simulation=sim)
        json.loads(kpi_scalar_results_obj.scalar_values)
        kpi_cost_results_obj = KPICostsMatrixResults.objects.get(simulation=sim)
        json.loads(kpi_cost_results_obj.cost_values)

        qs_res = FancyResults.objects.filter(simulation=sim)
        opt_caps = qs_res.filter(optimized_capacity__gt=0).values_list("asset", "asset_type", "optimized_capacity")

        kpis_of_interest = [
            # "costs_total",
            "levelized_costs_of_electricity_equivalent",
            # "total_emissions",
            "renewable_factor",
        ]
        kpis_of_comparison_diesel = ["costs_total", "levelized_costs_of_electricity_equivalent", "total_emissions"]

        # diesel_results = json.loads(KPIScalarResults.objects.get(simulation__scenario__id=230).scalar_values)
        scenario_results = json.loads(KPIScalarResults.objects.get(simulation__scenario=project.scenario).scalar_values)

        kpis = {}
        qs_inverter = qs_res.filter(optimized_capacity__gt=0, asset="inverter")
        inverter_flow = 0
        if qs_inverter.exists():
            inverter_flow = qs_inverter.get().total_flow

        total_demand, peak_demand, daily_demand = get_demand_indicators(project)

        for kpi in kpis_of_interest:
            unit = KPI_PARAMETERS[kpi]["unit"].replace("currency", project.economic_data.currency_symbol)
            if "Factor" in KPI_PARAMETERS[kpi]["unit"]:
                factor = 100.0
                unit = "%"
                # TODO quick fix for renewable share, fix properly later (this also doesnt include possible renewable share from grid)
                scen_values = round(inverter_flow / total_demand * factor, 2)
            else:
                if project.economic_data.currency_symbol in unit:
                    factor = project.economic_data.exchange_rate
                else:
                    factor = 1.0
                scen_values = round(scenario_results[kpi] * factor, 2)  # , round(diesel_results[kpi] * factor, 2)]

            kpis[kpi] = {
                "verbose": KPI_PARAMETERS[kpi]["verbose"],
                "unit": unit,
                "value": scen_values,
                "description": help_icon(KPI_PARAMETERS[kpi]["definition"]),
            }

            table_headers = {}
            headers = ["Value"]
            for header in headers:
                table_headers[header] = {}
                table_headers[header]["verbose"] = header

        return JsonResponse({"data": kpis, "headers": table_headers}, status=200, content_type="application/json")


@json_view
@login_required
@require_http_methods(["GET", "POST"])
def upload_demand_timeseries(request):
    if request.method == "GET":
        n = DemandTimeseries.objects.count()
        form = UploadDemandForm(
            initial={
                "name": f"test_timeserie{n}",
                "ts_type": "source",
                "start_time": "2023-01-01",
                "end_time": "2023-01-31",
                "open_source": True,
                "units": "kWh",
            }
        )
        context = {"form": form}

        return render(request, "asset/upload_timeseries.html", context)

    elif request.method == "POST":
        qs = request.POST
        form = UploadDemandForm(qs)

        if form.is_valid():
            ts = form.save(commit=True)
            ts.user = request.user
            return None
        return None
    return None


def cpn_business_model(request):
    # TODO process this data
    if request.method == "POST":
        grid_condition = request.POST.get("grid_condition")
        proj_id = int(request.POST.get("proj_id"))
        project = get_object_or_404(Project, id=proj_id)
        bm, created = BusinessModel.objects.get_or_create(
            scenario=project.scenario, defaults={"scenario": project.scenario}
        )
        bm.grid_condition = grid_condition.lower()
        bm.save()
        return JsonResponse({"message": f"{grid_condition} model type"})

    return JsonResponse({"message": "Invalid request method"})


@json_view
@login_required
@require_http_methods(["POST"])
def save_to_session(request):
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        graph_id = request.POST.get("graph_id")
        image_url = request.POST.get("image_url")
        request.session[graph_id] = image_url

        return JsonResponse({"status": "success"})


@json_view
@login_required
@require_http_methods(["POST"])
def ajax_download_report(request):
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        proj_id = int(request.POST.get("proj_id"))
        project = get_object_or_404(Project, id=proj_id)
        logging.info("downloading implementation plan")
        implementation_plan = ReportHandler(project)
        implementation_plan.create_cover_sheet()
        implementation_plan.create_report_content()
        # implementation_plan.add_paragraph("For now, this is just a demo")
        # implementation_plan.add_paragraph("Here are some graphs:")
        #
        # graph_dir = "static/assets/cp_nigeria/FATE_graphs"
        # for graph in os.listdir(graph_dir):
        #     implementation_plan.add_image(os.path.join(graph_dir, graph))

        # TODO what is the best way to potentially not recalculate all of the information but reuse it
        # Add tables
        # aggregated_cgs = get_aggregated_cgs(project)
        # implementation_plan.add_df_as_table(pd.DataFrame(aggregated_cgs), caption="Consumer groups")

        # Add images
        report_imgs = ["cpn_stacked_timeseriesElectricity"]
        for img in report_imgs:
            image_data = request.session.get(img).split(",")[1]
            if image_data:
                try:
                    image_bytes = base64.b64decode(image_data)
                    image = io.BytesIO(image_bytes)

                    implementation_plan.add_image(image)

                except Exception as e:
                    print(e)

        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        response["Content-Disposition"] = "attachment; filename=report.docx"
        implementation_plan.save(response)

        return response


@login_required
@require_http_methods(["GET"])
def download_report(request, proj_id):
    project = get_object_or_404(Project, id=proj_id)
    logging.info("downloading implementation plan")
    implementation_plan = ReportHandler(project)
    implementation_plan.create_cover_sheet()
    implementation_plan.create_report_content()
    # implementation_plan.add_paragraph("For now, this is just a demo")
    # implementation_plan.add_paragraph("Here are some graphs:")
    #
    # graph_dir = "static/assets/cp_nigeria/FATE_graphs"
    # for graph in os.listdir(graph_dir):
    #     implementation_plan.add_image(os.path.join(graph_dir, graph))

    # TODO what is the best way to potentially not recalculate all of the information but reuse it
    # Add tables
    # aggregated_cgs = get_aggregated_cgs(project)
    # implementation_plan.add_df_as_table(pd.DataFrame(aggregated_cgs), caption="Consumer groups")

    # # Add images
    # report_imgs = ["cpn_stacked_timeseriesElectricity"]
    # for img in report_imgs:
    #     image_data = request.session.get(img).split(",")[1]
    #     if image_data:
    #         try:
    #             image_bytes = base64.b64decode(image_data)
    #             image = io.BytesIO(image_bytes)
    #
    #             implementation_plan.add_image(image)
    #
    #         except Exception as e:
    #             print(e)

    response = "debug.docx"
    implementation_plan.save(response)

    response = HttpResponse("Hello")
    return response
