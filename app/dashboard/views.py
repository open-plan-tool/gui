import numpy as np
from django.core.exceptions import PermissionDenied
from django.template.loader import get_template
from django.db.models import Count
from django.http.response import Http404, HttpResponse
from dashboard.helpers import *
from dashboard.models import (
    AssetsResults,
    KPICostsMatrixResults,
    KPIScalarResults,
    KPI_COSTS_TOOLTIPS,
    KPI_COSTS_UNITS,
    KPI_SCALAR_TOOLTIPS,
    KPI_SCALAR_UNITS,
)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from jsonview.decorators import json_view
from projects.models import (
    Project,
    Scenario,
    Simulation,
    Asset,
    Bus,
    SensitivityAnalysis,
    get_project_sensitivity_analysis,
)
from projects.services import (
    excuses_design_under_development,
    get_selected_scenarios_in_cache,
)

from projects.forms import BusForm, AssetCreateForm, StorageForm

from projects.constants import COMPARE_VIEW
from dashboard.models import (
    ReportItem,
    FancyResults,
    SensitivityAnalysisGraph,
    get_project_reportitems,
    get_project_sensitivity_analysis_graphs,
    REPORT_GRAPHS,
    STORAGE_SUB_CATEGORIES,
    OUTPUT_POWER,
)
from projects.scenario_topology_helpers import load_scenario_topology_from_db
from dashboard.forms import (
    ReportItemForm,
    TimeseriesGraphForm,
    graph_parameters_form_factory,
)
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe
from io import BytesIO
import xlsxwriter
import json
import datetime
import logging
import traceback
from projects.helpers import parameters_helper

logger = logging.getLogger(__name__)


@login_required
@json_view
@require_http_methods(["GET"])
def scenario_available_results(request, scen_id):
    scenario = get_object_or_404(Scenario, pk=scen_id)
    if (scenario.project.user != request.user) and (
        request.user not in scenario.project.viewers.all()
    ):
        raise PermissionDenied

    try:
        assets_results_obj = AssetsResults.objects.get(simulation=scenario.simulation)
        assets_results_json = json.loads(assets_results_obj.assets_list)

        # bring all storage subasset one level up to show their flows.
        storage_asset_to_list(assets_results_json)

        # Generate available asset category JSON
        asset_category_json = [
            {"assetCategory": asset_category}
            for asset_category in assets_results_json.keys()
        ]
        # Generate available asset type JSON
        assets_names_json = [
            [
                {"assetCategory": asset_category, "assetName": asset["label"]}
                for asset in assets_results_json[asset_category]
                # show only assets of a certain Energy Vector
                if asset["energy_vector"] == request.GET["energy_vector"]
                and any(key in ["flow", "timeseries_soc"] for key in asset.keys())
            ]
            for asset_category in assets_results_json.keys()
        ]
        response_json = {"options": assets_names_json, "optgroups": asset_category_json}
        return JsonResponse(response_json, status=200, content_type="application/json")
    except Exception as e:
        logger.error(
            f"Dashboard ERROR: MVS Req Id: {scenario.simulation.mvs_token}. Thrown Exception: {traceback.format_exc()}"
        )
        return JsonResponse(
            {"error": "Could not retrieve asset names and categories."},
            status=404,
            content_type="application/json",
        )


@login_required
@require_http_methods(["POST"])
def result_change_project(request):
    proj_id = int(request.POST.get("proj_id"))
    if request.session[COMPARE_VIEW] is False:
        answer = HttpResponseRedirect(
            reverse("project_visualize_results", args=[proj_id])
        )
    else:
        answer = HttpResponseRedirect(
            reverse("project_compare_results", args=[proj_id])
        )
    return answer


