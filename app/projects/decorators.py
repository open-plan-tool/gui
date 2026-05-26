from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from functools import wraps

from projects.models import Project, Scenario


def viewer_has_view_rights(view_func):
    @wraps(view_func)
    def _wrapped_view(request, proj_id=None, scenario_id=None, *args, **kwargs):
        if proj_id:
            project = get_object_or_404(Project, pk=proj_id)
        elif scenario_id:
            scenario = get_object_or_404(Scenario, pk=scenario_id)
            project = scenario.project
        # oder ersetzen durch user.has_read_rights
        if (project.user != request.user) and (
            project.viewers.filter(user__email=request.user.email).exists() is False
        ):
            raise PermissionDenied
        return view_func(request, proj_id, *args, **kwargs)

    return _wrapped_view


def viewer_has_edit_rights(view_func):
    @wraps(view_func)
    def _wrapped_view(request, proj_id=None, scenario_id=None, *args, **kwargs):
        if proj_id:
            project = get_object_or_404(Project, pk=proj_id)
        elif scenario_id:
            scenario = get_object_or_404(Scenario, pk=scenario_id)
            project = scenario.project
        # oder ersetzen durch user.has_edit_rights
        if (project.user != request.user) and (
            project.viewers.filter(
                user__email=request.user.email, share_rights="edit"
            ).exists()
            is False
        ):
            raise PermissionDenied
        return view_func(request, proj_id, *args, **kwargs)

    return _wrapped_view
