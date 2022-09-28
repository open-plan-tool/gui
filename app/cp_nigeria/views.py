# from bootstrap_modal_forms.generic import BSModalCreateView
# from bootstrap_modal_forms.generic import BSModalCreateView
from django.contrib.auth.decorators import login_required
import json
import logging
import traceback
from django.http import HttpResponseForbidden, JsonResponse
from django.http.response import Http404
from django.utils.translation import gettext_lazy as _
from django.shortcuts import *
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from jsonview.decorators import json_view
from datetime import datetime
from users.models import CustomUser
from django.db.models import Q
from epa.settings import MVS_GET_URL, MVS_LP_FILE_URL, MVS_SA_GET_URL
from .forms import *
from projects.requests import (
    mvs_simulation_request,
    fetch_mvs_simulation_results,
    mvs_sensitivity_analysis_request,
    fetch_mvs_sa_results,
)
from projects.models import *
from projects.scenario_topology_helpers import (
    handle_storage_unit_form_post,
    handle_bus_form_post,
    handle_asset_form_post,
    load_scenario_topology_from_db,
    NodeObject,
    update_deleted_objects_from_database,
    duplicate_scenario_objects,
    duplicate_scenario_connections,
    load_scenario_from_dict,
    load_project_from_dict,
)
from projects.helpers import format_scenario_for_mvs
from projects.constants import DONE, PENDING, ERROR, MODIFIED
from projects.services import (
    create_or_delete_simulation_scheduler,
    excuses_design_under_development,
    send_feedback_email,
    get_selected_scenarios_in_cache,
)
import traceback

logger = logging.getLogger(__name__)

CPN_STEP_LIST = [
    _("Choose location"),
    _("Demand load profile selection"),
    _("Possible scenarios selection"),
    _("Selected scenario parameters"),
    _("Simulation"),
]


@require_http_methods(["GET"])
def home_cpn(request):
    return render(request, "cp_nigeria/landing_page.html")


@login_required
@require_http_methods(["GET", "POST"])
def cpn_scenario_create(request, proj_id, scen_id=None, step_id=1):
    if request.POST:
        form = CPNLocationForm(request.POST)
        if form.is_valid():
            logger.info(f"Creating new project.")

            project = Project.objects.create(
                name=form.cleaned_data["name"],
                longitude=form.cleaned_data["longitude"],
                latitude=form.cleaned_data["latitude"],
                user=request.user,
            )
            return HttpResponseRedirect(reverse("cpn_review", args=[project.id]))
    else:
        form = CPNLocationForm()
    return render(request, f"cp_nigeria/steps/scenario_step{step_id}.html",
                  {"form": form,
                   "proj_id": proj_id,
                   "step_id": step_id,
                   "scen_id": scen_id,
                   "step_list": CPN_STEP_LIST})


@login_required
@require_http_methods(["GET", "POST"])
def cpn_demand_params(request, proj_id, scen_id=None, step_id=2):
    if request.POST:
        form = CPNLoadProfileForm(request.POST)
        form2 = CPNLoadProfileForm(request.POST)
    else:
        form = CPNLoadProfileForm()
        form2 = CPNLoadProfileForm()
    return render(request, f"cp_nigeria/steps/scenario_step{step_id}.html",
                  {"form": form,
                   "form2": form2,
                   "proj_id": proj_id,
                   "step_id": step_id,
                   "scen_id": scen_id,
                   "step_list": CPN_STEP_LIST})


@login_required
@require_http_methods(["GET", "POST"])
def cpn_scenario(request, proj_id, scen_id, step_id=3):
    return render(request, f"cp_nigeria/steps/scenario_step{step_id}.html",
                  {"proj_id": proj_id,
                   "step_id": step_id,
                   "scen_id": scen_id,
                   "step_list": CPN_STEP_LIST})


@login_required
@require_http_methods(["GET", "POST"])
def cpn_constraints(request, proj_id, scen_id, step_id=4):
    return render(request, f"cp_nigeria/steps/scenario_step{step_id}.html",
                  {"proj_id": proj_id,
                   "step_id": step_id,
                   "scen_id": scen_id,
                   "step_list": CPN_STEP_LIST})


@login_required
@require_http_methods(["GET", "POST"])
def cpn_review(request, proj_id, scen_id, step_id=5):
    scenario = get_object_or_404(Scenario, pk=scen_id)

    if (scenario.project.user != request.user) and (
            request.user not in scenario.project.viewers.all()
    ):
        raise PermissionDenied

    if request.method == "GET":
        html_template = f"cp_nigeria/steps/simulation/no-status.html"
        context = {
            "scenario": scenario,
            "scen_id": scen_id,
            "proj_id": proj_id,
            "proj_name": scenario.project.name,
            "step_id": step_id,
            "step_list": CPN_STEP_LIST,
            "MVS_GET_URL": MVS_GET_URL,
            "MVS_LP_FILE_URL": MVS_LP_FILE_URL,
        }

        qs = Simulation.objects.filter(scenario_id=scen_id)

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


# TODO for later create those views instead of simply serving the html templates
CPN_STEPS = [
    cpn_scenario_create,
    cpn_demand_params,
    cpn_scenario,
    cpn_constraints,
    cpn_review,
]


@login_required
@require_http_methods(["GET"])
def cpn_steps(request, proj_id, step_id=None, scen_id=None):
    if request.method == "GET":
        if step_id is None:
            return HttpResponseRedirect(reverse("cpn_steps", args=[proj_id, 1]))

        return CPN_STEPS[step_id - 1](request, proj_id, scen_id, step_id)