@login_required
@require_http_methods(["POST", "GET"])
def scenario_visualize_results(request, proj_id=None, scen_id=None):
    request.session[COMPARE_VIEW] = False
    user_projects = request.user.project_set.all()

    if proj_id is None:
        if scen_id is not None:
            proj_id = Scenario.objects.get(id=scen_id).project.id
            # make sure the project id is always visible in url
            answer = HttpResponseRedirect(
                reverse("scenario_visualize_results", args=[proj_id, scen_id])
            )
        else:
            if request.POST:
                proj_id = int(request.POST.get("proj_id"))
            else:
                proj_id = request.user.project_set.first().id
            # make sure the project id is always visible in url
            answer = HttpResponseRedirect(
                reverse("project_visualize_results", args=[proj_id])
            )
    else:
        project = get_object_or_404(Project, id=proj_id)
        if (project.user != request.user) and (
            request.user not in project.viewers.all()
        ):
            raise PermissionDenied

        selected_scenarios = get_selected_scenarios_in_cache(request, proj_id)
        user_scenarios = project.get_scenarios_with_results()
        if user_scenarios.exists() is False:
            # TODO if user click on results from project before any scenario is simulated it might lead to problems
            if scen_id is None:
                scen_id = 0
            # There are no scenarios with results yet for this project
            answer = render(
                request,
                "report/single_scenario.html",
                {
                    "project_list": user_projects,
                    "proj_id": proj_id,
                    "scen_id": scen_id,
                    "scenario_list": [],
                    "kpi_list": KPI_PARAMETERS,
                    "table_styles": TABLES,
                    "report_items_data": [],
                },
            )
        else:
            # There are scenarios with simulation results in the project
            if scen_id is None:
                if len(selected_scenarios) == 0:
                    scen_id = user_scenarios.first().id
                else:
                    # TODO here allow more than one scenario to be selected
                    scen_id = selected_scenarios[0]

            # collect the report items of the project
            report_items_data = [
                ri.render_json for ri in get_project_reportitems(project)
            ]

            scenario = get_object_or_404(Scenario, id=scen_id)
            # TODO: change this when multi-scenario selection is allowed

            if (scenario.project.user != request.user) and (
                request.user not in scenario.project.viewers.all()
            ):
                raise PermissionDenied

            qs = Simulation.objects.filter(scenario=scenario)
            if qs.exists() and scenario in user_scenarios:
                kpi_scalar_results_obj = KPIScalarResults.objects.get(
                    simulation=scenario.simulation
                )
                kpi_scalar_values_dict = json.loads(
                    kpi_scalar_results_obj.scalar_values
                )

                scalar_kpis_json = kpi_scalars_list(
                    kpi_scalar_values_dict, KPI_SCALAR_UNITS, KPI_SCALAR_TOOLTIPS
                )

                update_selected_scenarios_in_cache(request, proj_id, scen_id)

                topology_data_list = load_scenario_topology_from_db(scen_id)

                answer = render(
                    request,
                    "report/single_scenario.html",
                    {
                        "scen_id": scen_id,
                        "scalar_kpis": scalar_kpis_json,
                        "proj_id": proj_id,
                        "project_list": user_projects,
                        "scenario_list": user_scenarios,
                        "report_items_data": report_items_data,
                        "kpi_list": KPI_PARAMETERS,
                        "table_styles": TABLES,
                        "topology_data_list": json.dumps(topology_data_list),
                    },
                )

            else:
                # redirect to the page where the simulation is started, or results fetched again
                messages.error(
                    request,
                    _(
                        "Your scenario was never simulated, the results are still pending or there is an error in the simulation. Please click on 'Run simulation', 'Update results' or 'Check status' button "
                    ),
                )
                answer = HttpResponseRedirect(
                    reverse("scenario_review", args=[proj_id, scen_id])
                )

    return answer


@login_required
@require_http_methods(["POST", "GET"])
def project_compare_results(request, proj_id):
    request.session[COMPARE_VIEW] = True
    user_projects = request.user.project_set.all()

    project = get_object_or_404(Project, id=proj_id)
    if (project.user != request.user) and (request.user not in project.viewers.all()):
        raise PermissionDenied

    user_scenarios = project.get_scenarios_with_results()
    report_items_data = [
        ri.render_json
        for ri in get_project_reportitems(project)
        .annotate(c=Count("simulations"))
        .filter(c__gt=1)
    ]

    selected_scenarios = get_selected_scenarios_in_cache(request, proj_id)
    return render(
        request,
        "report/compare_scenario.html",
        {
            "scen_id": None,
            "proj_id": proj_id,
            "project_list": user_projects,
            "scenario_list": user_scenarios,
            "selected_scenarios": selected_scenarios,
            "multiple_scenario_selection": len(selected_scenarios) > 1,
            "report_items_data": report_items_data,
            "kpi_list": KPI_PARAMETERS,
            "table_styles": TABLES,
        },
    )


@login_required
@require_http_methods(["POST", "GET"])
def project_sensitivity_analysis(request, proj_id, sa_id=None):
    request.session[COMPARE_VIEW] = False
    user_projects = request.user.project_set.all()

    if proj_id is None:
        if sa_id is not None:
            proj_id = SensitivityAnalysis.objects.get(id=sa_id).scenario.project.id
            # make sure the project id is always visible in url
            answer = HttpResponseRedirect(
                reverse("project_sensitivity_analysis", args=[proj_id, sa_id])
            )
        else:
            if request.POST:
                proj_id = int(request.POST.get("proj_id"))
            else:
                proj_id = request.user.project_set.first().id
            # make sure the project id is always visible in url
            answer = HttpResponseRedirect(
                reverse("project_sensitivity_analysis", args=[proj_id])
            )
    else:

        project = get_object_or_404(Project, id=proj_id)
        if (project.user != request.user) and (
            request.user not in project.viewers.all()
        ):
            raise PermissionDenied

        user_sa = get_project_sensitivity_analysis(project)
        if user_sa.exists() is False:
            # There are no sensitivity analysis with results yet for this project
            answer = render(
                request,
                "report/sensitivity_analysis.html",
                {
                    "project_list": user_projects,
                    "proj_id": proj_id,
                    "sa_list": [],
                    "report_items_data": [],
                },
            )
        else:
            if sa_id is None:
                sa_id = user_sa.first().id

            sa_graph_form = graph_parameters_form_factory(
                GRAPH_SENSITIVITY_ANALYSIS, proj_id=proj_id
            )
            report_items_data = [
                ri.render_json
                for ri in get_project_sensitivity_analysis_graphs(project)
            ]
            answer = render(
                request,
                "report/sensitivity_analysis.html",
                {
                    "proj_id": proj_id,
                    "project_list": user_projects,
                    "sa_list": user_sa,
                    "sa_id": sa_id,
                    "report_items_data": report_items_data,
                    "sa_graph_form": sa_graph_form,
                },
            )
    return answer


