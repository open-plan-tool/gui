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
from .requests import (
    mvs_simulation_request,
    fetch_mvs_simulation_results,
    mvs_sensitivity_analysis_request,
    fetch_mvs_sa_results,
)
from projects.models import *
from .scenario_topology_helpers import (
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
from .constants import DONE, PENDING, ERROR, MODIFIED
from .services import (
    create_or_delete_simulation_scheduler,
    excuses_design_under_development,
    send_feedback_email,
    get_selected_scenarios_in_cache,
)
import traceback

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def not_implemented(request):
    """Function returns a message"""
    redirect_name = request.GET.get("url")
    excuses_design_under_development(request, link=True)

    return redirect(redirect_name)


@require_http_methods(["GET"])
def home(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse("project_search"))
    else:
        return render(request, "index.html")


@login_required
@require_http_methods(["POST"])
def scenario_upload(request, proj_id):

    # read the scenario file to a dict
    scenario_data = request.FILES["file"].read()
    scenario_data = json.loads(scenario_data)

    project = get_object_or_404(Project, id=proj_id)

    if project.user != request.user:
        raise PermissionDenied

    new_scenario_name = request.POST.get("name")

    # make a single scenario within a list
    if isinstance(scenario_data, list) is False:
        scenario_data = [scenario_data]

    # load each of the scenario from the file into the database
    n_scenarios = len(scenario_data)
    for i, scen in enumerate(scenario_data):
        if new_scenario_name != "":
            if n_scenarios > 1:
                scen["name"] = f"{new_scenario_name}_{i+1}"
            else:
                scen["name"] = new_scenario_name

        scen_id = load_scenario_from_dict(scen, user=request.user, project=project)

    return HttpResponseRedirect(reverse("project_search", args=[proj_id, scen_id]))


# region Project


@login_required
@require_http_methods(["GET", "POST"])
def user_feedback(request):
    form = FeedbackForm(request.POST or None)
    if request.POST:
        if form.is_valid():
            feedback = form.save(commit=False)
            try:
                feedback.rating = [
                    key.split("-")[-1]
                    for key in request.POST.keys()
                    if key.startswith("rating")
                ][0]
            except:
                feedback.rating = None
            feedback.save()
            subject = f"[open_plan] Feedback for open_plan tool - {feedback.subject}"
            body = f"Feedback form for open_plan tool online api\n\nReceived Feedback\n-----------------\n\nTopic: {feedback.subject}\nContent: {feedback.feedback}\n\nInformation about sender\n------------------------\nName: {feedback.name}\n E-mail Address: {feedback.email}"
            try:
                send_feedback_email(subject, body)
                messages.success(request, f"Thank you for your feedback.")
            except Exception as e:
                messages.success(request, e)
            return HttpResponseRedirect(reverse("project_search"))
    return render(request, "feedback.html", {"form": form})


@login_required
@json_view
@require_http_methods(["GET"])
def project_members_list(request, proj_id):
    project = get_object_or_404(Project, pk=proj_id)

    if project.user != request.user:
        return JsonResponse(
            {"status": "error", "message": "Project does not belong to you."},
            status=403,
            content_type="application/json",
        )

    viewers = project.viewers.values_list("email", flat=True)
    return JsonResponse(
        {"status": "success", "viewers": list(viewers)},
        status=201,
        content_type="application/json",
    )


@login_required
@require_http_methods(["POST"])
def project_share(request, proj_id):
    qs = request.POST

    project = get_object_or_404(Project, id=proj_id)

    if project.user != request.user:
        raise PermissionDenied

    form_item = ProjectShareForm(qs)

    if form_item.is_valid():
        success, message = project.add_viewer_if_not_exist(**form_item.cleaned_data)
        if success is True:
            messages.success(request, message)
        else:
            messages.error(request, message)

    return HttpResponseRedirect(reverse("project_search", args=[proj_id]))


@login_required
@json_view
@require_http_methods(["POST"])
def project_revoke_access(request, proj_id=None):
    qs = request.POST

    project = get_object_or_404(Project, id=proj_id)

    if project.user != request.user:
        raise PermissionDenied
    form_item = ProjectRevokeForm(qs, proj_id=proj_id)
    if form_item.is_valid():
        success, message = project.revoke_access(**form_item.cleaned_data)
        if success is True:
            messages.success(request, message)
        else:
            messages.error(request, message)

    return HttpResponseRedirect(reverse("project_search", args=[proj_id]))


@login_required
@json_view
@require_http_methods(["POST"])
def ajax_project_viewers_form(request):

    if request.is_ajax():
        proj_id = int(request.POST.get("proj_id"))
        project = get_object_or_404(Project, id=proj_id)

        if project.user != request.user:
            raise PermissionDenied
        form_item = ProjectRevokeForm(proj_id=proj_id)

        return render(
            request,
            "project/project_viewers_form.html",
            context={"form_item": form_item},
        )


@login_required
@require_http_methods(["GET"])
def project_detail(request, proj_id):
    project = get_object_or_404(Project, pk=proj_id)

    if (project.user != request.user) and (request.user not in project.viewers.all()):
        raise PermissionDenied

    logger.info(f"Populating project and economic details in forms.")
    project_form = ProjectDetailForm(None, instance=project)
    economic_data_form = EconomicDataDetailForm(None, instance=project.economic_data)

    return render(
        request,
        "project/project_detail.html",
        {"project_form": project_form, "economic_data_form": economic_data_form},
    )


@login_required
@require_http_methods(["GET", "POST"])
def project_create(request):
    if request.POST:
        form = ProjectCreateForm(request.POST)
        if form.is_valid():
            logger.info(f"Creating new project with economic data.")
            economic_data = EconomicData.objects.create(
                duration=form.cleaned_data["duration"],
                currency=form.cleaned_data["currency"],
                discount=form.cleaned_data["discount"],
                tax=form.cleaned_data["tax"],
            )

            project = Project.objects.create(
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
                country=form.cleaned_data["country"],
                longitude=form.cleaned_data["longitude"],
                latitude=form.cleaned_data["latitude"],
                user=request.user,
                economic_data=economic_data,
            )
            return HttpResponseRedirect(reverse("project_search", args=[project.id]))
    else:
        form = ProjectCreateForm()
    return render(request, "project/project_create.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def project_update(request, proj_id):
    project = get_object_or_404(Project, id=proj_id)

    if project.user != request.user:
        raise PermissionDenied
        # return HttpResponseForbidden()

    project_form = ProjectUpdateForm(request.POST or None, instance=project)
    economic_data_form = EconomicDataUpdateForm(
        request.POST or None, instance=project.economic_data
    )

    if (
        request.method == "POST"
        and project_form.is_valid()
        and economic_data_form.is_valid()
    ):
        logger.info(f"Updating project with economic data...")
        project_form.save()
        economic_data_form.save()
        # Save was successful, so send message
        messages.success(request, "Project Info updated successfully!")
        return HttpResponseRedirect(reverse("project_search", args=[proj_id]))

    return render(
        request,
        "project/project_update.html",
        {"project_form": project_form, "economic_data_form": economic_data_form},
    )


@login_required
@require_http_methods(["GET", "POST"])
def project_export(request, proj_id):

    project = get_object_or_404(Project, id=proj_id)

    if project.user != request.user:
        raise PermissionDenied

    if request.method == "POST":
        bind_scenario_data = request.POST.get("bind_scenario_data", True)
        if bind_scenario_data == "True":
            bind_scenario_data = True
        if bind_scenario_data == "False":
            bind_scenario_data = False
    else:
        bind_scenario_data = True

    if project.user != request.user:
        raise PermissionDenied

    response = HttpResponse(
        json.dumps(project.export(bind_scenario_data=bind_scenario_data)),
        content_type="application/json",
    )
    response["Content-Disposition"] = f"attachment; filename=project{project.id}.json"
    return response


@login_required
@require_http_methods(["POST"])
def project_upload(request):

    # read the project file to a dict
    project_data = request.FILES["file"].read()
    project_data = json.loads(project_data)

    new_project_name = request.POST.get("name")

    if new_project_name != "":
        project_data["name"] = new_project_name

    proj_id = load_project_from_dict(project_data, request.user)

    return HttpResponseRedirect(reverse("project_search", args=[proj_id]))


@login_required
@require_http_methods(["POST"])
def project_from_usecase(request):
    usecase_id = request.POST.get("usecase", None)
    if usecase_id is not None:
        usecase_id = int(usecase_id)
    else:
        usecase_id = 0
    usecase = get_object_or_404(UseCase, id=usecase_id)
    proj_id = usecase.assign(request.user)

    return HttpResponseRedirect(reverse("project_search", args=[proj_id]))


@login_required
@require_http_methods(["POST"])
def project_delete(request, proj_id):
    project = get_object_or_404(Project, id=proj_id)

    if project.user != request.user:
        raise PermissionDenied

    if request.method == "POST":
        project.delete()
        messages.success(request, "Project successfully deleted!")

    return HttpResponseRedirect(reverse("project_search"))


@login_required
@require_http_methods(["GET"])
def project_search(request, proj_id=None, scen_id=None):
    # project_list = Project.objects.filter(user=request.user)
    # shared_project_list = Project.objects.filter(viewers=request.user)
    combined_projects_list = Project.objects.filter(
        Q(user=request.user) | Q(viewers__user=request.user)
    ).distinct()

    scenario_upload_form = UploadFileForm(
        labels=dict(name=_("New scenario name"), file=_("Scenario file"))
    )
    project_upload_form = UploadFileForm(
        labels=dict(name=_("New project name"), file=_("Project file"))
    )
    project_share_form = ProjectShareForm()
    project_revoke_form = ProjectRevokeForm(proj_id=proj_id)
    usecase_form = UseCaseForm(
        usecase_qs=UseCase.objects.all(), usecase_url=reverse("usecase_search")
    )

    return render(
        request,
        "project/project_search.html",
        {
            "project_list": combined_projects_list,
            "proj_id": proj_id,
            "scen_id": scen_id,
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
def project_duplicate(request, proj_id):
    """Duplicates the selected project along with its associated scenarios"""
    project = get_object_or_404(Project, pk=proj_id)

    # duplicate the project
    dm = project.export(bind_scenario_data=True)
    new_proj_id = load_project_from_dict(dm, user=project.user)

    return HttpResponseRedirect(reverse("project_search", args=[new_proj_id]))


# endregion Project

# region Usecase
@login_required
@require_http_methods(["GET"])
def usecase_search(request, usecase_id=None, scen_id=None):

    usecase_list = UseCase.objects.all()

    print(usecase_list)

    return render(
        request,
        "usecase/usecase_search.html",
        {
            "usecase_list": usecase_list,
            "usecase_id": usecase_id,
            "scen_id": scen_id,
            "translated_text": {
                "showScenarioText": _("Show scenarios"),
                "hideScenarioText": _("Hide scenarios"),
            },
        },
    )


# endregion Usecase

# region Comment


@login_required
@require_http_methods(["GET", "POST"])
def comment_create(request, proj_id):
    project = get_object_or_404(Project, pk=proj_id)

    if request.POST:
        form = CommentForm(request.POST)
        if form.is_valid():
            Comment.objects.create(
                name=form.cleaned_data["name"],
                body=form.cleaned_data["body"],
                project=project,
            )
            return HttpResponseRedirect(reverse("scenario_search", args=[proj_id, 1]))

    else:  # GET
        form = CommentForm()

    return render(request, "comment/comment_create.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def comment_update(request, com_id):
    comment = get_object_or_404(Comment, pk=com_id)

    if comment.project.user != request.user:
        raise PermissionDenied

    if request.POST:
        form = CommentForm(request.POST)
        if form.is_valid():
            comment.name = form.cleaned_data["name"]
            comment.body = form.cleaned_data["body"]
            comment.save()
            return HttpResponseRedirect(
                reverse("scenario_search", args=[comment.project.id, 1])
            )
    else:  # GET
        form = CommentForm(instance=comment)

    return render(request, "comment/comment_update.html", {"form": form})


@login_required
@require_http_methods(["POST"])
def comment_delete(request, com_id):
    comment = get_object_or_404(Comment, pk=com_id)

    if comment.project.user != request.user:
        raise PermissionDenied

    if request.POST:
        comment.delete()
        messages.success(request, "Comment successfully deleted!")
        return HttpResponseRedirect(
            reverse("scenario_search", args=[comment.project.id, 1])
        )


# endregion Comment


# region Scenario


@login_required
@require_http_methods(["GET"])
def scenario_search(request, proj_id, show_comments=0):
    """
    This view renders the scenarios and comments search html template.

    args: proj_id, show_comments
    proj_id: The Project id the user requests to observe associated scenarios and comments.
    show_comments: An integer flag to indicate wether the page will open on scenarios tab or comments tab.
    If show_comments==1 the html page will load and following a click event will change the active tab to comments.
    Otherwise the default scenarios tab will be presented to the user.

    Returns: A rendered html template.
    """
    project = get_object_or_404(Project, pk=proj_id)
    return render(
        request,
        "scenario/scenario_search.html",
        {
            "comment_list": project.comment_set.all(),
            "scenarios_list": project.scenario_set.all(),
            "project": project,
            "show_comments": show_comments,
        },
    )


STEP_LIST = [
    _("Scenario Setup"),
    _("Energy system design"),
    _("Constraints"),
    _("Simulation"),
]


@login_required
@require_http_methods(["GET", "POST"])
def scenario_select_project(request, step_id=0, max_step=1):
    user_projects = request.user.project_set.all()
    if request.method == "GET":

        if user_projects.exists():
            form = ScenarioSelectProjectForm(project_queryset=user_projects)
            answer = render(
                request,
                f"scenario/scenario_step{step_id}.html",
                {
                    "form": form,
                    "step_id": step_id,
                    "step_list": [_("Project selection")] + STEP_LIST,
                    "max_step": max_step,
                },
            )
        else:
            messages.info(
                request, _("You have currently no projects, please create one first")
            )
            answer = HttpResponseRedirect(reverse("project_search"))

    elif request.method == "POST":
        form = ScenarioSelectProjectForm(request.POST, project_queryset=user_projects)

        if form.is_valid():
            proj_id = form.cleaned_data.get("project").id
            answer = HttpResponseRedirect(
                reverse("scenario_create_parameters", args=[proj_id])
            )

    return answer


@login_required
@require_http_methods(["GET", "POST"])
def scenario_create_parameters(request, proj_id, scen_id=None, step_id=1, max_step=2):

    project = get_object_or_404(Project, pk=proj_id)
    # all projects which the user is able to select (the one the user created)
    user_projects = request.user.project_set.all()

    form = ScenarioCreateForm(
        initial={"project": project}, project_queryset=user_projects
    )
    if scen_id == "None":
        scen_id = None

    if request.method == "GET":
        if scen_id is not None:
            scenario = get_object_or_404(Scenario, id=scen_id)

            if (scenario.project.user != request.user) and (
                request.user not in scenario.project.viewers.all()
            ):
                raise PermissionDenied

            form = ScenarioUpdateForm(
                None, instance=scenario, project_queryset=user_projects
            )

            # if a simulation object linked to this scenario exists, all steps have been already fullfilled
            qs_sim = Simulation.objects.filter(scenario=scenario)
            if qs_sim.exists():
                max_step = 5
            else:
                # if a connexion object linked to this scenario exists, topology has already been saved once
                qs_topo = ConnectionLink.objects.filter(scenario_id=scen_id)
                if qs_topo.exists():
                    max_step = 3
        else:
            scenario = None
        answer = render(
            request,
            f"scenario/scenario_step{step_id}.html",
            {
                "form": form,
                "proj_id": proj_id,
                "proj_name": project.name,
                "scenario": scenario,
                "scen_id": scen_id,
                "step_id": step_id,
                "step_list": STEP_LIST,
                "max_step": max_step,
            },
        )

    elif request.method == "POST":

        form = ScenarioCreateForm(request.POST, project_queryset=user_projects)

        if form.is_valid():
            if scen_id is None:
                scenario = Scenario()
            else:
                scenario = Scenario.objects.get(id=scen_id)

            qs_sim = Simulation.objects.filter(scenario=scenario)
            # update the parameter values which are different from existing values
            for name, value in form.cleaned_data.items():
                if getattr(scenario, name) != value:
                    setattr(scenario, name, value)
                    if qs_sim.exists():
                        qs_sim.update(status=MODIFIED)

            # update the project associated to the scenario
            proj_id = scenario.project.id
            scenario.save()
            answer = HttpResponseRedirect(
                reverse("scenario_create_topology", args=[proj_id, scenario.id])
            )

    return answer


@login_required
@require_http_methods(["GET", "POST"])
def scenario_create_topology(request, proj_id, scen_id, step_id=2, max_step=3):

    components = {
        "providers": {
            "dso": _("Electricity DSO"),
            "gas_dso": _("Gas DSO"),
            "h2_dso": _("H2 DSO"),
            "heat_dso": _("Heat DSO"),
        },
        "production": {
            "pv_plant": _("PV Plant"),
            "wind_plant": _("Wind Plant"),
            "biogas_plant": _("Biogas Plant"),
            "geothermal_conversion": _("Geothermal Conversion"),
            "solar_thermal_plant": _("Solar Thermal Plant"),
        },
        "conversion": {
            "transformer_station_in": _("Transformer Station (in)"),  #
            "transformer_station_out": _("Transformer Station (out)"),  #
            "storage_charge_controller_in": _("Storage Charge Controller (in)"),  #
            "storage_charge_controller_out": _("Storage Charge Controller (out)"),  #
            "solar_inverter": _("Solar Inverter"),  #
            "diesel_generator": _("Diesel Generator"),
            "fuel_cell": _(" Fuel Cell"),
            "gas_boiler": _("Gas Boiler"),
            "electrolyzer": _("Electrolyzer"),
            "heat_pump": _("Heat Pump"),
            "chp": _("Combined Heat and Power"),
            "chp_fixed_ratio": _("CHP fixed ratio"),
        },
        "storage": {
            "bess": _("Electricity Storage"),
            # "gess": _("Gas Storage"),
            # "h2ess": _("H2 Storage"),
            "hess": _("Heat Storage"),
        },
        "demand": {
            "demand": _("Electricity Demand"),
            # "gas_demand": _("Gas Demand"),
            # "h2_demand": _("H2 Demand"),
            "heat_demand": _("Heat Demand"),
        },
        "bus": {"bus": _("Bus")},
    }
    group_names = {group: _(group) for group in components.keys()}

    # TODO: if the scenario exists, load it, otherwise default form

    if request.method == "POST":
        # called by function save_topology() in templates/scenario/scenario_step2.html

        scenario = get_object_or_404(Scenario, pk=scen_id)
        if request.user != scenario.project.user:
            raise PermissionDenied

        topologies = json.loads(request.body)
        node_list = [NodeObject(topology) for topology in topologies]

        # delete objects from database which were deleted by the user
        update_deleted_objects_from_database(scen_id, node_list)
        # Make sure there are no connections in the Database to prevent inserting the same connections upon updating.
        ConnectionLink.objects.filter(scenario_id=scen_id).delete()
        for node_obj in node_list:
            node_obj.create_connection_links(scen_id)
            # node_obj.assign_asset_to_proper_group(node_to_db_mapping_dict)
        return JsonResponse({"success": True}, status=200)
    else:

        scenario = get_object_or_404(Scenario, pk=scen_id)

        # if a simulation object linked to this scenario exists, all steps have been already fullfilled
        qs_sim = Simulation.objects.filter(scenario=scenario)
        if qs_sim.exists():
            max_step = 5

        # this is a dict with keys "busses", "assets" and "links"
        topology_data_list = load_scenario_topology_from_db(scen_id)
        return render(
            request,
            f"scenario/scenario_step{step_id}.html",
            {
                "scenario": scenario,
                "scen_id": scen_id,
                "proj_id": scenario.project.id,
                "proj_name": scenario.project.name,
                "topology_data_list": json.dumps(topology_data_list),
                "step_id": step_id,
                "step_list": STEP_LIST,
                "max_step": max_step,
                "components": components,
                "group_names": group_names,
            },
        )


@login_required
@require_http_methods(["GET", "POST"])
def scenario_create_constraints(request, proj_id, scen_id, step_id=3, max_step=4):

    constraints_labels = {
        "minimal_degree_of_autonomy": _("Minimal degree of autonomy"),
        "minimal_renewable_factor": _("Minimal share of renewables"),
        "maximum_emissions": _("Maximal CO2 emissions"),
        "net_zero_energy": _("Net zero energy system"),
    }
    constraints_forms = {
        "minimal_degree_of_autonomy": MinDOAConstraintForm,
        "minimal_renewable_factor": MinRenewableConstraintForm,
        "maximum_emissions": MaxEmissionConstraintForm,
        "net_zero_energy": NZEConstraintForm,
    }

    constraints_models = {
        "minimal_degree_of_autonomy": MinDOAConstraint,
        "minimal_renewable_factor": MinRenewableConstraint,
        "maximum_emissions": MaxEmissionConstraint,
        "net_zero_energy": NZEConstraint,
    }

    scenario = get_object_or_404(Scenario, pk=scen_id)

    if (scenario.project.user != request.user) and (
        request.user not in scenario.project.viewers.all()
    ):
        raise PermissionDenied

    qs_sim = Simulation.objects.filter(scenario=scenario)

    if request.method == "GET":

        # if a simulation object linked to this scenario exists, all steps have been already fullfilled
        if qs_sim.exists():
            max_step = 5

        # prepare the forms for each constraint
        unbound_forms = {}
        for constraint_type, constraint_form in constraints_forms.items():
            # check whether the constraint is already associated to the scenario
            qs = constraints_models[constraint_type].objects.filter(scenario=scenario)
            if qs.exists():
                unbound_forms[constraint_type] = constraint_form(
                    prefix=constraint_type, instance=qs[0]
                )
            else:
                unbound_forms[constraint_type] = constraint_form(prefix=constraint_type)
        return render(
            request,
            f"scenario/scenario_step{step_id}.html",
            {
                "scenario": scenario,
                "scen_id": scen_id,
                "proj_id": scenario.project.id,
                "proj_name": scenario.project.name,
                "step_id": step_id,
                "step_list": STEP_LIST,
                "max_step": max_step,
                "forms": unbound_forms,
                "forms_labels": constraints_labels,
            },
        )
    elif request.method == "POST":
        for constraint_type, form_model in constraints_forms.items():
            form = form_model(request.POST, prefix=constraint_type)

            if form.is_valid():
                # check whether the constraint is already associated to the scenario
                qs = constraints_models[constraint_type].objects.filter(
                    scenario=scenario
                )
                if qs.exists():
                    if len(qs) == 1:
                        constraint_instance = qs[0]
                        for name, value in form.cleaned_data.items():
                            if getattr(constraint_instance, name) != value:
                                setattr(constraint_instance, name, value)
                                if qs_sim.exists():
                                    qs_sim.update(status=MODIFIED)

                else:
                    constraint_instance = form.save(commit=False)
                    constraint_instance.scenario = scenario

                if constraint_type == "net_zero_energy":
                    constraint_instance.value = constraint_instance.activated

                constraint_instance.save()

        return HttpResponseRedirect(reverse("scenario_review", args=[proj_id, scen_id]))


@login_required
@require_http_methods(["GET", "POST"])
def scenario_review(request, proj_id, scen_id, step_id=4, max_step=5):

    scenario = get_object_or_404(Scenario, pk=scen_id)

    if (scenario.project.user != request.user) and (
        request.user not in scenario.project.viewers.all()
    ):
        raise PermissionDenied

    if request.method == "GET":
        html_template = f"scenario/simulation/no-status.html"
        context = {
            "scenario": scenario,
            "scen_id": scen_id,
            "proj_id": scenario.project.id,
            "proj_name": scenario.project.name,
            "step_id": step_id,
            "step_list": STEP_LIST,
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
                html_template = "scenario/simulation/error.html"
            elif simulation.status == PENDING:
                html_template = "scenario/simulation/pending.html"
            elif simulation.status == DONE:
                html_template = "scenario/simulation/success.html"

        else:
            print("no simulation existing")

        return render(request, html_template, context)


@login_required
@require_http_methods(["GET"])
def back_to_scenario_review(request, proj_id):

    selected_scenario = get_selected_scenarios_in_cache(request, proj_id)

    if len(selected_scenario) >= 1:
        scen_id = selected_scenario[0]
        answer = scenario_review(request, proj_id, scen_id)
    else:
        messages.error(
            request,
            _(
                "No scenario was available in the cache, try refreshing the page and make sure one scenario is selected."
            ),
        )
        answer = HttpResponseRedirect(request.headers.get("Referer"))

    return answer


SCENARIOS_STEPS = [
    scenario_create_parameters,
    scenario_create_topology,
    scenario_create_constraints,
    scenario_review,
]


@login_required
@require_http_methods(["GET"])
def scenario_steps(request, proj_id, step_id=None, scen_id=None):
    if request.method == "GET":
        if step_id is None:
            return HttpResponseRedirect(reverse("scenario_steps", args=[proj_id, 1]))

        return SCENARIOS_STEPS[step_id - 1](request, proj_id, scen_id, step_id)


# TODO delete this useless code here
@login_required
@require_http_methods(["GET"])
def scenario_view(request, scen_id, step_id):
    """Scenario View. GET request only."""
    scenario = get_object_or_404(Scenario, pk=scen_id)

    if (scenario.project.user != request.user) and (
        request.user not in scenario.project.viewers.all()
    ):
        raise PermissionDenied

    return HttpResponseRedirect(reverse("project_search", args=[scenario.project.id]))


# TODO delete this useless code here
@login_required
@require_http_methods(["GET"])
def scenario_update(request, scen_id, step_id):
    """Scenario Update View. POST request only."""
    scenario = get_object_or_404(Scenario, pk=scen_id)
    if scenario.project.user != request.user:
        raise PermissionDenied
    if request.POST:
        form = ScenarioUpdateForm(request.POST)
        if form.is_valid():
            [
                setattr(scenario, name, value)
                for name, value in form.cleaned_data.items()
            ]
            scenario.save(update_fields=form.cleaned_data.keys())
            return HttpResponseRedirect(
                reverse("project_search", args=[scenario.project.id])
            )
    else:
        raise Http404("An error occurred while updating the Scenario.")


@login_required
@require_http_methods(["GET"])
def scenario_duplicate(request, scen_id):
    """duplicates the selected scenario and all of its associated components (topology data included)"""
    scenario = get_object_or_404(Scenario, pk=scen_id)

    if scenario.project.user != request.user:
        raise PermissionDenied

    # We need to iterate over all the objects related to this scenario and duplicate them
    # and associate them with the new scenario id.
    asset_list = Asset.objects.filter(scenario=scenario)
    bus_list = Bus.objects.filter(scenario=scenario)
    connections_list = ConnectionLink.objects.filter(scenario=scenario)
    # simulation_list = Simulation.objects.filter(scenario=scenario)

    # first duplicate the scenario
    scenario.pk = None
    scenario.save()
    # from now on we are working with the duplicated scenario, not the original
    old2new_asset_ids_map = duplicate_scenario_objects(asset_list, scenario)
    old2new_bus_ids_map = duplicate_scenario_objects(
        bus_list, scenario, old2new_asset_ids_map
    )
    duplicate_scenario_connections(
        connections_list, scenario, old2new_asset_ids_map, old2new_bus_ids_map
    )
    # duplicate_scenario_objects(simulation_list, scenario)

    return HttpResponseRedirect(reverse("project_search", args=[scenario.project.id]))


@login_required
@require_http_methods(["POST"])
def scenario_export(request, proj_id):
    response = HttpResponseRedirect(reverse("project_search", args=[proj_id]))

    # get the selected scenarios under the project view and export them into a file
    scenario_ids = request.POST.get("scenario_ids")
    if scenario_ids is not None:
        scenario_ids = json.loads(scenario_ids)
        scenario_data = []
        for scen_id in scenario_ids:
            scenario = get_object_or_404(Scenario, id=int(scen_id))
            scenario_data.append(scenario.export(bind_project_data=True))
        response = HttpResponse(
            json.dumps(scenario_data), content_type="application/json"
        )
        response["Content-Disposition"] = "attachment; filename=scenario.json"
    return response


@login_required
@require_http_methods(["POST"])
def scenario_delete(request, scen_id):
    scenario = get_object_or_404(Scenario, id=scen_id)
    if scenario.project.user != request.user:
        logger.warning(
            f"Unauthorized user tried to delete project scenario with db id = {scen_id}."
        )
        raise PermissionDenied
    if request.POST:
        scenario.delete()
        messages.success(request, "scenario successfully deleted!")
        return HttpResponseRedirect(
            reverse("project_search", args=[scenario.project.id])
        )


# endregion Scenario


@login_required
@require_http_methods(["GET", "POST"])
def sensitivity_analysis_create(request, scen_id, sa_id=None, step_id=5):
    excuses_design_under_development(request)
    scenario = get_object_or_404(Scenario, id=scen_id)
    if scenario.project.user != request.user:
        raise PermissionDenied

    if request.method == "GET":
        if sa_id is not None:
            sa_item = get_object_or_404(SensitivityAnalysis, id=sa_id)
            sa_form = SensitivityAnalysisForm(scen_id=scen_id, instance=sa_item)
            sa_status = sa_item.status
            mvs_token = sa_item.mvs_token
        else:
            number_existing_sa = scenario.sensitivityanalysis_set.all().count()
            sa_item = None
            sa_status = None
            mvs_token = None
            sa_form = SensitivityAnalysisForm(
                scen_id=scen_id,
                initial={"name": f"sensitivity_analysis_{number_existing_sa + 1}"},
            )

        answer = render(
            request,
            "scenario/sensitivity_analysis.html",
            {
                "proj_id": scenario.project.id,
                "proj_name": scenario.project.name,
                "scenario": scenario,
                "scen_id": scen_id,
                "step_id": step_id,
                "step_list": STEP_LIST + [_("Sensitivity analysis")],
                "max_step": 5,
                "MVS_SA_GET_URL": MVS_SA_GET_URL,
                "sa_form": sa_form,
                "sa_status": sa_status,
                "sa_id": sa_id,
                "mvs_token": mvs_token,
            },
        )

    if request.method == "POST":
        qs = request.POST
        sa_form = SensitivityAnalysisForm(qs)

        if sa_form.is_valid():
            sa_item = sa_form.save(commit=False)
            # TODO if the reference value is not the same as in the current scenario, duplicate the scenario and bind the duplicate to sa_item
            # TODO check if the scenario is already bound to a SA
            sa_item.set_reference_scenario(scenario)
            try:
                data_clean = format_scenario_for_mvs(scenario)
            except Exception as e:
                error_msg = f"Scenario Serialization ERROR! User: {scenario.project.user.username}. Scenario Id: {scenario.id}. Thrown Exception: {e}."
                logger.error(error_msg)
                messages.error(request, error_msg)
                answer = JsonResponse(
                    {"error": f"Scenario Serialization ERROR! Thrown Exception: {e}."},
                    status=500,
                    content_type="application/json",
                )

            sa_item.save()

            # Add the information about the sensitivity analysis to the json
            data_clean.update(sa_item.payload)
            # Make simulation request to MVS
            response = mvs_sensitivity_analysis_request(data_clean)

        if response is None:
            error_msg = "Could not communicate with the simulation server."
            logger.error(error_msg)
            messages.error(request, error_msg)
            # TODO redirect to prefilled feedback form / bug form
            answer = JsonResponse(
                {"status": "error", "error": error_msg},
                status=407,
                content_type="application/json",
            )
        else:
            sa_item.mvs_token = response["id"] if response["id"] else None
            # import pdb; pdb.set_trace()
            # sa_item.parse_server_response(response)

            if "status" in response.keys() and (
                response["status"] == DONE or response["status"] == ERROR
            ):
                # TODO call method to fetch response here
                sa_item.status = response["status"]
                sa_item.response = response["results"]
                # Simulation.objects.filter(scenario_id=scen_id).delete()
                # TODO the reference scenario should have its simulation replaced by this one if successful, this can be done via the mvs_token of the simulation

                sa_item.end_date = datetime.now()
            else:  # PENDING
                sa_item.status = response["status"]
                # create a task which will update simulation status
                # TODO check it does the right thing with sensitivity analysis
                # create_or_delete_simulation_scheduler(mvs_token=sa_item.mvs_token)

            sa_item.elapsed_seconds = (datetime.now() - sa_item.start_date).seconds
            sa_item.save()
            answer = HttpResponseRedirect(
                reverse("sensitivity_analysis_review", args=[scen_id, sa_item.id])
            )

    return answer


# region Asset


@login_required
@require_http_methods(["GET"])
def get_asset_create_form(request, scen_id=0, asset_type_name="", asset_uuid=None):
    scenario = Scenario.objects.get(id=scen_id)

    # collect the information about the connected nodes in the GUI
    input_output_mapping = {
        "inputs": json.loads(request.POST.get("inputs", "[]")),
        "outputs": json.loads(request.POST.get("outputs", "[]")),
    }

    if asset_type_name == "bus":
        if asset_uuid:
            existing_bus = get_object_or_404(Bus, pk=asset_uuid)
            form = BusForm(asset_type=asset_type_name, instance=existing_bus)
        else:
            bus_list = Bus.objects.filter(scenario=scenario)
            n_bus = len(bus_list)
            default_name = f"{asset_type_name}-{n_bus}"
            form = BusForm(asset_type=asset_type_name, initial={"name": default_name})
        return render(request, "asset/bus_create_form.html", {"form": form})

    elif asset_type_name in ["bess", "h2ess", "gess", "hess"]:
        if asset_uuid:
            existing_ess_asset = get_object_or_404(Asset, unique_id=asset_uuid)
            ess_asset_children = Asset.objects.filter(
                parent_asset=existing_ess_asset.id
            )
            ess_capacity_asset = ess_asset_children.get(
                asset_type__asset_type="capacity"
            )
            ess_charging_power_asset = ess_asset_children.get(
                asset_type__asset_type="charging_power"
            )
            ess_discharging_power_asset = ess_asset_children.get(
                asset_type__asset_type="discharging_power"
            )
            # also get all child assets
            form = StorageForm(
                asset_type=asset_type_name,
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
                input_output_mapping=input_output_mapping,
            )
        else:
            form = StorageForm(
                asset_type=asset_type_name, input_output_mapping=input_output_mapping
            )
        return render(request, "asset/storage_asset_create_form.html", {"form": form})
    else:  # all other assets

        if asset_uuid:
            existing_asset = get_object_or_404(Asset, unique_id=asset_uuid)
            form = AssetCreateForm(
                asset_type=asset_type_name,
                instance=existing_asset,
                input_output_mapping=input_output_mapping,
            )
            input_timeseries_data = (
                existing_asset.input_timeseries
                if existing_asset.input_timeseries
                else ""
            )
        else:
            asset_list = Asset.objects.filter(
                asset_type__asset_type=asset_type_name, scenario=scenario
            )
            n_asset = len(asset_list)
            default_name = f"{asset_type_name}-{n_asset}"
            form = AssetCreateForm(
                asset_type=asset_type_name,
                initial={"name": default_name},
                input_output_mapping=input_output_mapping,
            )
            input_timeseries_data = ""

        context = {
            "form": form,
            "asset_type_name": asset_type_name,
            "input_timeseries_data": input_timeseries_data,
            "input_timeseries_timestamps": json.dumps(
                scenario.get_timestamps(json_format=True)
            ),
        }

        return render(request, "asset/asset_create_form.html", context)


@login_required
@require_http_methods(["POST"])
def asset_create_or_update(request, scen_id=0, asset_type_name="", asset_uuid=None):
    if asset_type_name == "bus":
        answer = handle_bus_form_post(request, scen_id, asset_type_name, asset_uuid)
    elif asset_type_name in ["bess", "h2ess", "gess", "hess"]:
        answer = handle_storage_unit_form_post(
            request, scen_id, asset_type_name, asset_uuid
        )
    else:  # all assets
        answer = handle_asset_form_post(request, scen_id, asset_type_name, asset_uuid)
    return answer


@login_required
@require_http_methods(["GET"])
def get_asset_cops_form(request, scen_id=0, asset_type_name="", asset_uuid=None):
    opts = {}
    if asset_uuid:
        existing_asset = get_object_or_404(Asset, unique_id=asset_uuid)
        existing_cop = COPCalculator.objects.filter(asset=existing_asset)
        if existing_cop.exists():
            opts["instance"] = existing_cop.get()
    context = {"form": COPCalculatorForm(**opts)}

    return render(request, "asset/asset_cops_form.html", context)


@login_required
@require_http_methods(["POST"])
def asset_cops_create_or_update(
    request, scen_id=0, asset_type_name="", asset_uuid=None
):
    # collect the information about the connected nodes in the GUI

    opts = {}
    if asset_uuid:
        existing_asset = get_object_or_404(Asset, unique_id=asset_uuid)
        existing_cop = COPCalculator.objects.filter(asset=existing_asset)
        if existing_cop.exists():
            opts["instance"] = existing_cop.get()
    form = COPCalculatorForm(request.POST, request.FILES, **opts)

    scenario = get_object_or_404(Scenario, id=scen_id)
    if form.is_valid():
        cop = form.save(commit=False)
        cop.scenario = scenario
        cop.mode = asset_type_name
        if asset_uuid:
            cop.asset = existing_asset
        cop.save()

        try:
            cops = cop.calc_cops()
            return JsonResponse(
                {"success": True, "cop_id": cop.id, "cops": json.dumps(cops)},
                status=200,
            )
        except:
            return JsonResponse({"success": False, "cop_id": cop.id}, status=422)
    else:
        import pdb

        pdb.set_trace()
    logger.warning(f"The submitted asset has erroneous field values.")

    form_html = get_template("asset/asset_cops_form.html")
    return JsonResponse(
        {"success": False, "form_html": form_html.render({"form": form})}, status=422
    )


# endregion Asset


# region MVS JSON Related


@json_view
@login_required
@require_http_methods(["GET"])
def view_mvs_data_input(request, scen_id=0):
    if scen_id == 0:
        return JsonResponse(
            {"status": "error", "error": "No scenario id provided"},
            status=500,
            content_type="application/json",
        )
    # Load scenario
    scenario = Scenario.objects.get(id=scen_id)

    if scenario.project.user != request.user:
        logger.warning(
            f"Unauthorized user tried to access scenario with db id = {scen_id}."
        )
        raise PermissionDenied

    try:
        data_clean = format_scenario_for_mvs(scenario)
    except Exception as e:

        logger.error(
            f"Scenario Serialization ERROR! User: {scenario.project.user.username}. Scenario Id: {scenario.id}. Thrown Exception: {traceback.format_exc()}."
        )
        return JsonResponse(
            {"error": f"Scenario Serialization ERROR! Thrown Exception: {e}."},
            status=500,
            content_type="application/json",
        )

    return JsonResponse(data_clean, status=200, content_type="application/json")


# End-point to send MVS simulation request
# @json_view
@login_required
@require_http_methods(["GET", "POST"])
def request_mvs_simulation(request, scen_id=0):
    if scen_id == 0:
        answer = JsonResponse(
            {"status": "error", "error": "No scenario id provided"},
            status=500,
            content_type="application/json",
        )
    # Load scenario
    scenario = Scenario.objects.get(pk=scen_id)
    try:
        data_clean = format_scenario_for_mvs(scenario)
        # err = 1/0
    except Exception as e:
        error_msg = f"Scenario Serialization ERROR! User: {scenario.project.user.username}. Scenario Id: {scenario.id}. Thrown Exception: {e}."
        logger.error(error_msg)
        messages.error(request, error_msg)
        answer = JsonResponse(
            {"error": f"Scenario Serialization ERROR! Thrown Exception: {e}."},
            status=500,
            content_type="application/json",
        )

    if request.method == "POST":
        output_lp_file = request.POST.get("output_lp_file", None)
        if output_lp_file == "on":
            data_clean["simulation_settings"]["output_lp_file"] = "true"

    # Make simulation request to MVS
    results = mvs_simulation_request(data_clean)

    if results is None:
        error_msg = "Could not communicate with the simulation server."
        logger.error(error_msg)
        messages.error(request, error_msg)
        # TODO redirect to prefilled feedback form / bug form
        answer = JsonResponse(
            {"status": "error", "error": error_msg},
            status=407,
            content_type="application/json",
        )
    else:

        # delete existing simulation
        Simulation.objects.filter(scenario_id=scen_id).delete()
        # Create empty Simulation model object
        simulation = Simulation(start_date=datetime.now(), scenario_id=scen_id)

        simulation.mvs_token = results["id"] if results["id"] else None

        if "status" in results.keys() and (
            results["status"] == DONE or results["status"] == ERROR
        ):
            simulation.status = results["status"]
            simulation.results = results["results"]
            simulation.end_date = datetime.now()
        else:  # PENDING
            simulation.status = results["status"]
            # create a task which will update simulation status
            create_or_delete_simulation_scheduler(mvs_token=simulation.mvs_token)

        simulation.elapsed_seconds = (datetime.now() - simulation.start_date).seconds
        simulation.save()

        answer = HttpResponseRedirect(
            reverse("scenario_review", args=[scenario.project.id, scen_id])
        )

    return answer


@json_view
@login_required
@require_http_methods(["POST"])
def update_simulation_rating(request):
    try:
        simulation = Simulation.objects.filter(
            scenario_id=request.POST["scen_id"]
        ).first()
        simulation.user_rating = request.POST["user_rating"]
        simulation.save()
        return JsonResponse(
            {"success": True}, status=200, content_type="application/json"
        )
    except Exception as e:
        return JsonResponse(
            {"success": False, "cause": str(e)},
            status=200,
            content_type="application/json",
        )


@json_view
@login_required
@require_http_methods(["GET"])
def fetch_simulation_results(request, sim_id):
    simulation = get_object_or_404(Simulation, id=sim_id)
    are_result_ready = fetch_mvs_simulation_results(simulation)
    return JsonResponse(
        dict(areResultReady=are_result_ready),
        status=200,
        content_type="application/json",
    )


@json_view
@login_required
@require_http_methods(["GET"])
def fetch_sensitivity_analysis_results(request, sa_id):
    sa_item = get_object_or_404(SensitivityAnalysis, id=sa_id)
    are_result_ready = fetch_mvs_sa_results(sa_item)
    return JsonResponse(
        dict(areResultReady=are_result_ready),
        status=200,
        content_type="application/json",
    )


@login_required
@require_http_methods(["GET"])
def simulation_cancel(request, scen_id):
    scenario = get_object_or_404(Scenario, id=scen_id)

    if scenario.project.user != request.user:
        raise PermissionDenied

    qs = Simulation.objects.filter(scenario=scen_id)
    if qs.exists():
        scenario.simulation.delete()

    return HttpResponseRedirect(
        reverse("scenario_review", args=[scenario.project.id, scen_id])
    )


# endregion MVS JSON Related
