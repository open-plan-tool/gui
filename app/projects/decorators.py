from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from functools import wraps

from projects.models import Project, Scenario


def user_is_owner(view_func):
    @wraps(view_func)
    def _wrapped_view(request, proj_id=None, scen_id=None, *args, **kwargs):
        if proj_id:
            project = get_object_or_404(Project, pk=proj_id)
        elif scen_id:
            scenario = get_object_or_404(Scenario, pk=scen_id)
            project = scenario.project

        if project.user != request.user:
            raise PermissionDenied
        # check for existing parameters to handle the different view parameters
        if proj_id is not None and scen_id is not None:
            return view_func(request, proj_id, scen_id, *args, **kwargs)
        elif proj_id is not None:
            return view_func(request, proj_id, *args, **kwargs)
        elif scen_id is not None:
            return view_func(request, scen_id, *args, **kwargs)

    return _wrapped_view


def viewer_has_view_rights(view_func):
    @wraps(view_func)
    def _wrapped_view(request, proj_id=None, scen_id=None, *args, **kwargs):
        if proj_id:
            project = get_object_or_404(Project, pk=proj_id)
        elif scen_id:
            scenario = get_object_or_404(Scenario, pk=scen_id)
            project = scenario.project

        if (project.user != request.user) and (
            project.viewers.filter(user__email=request.user.email).exists() is False
        ):
            raise PermissionDenied
        # check for existing parameters to handle the different view parameters
        if proj_id is not None and scen_id is not None:
            return view_func(request, proj_id, scen_id, *args, **kwargs)
        elif proj_id is not None:
            return view_func(request, proj_id, *args, **kwargs)
        elif scen_id is not None:
            return view_func(request, scen_id, *args, **kwargs)

    return _wrapped_view


def viewer_has_edit_rights(view_func):
    @wraps(view_func)
    def _wrapped_view(request, proj_id=None, scen_id=None, *args, **kwargs):
        if proj_id:
            project = get_object_or_404(Project, pk=proj_id)
        elif scen_id:
            scenario = get_object_or_404(Scenario, pk=scen_id)
            project = scenario.project

        if (project.user != request.user) and (
            project.viewers.filter(
                user__email=request.user.email, share_rights="edit"
            ).exists()
            is False
        ):
            raise PermissionDenied
        # check for existing parameters to handle the different view parameters
        if proj_id is not None and scen_id is not None:
            return view_func(request, proj_id, scen_id, *args, **kwargs)
        elif proj_id is not None:
            return view_func(request, proj_id, *args, **kwargs)
        elif scen_id is not None:
            return view_func(request, scen_id, *args, **kwargs)

    return _wrapped_view