@login_required
@json_view
@require_http_methods(["POST"])
def report_create_item(request, proj_id):
    """This ajax view is triggered by clicking on "create" in the form to add a report item"""

    if request.is_ajax():
        qs = request.POST
        multi_scenario = request.session.get(COMPARE_VIEW, False)
        report_form = ReportItemForm(qs, proj_id=proj_id, multi_scenario=multi_scenario)
        answer_context = {
            "report_form": report_form.as_table(),
            "report_type": qs.get("report_type"),
        }
        if report_form.is_valid():
            # scenario selection and graph type are valid
            report_item = report_form.save(commit=False)
            if multi_scenario is True:
                scen_ids = [int(s) for s in report_form.cleaned_data["scenarios"]]
            else:
                scen_ids = [int(report_form.cleaned_data["scenarios"])]
            graph_parameter_form = graph_parameters_form_factory(
                report_item.report_type, qs, scenario_ids=scen_ids
            )
            if graph_parameter_form.is_valid():
                # parameters choosen for the scenario selection and graph type are valid
                report_item.safely_assign_parameters(graph_parameter_form.cleaned_data)
                report_item.save()
                # link the report item with all simulations matching the provided list of scenario ids
                report_item.update_simulations(
                    [
                        sim
                        for sim in Simulation.objects.filter(
                            scenario__id__in=scen_ids
                        ).values_list("id", flat=True)
                    ]
                )

                answer = JsonResponse(
                    report_item.render_json, status=200, content_type="application/json"
                )
            else:

                # TODO workout the passing of post when there are errors (in crisp format)
                form_html = get_template("report/report_item_parameters_form.html")
                answer_context.update(
                    {
                        "report_form": form_html.render(
                            {
                                "report_item_form": report_form,
                                "graph_parameters_form": graph_parameter_form,
                            }
                        )
                    }
                )

                answer = JsonResponse(
                    answer_context, status=422, content_type="application/json"
                )
        else:
            # TODO workout the passing of post when there are errors (in crisp format)

            answer = JsonResponse(
                answer_context, status=422, content_type="application/json"
            )

    else:
        answer = JsonResponse(
            {"error": "This url is only for post calls"},
            status=405,
            content_type="application/json",
        )
    return answer


@login_required
@require_http_methods(["POST"])
def sensitivity_analysis_create_graph(request, proj_id):
    """This view is triggered by clicking on "create" in the form to add a sensitivity analysis graph"""

    if request.method == "POST":
        qs = request.POST
        graph_parameter_form = graph_parameters_form_factory(
            GRAPH_SENSITIVITY_ANALYSIS, qs, proj_id=proj_id
        )
        if graph_parameter_form.is_valid():
            sa_graph = graph_parameter_form.save()

        # Refresh the sensitivity analysis page with a new graph if the form was valid
        answer = HttpResponseRedirect(
            reverse(
                "project_sensitivity_analysis", args=[proj_id, sa_graph.analysis.id]
            )
        )
    else:
        answer = JsonResponse(
            {"error": "This url is only for post calls"},
            status=405,
            content_type="application/json",
        )
    return answer


@login_required
@json_view
@require_http_methods(["POST"])
def report_delete_item(request, proj_id):
    """This ajax view is triggered by clicking on "delete" in the report item top right menu options"""
    if request.is_ajax():
        qs = request.POST
        report_item_id = qs.get("report_item_id")
        if "reportItem" in report_item_id:
            ri = get_object_or_404(ReportItem, id=decode_report_item_id(report_item_id))
        elif "saItem" in report_item_id:
            ri = get_object_or_404(
                SensitivityAnalysisGraph, id=decode_sa_graph_id(report_item_id)
            )
        ri.delete()

        answer = JsonResponse(
            {"reportItemId": report_item_id},
            status=200,
            content_type="application/json",
        )
    else:
        answer = JsonResponse(
            {"error": "This url is only for ajax calls"},
            status=405,
            content_type="application/json",
        )
    return answer


