from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _

from functools import wraps

from projects.models import Project, Scenario


def get_project_from_proj_or_scen_id(proj_id, scen_id):
    if proj_id is not None:
        return get_object_or_404(Project, pk=proj_id)

    if scen_id is not None:
        scenario = get_object_or_404(Scenario, pk=scen_id)
        return scenario.project

    raise ValueError("this decorator requires proj_id or scen_id")


def user_is_owner(view_func):
    @wraps(view_func)
    def _wrapped_view(request, proj_id=None, scen_id=None, *args, **kwargs):
        project = get_project_from_proj_or_scen_id(proj_id, scen_id)

        if project.user != request.user:
            reason = _("You need to be the owner of the project to access this.")
            return render(
                request,
                "error_403.html",
                {
                    "reason": reason,
                },
            )

        # check for existing parameters to handle the different view parameters
        if proj_id is not None and scen_id is not None:
            return view_func(request, proj_id, scen_id, *args, **kwargs)
        elif proj_id is not None:
            return view_func(request, proj_id, *args, **kwargs)
        elif scen_id is not None:
            return view_func(request, scen_id, *args, **kwargs)

    return _wrapped_view


def user_has_read_rights(view_func):
    @wraps(view_func)
    def _wrapped_view(request, proj_id=None, scen_id=None, *args, **kwargs):
        project = get_project_from_proj_or_scen_id(proj_id, scen_id)

        if (project.user != request.user) and (
            project.viewers.filter(user__email=request.user.email).exists() is False
        ):
            reason = _(
                "You need to be the owner of the project or have read rights to access this."
            )
            return render(
                request,
                "error_403.html",
                {
                    "reason": reason,
                },
            )

        # check for existing parameters to handle the different view parameters
        if proj_id is not None and scen_id is not None:
            return view_func(request, proj_id, scen_id, *args, **kwargs)
        elif proj_id is not None:
            return view_func(request, proj_id, *args, **kwargs)
        elif scen_id is not None:
            return view_func(request, scen_id, *args, **kwargs)

    return _wrapped_view


def user_has_edit_rights(view_func):
    @wraps(view_func)
    def _wrapped_view(request, proj_id=None, scen_id=None, *args, **kwargs):
        project = get_project_from_proj_or_scen_id(proj_id, scen_id)

        if (project.user != request.user) and (
            project.viewers.filter(
                user__email=request.user.email, share_rights="edit"
            ).exists()
            is False
        ):
            reason = _(
                "You need to be the owner of the project or have edit rights to access this."
            )
            return render(
                request,
                "error_403.html",
                {
                    "reason": reason,
                },
            )

        # check for existing parameters to handle the different view parameters
        if proj_id is not None and scen_id is not None:
            return view_func(request, proj_id, scen_id, *args, **kwargs)
        elif proj_id is not None:
            return view_func(request, proj_id, *args, **kwargs)
        elif scen_id is not None:
            return view_func(request, scen_id, *args, **kwargs)

    return _wrapped_view
