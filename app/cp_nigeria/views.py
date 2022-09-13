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


logger = logging.getLogger(__name__)


CPN_STEP_LIST = [
    _("Demand load profile selection"),
    _("Possible scenarios selection"),
    _("Simulation constraints"),
    _("Simulation"),
]


@require_http_methods(["GET"])
def home_cpn(request):
    if request.user.is_authenticated:
        return render(request, "cp_nigeria/landing_page.html")

    else:
        return render(request, "cp_nigeria/index_cpn.html")

# TODO for later create those views instead of simply serving the html templates
# CPN_STEPS = [
#     scenario_create_parameters,
#     scenario_create_topology,
#     scenario_create_constraints,
#     scenario_review,
# ]


@login_required
@require_http_methods(["GET"])
def cpn_steps(request, proj_id, step_id=None, scen_id=None):
    if request.method == "GET":
        if step_id is None:
            return HttpResponseRedirect(reverse("scenario_steps", args=[proj_id, 1]))
        if step_id < len(CPN_STEP_LIST):
            return render(request,f"cp_nigeria/steps/scenario_step{step_id}.html", {"proj_id": proj_id, "scen_id": 1, "step_list": CPN_STEP_LIST, "step_id": step_id, "max_step":1+len(CPN_STEP_LIST)+1})
        else:
            return HttpResponseRedirect(reverse("cpn_review", args=[proj_id, 1]))
        # return CPN_STEPS[step_id - 1](request, proj_id, scen_id, step_id)


@login_required
@require_http_methods(["GET", "POST"])
def cpn_review(request, proj_id, scen_id, step_id=4, max_step=5):

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
            "proj_id": scenario.project.id,
            "proj_name": scenario.project.name,
            "step_id": step_id,
            "step_list": CPN_STEP_LIST,
            "max_step": max_step,
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