@login_required
@json_view
@require_http_methods(["POST"])
def ajax_get_graph_parameters_form(request, proj_id):
    if request.is_ajax():
        # Prefill the form with initial values
        initial_values = {}
        initial_values["title"] = request.POST.get("title")
        initial_values["report_type"] = request.POST.get("report_type")
        # Converts the scenario ids provided as list of strings to a list of scenario ids as list of ints
        initial_values["scenarios"] = [
            int(s) for s in json.loads(request.POST.get("selected_scenarios"))
        ]
        multi_scenario = request.session.get(COMPARE_VIEW, False)

        # TODO add a parameter reportitem_id to the function, default to None and load the values from the db if it exits, then also changes the initial of the graph parameters form

        report_item_form = ReportItemForm(
            initial=initial_values, proj_id=proj_id, multi_scenario=multi_scenario
        )

        answer = render(
            request,
            "report/report_item_parameters_form.html",
            context={
                "report_item_form": report_item_form,
                "graph_parameters_form": graph_parameters_form_factory(
                    initial_values["report_type"],
                    scenario_ids=initial_values["scenarios"],
                ),
            },
        )
    else:
        answer = JsonResponse(
            {"error": "This url is only for post calls"},
            status=405,
            content_type="application/json",
        )
    return answer


@login_required
@require_http_methods(["POST"])
def ajax_get_sensitivity_analysis_parameters(request):
    if request.is_ajax():
        qs = request.POST
        sa_id = int(qs.get("sa_id"))
        sa_item = get_object_or_404(SensitivityAnalysis, id=sa_id)

        return render(
            request,
            "report/sa_parameters_form.html",
            context={
                "output_parameters": [
                    {"name": p, "verbose": KPI_helper.get_doc_verbose(p)}
                    for p in sa_item.output_names
                ]
            },
        )


@login_required
@json_view
@require_http_methods(["GET"])
def update_selected_single_scenario(request, proj_id, scen_id):
    proj_id = str(proj_id)
    scen_id = str(scen_id)
    if request.is_ajax():
        status_code = 200
        selected_scenarios_per_project = request.session.get("selected_scenarios", {})
        selected_scenario = selected_scenarios_per_project.get(proj_id, [])

        if scen_id in selected_scenario:
            if len(selected_scenario) > 1:
                selected_scenario.pop(selected_scenario.index(scen_id))
                msg = _(f"Scenario {scen_id} was deselected")
            else:
                msg = _(f"At least one scenario need to be selected")
                status_code = 405
        else:
            selected_scenario = [scen_id]
            msg = _(f"Scenario {scen_id} was selected")
        selected_scenarios_per_project[proj_id] = selected_scenario
        request.session["selected_scenarios"] = selected_scenarios_per_project
        answer = JsonResponse(
            {"success": msg}, status=status_code, content_type="application/json"
        )
    else:
        answer = JsonResponse(
            {"error": "This url is only for AJAX calls"},
            status=405,
            content_type="application/json",
        )
    return answer


@login_required
@json_view
@require_http_methods(["POST"])
def update_selected_multi_scenarios(request, proj_id):
    proj_id = str(proj_id)
    qs = request.POST
    scen_ids = qs.get("scen_ids", None)
    if scen_ids is not None:
        scen_ids = json.loads(scen_ids)

    if request.is_ajax():
        status_code = 200
        selected_scenarios_per_project = request.session.get("selected_scenarios", {})
        selected_scenarios = selected_scenarios_per_project.get(proj_id, [])

        selected_scenarios = scen_ids
        msg = _(f"Scenarios were updated")

        selected_scenarios_per_project[proj_id] = selected_scenarios
        request.session["selected_scenarios"] = selected_scenarios_per_project
        answer = JsonResponse(
            {"success": msg}, status=status_code, content_type="application/json"
        )
    else:
        answer = JsonResponse(
            {"error": "This url is only for AJAX calls"},
            status=405,
            content_type="application/json",
        )
    return answer


@login_required
@json_view
@require_http_methods(["GET"])
def request_kpi_table(request, proj_id=None):

    compare_scen = request.GET.get("compare_scenario")
    if compare_scen != "":
        compare_scen = int(compare_scen)
    else:
        compare_scen = None

    selected_scenarios = get_selected_scenarios_in_cache(request, proj_id)

    if compare_scen is not None:
        selected_scenarios = [compare_scen]
    kpis = {}
    scen_names = []
    for scenario_id in selected_scenarios:
        scenario = get_object_or_404(Scenario, pk=scenario_id)
        scen_names.append(scenario.name)
        kpi_scalar_results_obj = KPIScalarResults.objects.get(
            simulation=scenario.simulation
        )
        kpi_scalar_results_dict = json.loads(kpi_scalar_results_obj.scalar_values)
        kpis[scenario_id] = kpi_scalar_results_dict

    proj = get_object_or_404(Project, id=scenario.project.id)
    unit_conv = {"currency": proj.economic_data.currency, "Faktor": "%"}
    table = TABLES.get("management", None)

    # do some unit substitution
    for l in table.values():
        for e in l:
            if e["unit"] in unit_conv:
                sub = unit_conv[e["unit"]]
                e["unit"] = sub

    if table is not None:
        for subtable_title, subtable_content in table.items():
            for param in subtable_content:
                param["scen_values"] = [
                    round_only_numbers(
                        kpis[scen_id].get(param["id"], "not implemented yet"), 2
                    )
                    for scen_id in selected_scenarios
                ]
                param["description"] = KPI_helper.get_doc_definition(param["id"])
                if "currency" in param["unit"]:
                    param["unit"] = param["unit"].replace(
                        "currency", scenario.get_currency()
                    )
        answer = JsonResponse(
            {"data": table, "hdrs": ["Indicator"] + scen_names},
            status=200,
            content_type="application/json",
        )

    else:
        allowed_styles = ", ".join(TABLES.keys())
        answer = JsonResponse(
            {
                "error": f"The kpi table sytle {table_style} is not implemented. Please try one of {allowed_styles}"
            },
            status=404,
            content_type="application/json",
        )

    return answer


@login_required
@require_http_methods(["GET"])
def view_asset_parameters(request, scen_id, asset_type_name, asset_uuid):
    """Return a template to view the input parameters and results, if any"""
    scenario = Scenario.objects.get(id=scen_id)
    if asset_type_name == "bus":
        template = "asset/bus_create_form.html"
        existing_bus = get_object_or_404(Bus, pk=asset_uuid)
        form = BusForm(
            asset_type=asset_type_name, instance=existing_bus, view_only=True
        )

        context = {"form": form}
    elif asset_type_name in ["bess", "h2ess", "gess", "hess"]:
        template = "asset/storage_asset_create_form.html"
        existing_ess_asset = get_object_or_404(Asset, unique_id=asset_uuid)
        ess_asset_children = Asset.objects.filter(parent_asset=existing_ess_asset.id)
        ess_capacity_asset = ess_asset_children.get(asset_type__asset_type="capacity")
        ess_charging_power_asset = ess_asset_children.get(
            asset_type__asset_type="charging_power"
        )
        ess_discharging_power_asset = ess_asset_children.get(
            asset_type__asset_type="discharging_power"
        )
        # also get all child assets
        form = StorageForm(
            asset_type=asset_type_name,
            view_only=True,
            initial={
                "name": existing_ess_asset.name,
                "installed_capacity": ess_capacity_asset.installed_capacity,
                "age_installed": ess_capacity_asset.age_installed,
                "capex_fix": ess_capacity_asset.capex_fix,
                "capex_var": ess_capacity_asset.capex_var,
                "opex_fix": ess_capacity_asset.opex_fix,
                "opex_var": ess_capacity_asset.opex_var,
                "lifetime": ess_capacity_asset.lifetime,
                "crate": ess_capacity_asset.crate,
                "efficiency": ess_capacity_asset.efficiency,
                "dispatchable": ess_capacity_asset.dispatchable,
                "optimize_cap": ess_capacity_asset.optimize_cap,
                "soc_max": ess_capacity_asset.soc_max,
                "soc_min": ess_capacity_asset.soc_min,
            },
        )

        context = {"form": form, "display_results": False}

        qs = Simulation.objects.filter(scenario=scenario)
        if qs.exists():
            asset_results = AssetsResults.objects.get(simulation=qs.get())
            flows = []
            # collect optimized add cap of capacity and flow of all 3 sub assets of storage asset
            for subasset_name in STORAGE_SUB_CATEGORIES:
                subasset_results = asset_results.single_asset_results(
                    asset_name=format_storage_subasset_name(
                        existing_ess_asset.name, subasset_name
                    ),
                    asset_category="energy_storage",
                )
                # this parameter will only be present for capacity
                result_param = "optimized_add_cap"
                if result_param in subasset_results:
                    context.update({result_param: subasset_results[result_param]})
                    context.update({"display_results": True})
                # flow is a dict with keys "value" and "unit"
                result_param = "flow"
                if result_param in subasset_results:
                    if subasset_name == OUTPUT_POWER:

                        subasset_results[result_param]["value"] = -1 * np.array(
                            subasset_results[result_param]["value"]
                        )
                        subasset_results[result_param]["value"] = subasset_results[
                            result_param
                        ]["value"].tolist()

                    subasset_results[result_param].update({"name": subasset_name})
                    flows.append(subasset_results[result_param])
            if len(flows) > 0:
                context.update(
                    {
                        "soc_traces": json.dumps(
                            {
                                "timestamps": scenario.get_timestamps(json_format=True),
                                "flows": flows,
                            }
                        )
                    }
                )
                context.update({"display_results": True})

    else:  # all other assets
        template = "asset/asset_create_form.html"
        existing_asset = get_object_or_404(Asset, unique_id=asset_uuid)

        form = AssetCreateForm(
            asset_type=asset_type_name, instance=existing_asset, view_only=True
        )
        input_timeseries_data = (
            existing_asset.input_timeseries if existing_asset.input_timeseries else ""
        )

        context = {
            "form": form,
            "input_timeseries_data": input_timeseries_data,
            "input_timeseries_timestamps": json.dumps(
                scenario.get_timestamps(json_format=True)
            ),
            "display_results": False,
        }

        # fetch optimized capacity and flow if they exist
        qs = Simulation.objects.filter(scenario=scenario)
        if qs.exists():
            asset_results = AssetsResults.objects.get(
                simulation=qs.get()
            ).single_asset_results(asset_name=existing_asset.name)

            result_param = "optimized_add_cap"
            if result_param in asset_results:
                context.update({result_param: asset_results[result_param]})
                context.update({"display_results": True})
            else:
                if "optimize_capacity" in asset_results:
                    if asset_results["optimize_capacity"]["value"] is True:

                        results_dict = json.loads(qs.get().results)
                        kpi = results_dict["kpi"]["scalar_matrix"]
                        context.update(
                            {
                                result_param: {
                                    "value": kpi[existing_asset.name][result_param],
                                    "unit": kpi[existing_asset.name]["unit"],
                                }
                            }
                        )
                        context.update({"display_results": True})

            # flow is a dict with keys "value" and "unit"
            result_param = "flow"
            if result_param in asset_results:
                # add key "timestamp" to the flow dict
                asset_results[result_param].update(
                    {"timestamps": scenario.get_timestamps(json_format=True)}
                )
                context.update({result_param: json.dumps(asset_results[result_param])})
                context.update({"display_results": True})
            else:
                # provider have their flows under consumption and feedin
                if existing_asset.is_provider is True:
                    traces = []
                    timestamps = scenario.get_timestamps(json_format=True)
                    for fl, fl_name in zip(
                        ("connected_consumption_sources", "connected_feedin_sink"),
                        ("Consumption", "Feedin"),
                    ):
                        subasset_name = asset_results[fl]
                        subasset_results = AssetsResults.objects.get(
                            simulation=qs.get()
                        ).single_asset_results(asset_name=subasset_name)

                        subasset_results = subasset_results["flow"]
                        subasset_results.update({"name": fl_name})

                        # make consumption values negative
                        if fl_name == "Consumption":
                            subasset_results["value"] = -1 * np.array(
                                subasset_results["value"]
                            )
                            subasset_results["value"] = subasset_results[
                                "value"
                            ].tolist()

                        traces.append(subasset_results)

                    # add the possibility to see the cap limit on the feedin on the result graph
                    feedin_cap = existing_asset.feedin_cap
                    traces.append(
                        {
                            "value": [feedin_cap for t in timestamps],
                            "name": parameters_helper.get_doc_verbose("feedin_cap"),
                            "unit": parameters_helper.get_doc_unit("feedin_cap"),
                            "options": {"visible": "legendonly"},
                        }
                    )

                    context.update(
                        {
                            "flow": json.dumps(
                                {"timestamps": timestamps, "traces": traces}
                            )
                        }
                    )
                    context.update({"display_results": True})
    return render(request, template, context)


@login_required
@json_view
@require_http_methods(["GET"])
def scenario_economic_results(request, scen_id=None):
    """
    This view gathers all simulation specific cost matrix KPI results
    and sends them to the client for representation.
    """
    if scen_id is None:
        return JsonResponse(
            {"error": "No scenario name provided"},
            status=404,
            content_type="application/json",
            safe=False,
        )

    scenario = get_object_or_404(Scenario, pk=scen_id)

    # if scenario.project.user != request.user:
    #     return HttpResponseForbidden()
    if (scenario.project.user != request.user) and (
        request.user not in scenario.project.viewers.all()
    ):
        raise PermissionDenied

    try:
        kpi_cost_results_obj = KPICostsMatrixResults.objects.get(
            simulation=scenario.simulation
        )
        kpi_cost_values_dict = json.loads(kpi_cost_results_obj.cost_values)

        new_dict = dict()
        for asset_name in kpi_cost_values_dict.keys():
            for category, v in kpi_cost_values_dict[asset_name].items():
                new_dict.setdefault(category, {})[asset_name] = v

        # non-dummy data
        results_json = [
            {
                "values": [
                    (
                        round(value, 3)
                        if "€/kWh" in KPI_COSTS_UNITS[category]
                        else round(value, 2)
                    )
                    for value in new_dict[category].values()
                ],
                "labels": [
                    asset.replace("_", " ").upper()
                    for asset in new_dict[category].keys()
                ],
                "type": "pie",
                "title": category.replace("_", " ").upper(),
                "titleTooltip": KPI_COSTS_TOOLTIPS[category],
                "units": [KPI_COSTS_UNITS[category] for _ in new_dict[category].keys()],
            }
            for category in new_dict.keys()
            if category in KPI_COSTS_UNITS.keys()
            and sum(new_dict[category].values())
            > 0.0  # there is at least one non zero value
            and len(
                list(
                    filter(
                        lambda asset_name: new_dict[category][asset_name] > 0.0,
                        new_dict[category],
                    )
                )
            )
            > 1.0
            # there are more than one assets with value > 0
        ]

        return JsonResponse(
            results_json, status=200, content_type="application/json", safe=False
        )
    except Exception as e:
        logger.error(
            f"Dashboard ERROR: MVS Req Id: {scenario.simulation.mvs_token}. Thrown Exception: {traceback.format_exc()}"
        )
        return JsonResponse(
            {"error": f"Could not retrieve kpi cost data."},
            status=404,
            content_type="application/json",
            safe=False,
        )


# TODO: Improve automatic unit recognition and selection
# TODO: If providers are used in model, delete duplicate time-series "DSO_consumption_period"
#  (naive string matching solution in get_asset_and_ts() done)
@login_required
@json_view
@require_http_methods(["GET"])
def scenario_visualize_timeseries(request, proj_id=None, scen_id=None):
    if scen_id is None:
        selected_scenario = get_selected_scenarios_in_cache(request, proj_id)
    else:
        selected_scenario = [scen_id]

    simulations = []

    for scen_id in selected_scenario:
        scenario = get_object_or_404(Scenario, pk=scen_id)
        if (scenario.project.user != request.user) and (
            request.user not in scenario.project.viewers.all()
        ):
            raise PermissionDenied
        simulations.append(scenario.simulation)

    results_json = report_item_render_to_json(
        report_item_id="all_timeseries",
        data=REPORT_GRAPHS[GRAPH_TIMESERIES](simulations=simulations),
        title="",
        report_item_type=GRAPH_TIMESERIES,
    )

    return JsonResponse(
        results_json, status=200, content_type="application/json", safe=False
    )


def scenario_visualize_stacked_timeseries(request, scen_id):
    scenario = get_object_or_404(Scenario, pk=scen_id)
    if (scenario.project.user != request.user) and (
        request.user not in scenario.project.viewers.all()
    ):
        raise PermissionDenied

    results_json = []
    for energy_vector in scenario.energy_vectors:

        results_json.append(
            report_item_render_to_json(
                report_item_id=energy_vector,
                data=REPORT_GRAPHS[GRAPH_TIMESERIES_STACKED](
                    simulations=[scenario.simulation],
                    y_variables=None,
                    energy_vector=energy_vector,
                ),
                title=energy_vector,
                report_item_type=GRAPH_TIMESERIES_STACKED,
            )
        )

    return JsonResponse(
        results_json, status=200, content_type="application/json", safe=False
    )


# TODO exclude sink components
def scenario_visualize_capacities(request, proj_id, scen_id=None):

    if scen_id is None:
        selected_scenario = get_selected_scenarios_in_cache(request, proj_id)
    else:
        selected_scenario = [scen_id]

    simulations = []

    common_assets = []  # TODO take intersection of all y_variables sets

    for scen_id in selected_scenario:
        scenario = get_object_or_404(Scenario, pk=scen_id)
        if (scenario.project.user != request.user) and (
            request.user not in scenario.project.viewers.all()
        ):
            raise PermissionDenied
        simulations.append(scenario.simulation)

        assets_results = AssetsResults.objects.get(simulation__scenario__id=scenario.id)
        y_variables = [n for n in assets_results.available_timeseries]

    results_json = report_item_render_to_json(
        report_item_id="capacities",
        data=REPORT_GRAPHS[GRAPH_CAPACITIES](
            simulations=simulations, y_variables=y_variables
        ),
        title="",
        report_item_type=GRAPH_CAPACITIES,
    )

    return JsonResponse(
        results_json, status=200, content_type="application/json", safe=False
    )


# TODO: Sector coupling must be refined (including transformer flows)
def scenario_visualize_sankey(request, scen_id):
    scenario = get_object_or_404(Scenario, pk=scen_id)
    if (scenario.project.user != request.user) and (
        request.user not in scenario.project.viewers.all()
    ):
        raise PermissionDenied

    results_json = report_item_render_to_json(
        report_item_id="sankey",
        data=REPORT_GRAPHS[GRAPH_SANKEY](
            simulation=scenario.simulation, energy_vector=scenario.energy_vectors
        ),
        title="Sankey",
        report_item_type=GRAPH_SANKEY,
    )

    return JsonResponse(
        results_json, status=200, content_type="application/json", safe=False
    )


@login_required
@require_http_methods(["GET"])
def download_scalar_results(request, scen_id):
    scenario = get_object_or_404(Scenario, pk=scen_id)

    if (scenario.project.user != request.user) and (
        request.user not in scenario.project.viewers.all()
    ):
        raise PermissionDenied

    try:
        kpi_scalar_results_obj = KPIScalarResults.objects.get(
            simulation=scenario.simulation
        )
        kpi_scalar_values_dict = json.loads(kpi_scalar_results_obj.scalar_values)
        scalar_kpis_json = kpi_scalars_list(
            kpi_scalar_values_dict, KPI_SCALAR_UNITS, KPI_SCALAR_TOOLTIPS
        )

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet("Scalars")

        for idx, kpi_obj in enumerate(scalar_kpis_json):
            if idx == 0:
                worksheet.write_row(0, 0, kpi_obj.keys())
            worksheet.write_row(idx + 1, 0, kpi_obj.values())

        workbook.close()
        output.seek(0)
    except Exception as e:
        logger.error(
            f"Dashboard ERROR: Could not generate KPI Scalars download file with Scenario Id: {scen_id}. Thrown Exception: {traceback.format_exc()}"
        )
        raise Http404()

    filename = "kpi_scalar_results.xlsx"
    response = HttpResponse(
        output,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f"attachment; filename={filename}"

    return response


@login_required
@require_http_methods(["GET"])
def download_cost_results(request, scen_id):
    scenario = get_object_or_404(Scenario, pk=scen_id)

    if (scenario.project.user != request.user) and (
        request.user not in scenario.project.viewers.all()
    ):
        raise PermissionDenied

    try:
        kpi_cost_results_obj = KPICostsMatrixResults.objects.get(
            simulation=scenario.simulation
        )
        kpi_cost_values_dict = json.loads(kpi_cost_results_obj.cost_values)

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet("Costs")

        for col, asset in enumerate(kpi_cost_values_dict.items()):
            asset_name, asset_dict = asset
            if col == 0:
                worksheet.write_column(1, 0, asset_dict.keys())
                worksheet.write_row(0, 1, kpi_cost_values_dict.keys())
            worksheet.write_column(1, col + 1, asset_dict.values())

        workbook.close()
        output.seek(0)
    except Exception as e:
        logger.error(
            f"Dashboard ERROR: Could not generate KPI Costs download file with Scenario Id: {scen_id}. Thrown Exception: {traceback.format_exc()}"
        )
        raise Http404()

    filename = "kpi_individual_costs.xlsx"
    response = HttpResponse(
        output,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f"attachment; filename={filename}"

    return response


@login_required
@require_http_methods(["GET"])
def download_timeseries_results(request, scen_id):
    scenario = get_object_or_404(Scenario, pk=scen_id)

    if (scenario.project.user != request.user) and (
        request.user not in scenario.project.viewers.all()
    ):
        raise PermissionDenied

    try:
        assets_results_obj = AssetsResults.objects.get(simulation=scenario.simulation)
        assets_results_json = json.loads(assets_results_obj.assets_list)
        # Create the datetimes index. Constrains: step in minutes and evaluated_period in days
        base_date = scenario.start_date
        datetime_list = [
            datetime.datetime.timestamp(base_date + datetime.timedelta(minutes=step))
            for step in range(
                0,
                24 * scenario.evaluated_period * scenario.time_step,
                scenario.time_step,
            )
        ]

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        merge_format = workbook.add_format(
            {"bold": True, "align": "center", "valign": "vcenter"}
        )

        KEY1, KEY2, KEY3, KEY4 = (
            "timeseries_soc",
            "input power",
            "output power",
            "storage capacity",
        )

        for key in assets_results_json.keys():
            worksheet = workbook.add_worksheet(key)
            worksheet.write(0, 0, "Timestamp")
            if key != "energy_storage":
                worksheet.write_column(2, 0, datetime_list)
                for col, asset in enumerate(assets_results_json[key]):
                    if all(key in asset.keys() for key in ["label", "flow"]):
                        worksheet.write(0, col + 1, asset["label"])
                        worksheet.write(1, col + 1, asset["flow"]["unit"])
                        worksheet.write_column(2, col + 1, asset["flow"]["value"])
            else:
                worksheet.write_column(3, 0, datetime_list)
                col = 0
                for idx, storage_asset in enumerate(assets_results_json[key]):
                    if all(
                        key in storage_asset.keys()
                        for key in ["label", KEY1, KEY2, KEY3, KEY4]
                    ):
                        worksheet.merge_range(
                            0, col + 1, 0, col + 4, storage_asset["label"], merge_format
                        )

                        worksheet.write(1, col + 1, KEY1)
                        worksheet.write(2, col + 1, storage_asset[KEY1]["unit"])
                        worksheet.write_column(3, col + 1, storage_asset[KEY1]["value"])

                        worksheet.write(1, col + 2, KEY2)
                        worksheet.write(2, col + 2, storage_asset[KEY2]["flow"]["unit"])
                        worksheet.write_column(
                            3, col + 2, storage_asset[KEY2]["flow"]["value"]
                        )

                        worksheet.write(1, col + 3, KEY3)
                        worksheet.write(2, col + 3, storage_asset[KEY3]["flow"]["unit"])
                        worksheet.write_column(
                            3, col + 3, storage_asset[KEY3]["flow"]["value"]
                        )

                        worksheet.write(1, col + 4, KEY4)
                        worksheet.write(2, col + 4, storage_asset[KEY4]["flow"]["unit"])
                        worksheet.write_column(
                            3, col + 4, storage_asset[KEY3]["flow"]["value"]
                        )

                        col += 5

        workbook.close()
        output.seek(0)

        filename = f"scenario{scen_id}_timeseries_results.xlsx"
        response = HttpResponse(
            output,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f"attachment; filename={filename}"

        return response
    except Exception as e:
        logger.error(
            f"Dashboard ERROR: Could not generate Timeseries Results file for the Scenario with Id: {scen_id}. Thrown Exception: {traceback.format_exc()}"
        )
        raise Http404()


@login_required
@require_http_methods(["GET"])
def redirect_download_timeseries_results(request, proj_id):

    selected_scenario = get_selected_scenarios_in_cache(request, proj_id)

    if len(selected_scenario) >= 1:
        scen_id = int(selected_scenario[0])
        answer = download_timeseries_results(request, scen_id)
    else:
        messages.error(
            request,
            _(
                "No scenario was available in the cache, try refreshing the page and make sure one scenario is selected."
            ),
        )
        answer = HttpResponseRedirect(request.headers.get("Referer"))

    return answer
