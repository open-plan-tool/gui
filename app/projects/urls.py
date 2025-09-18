from django.urls import path, re_path
from .views import *

urlpatterns = [
    path("", home, name="home"),
    # TODO provide landing with different URL for different languages
    # https://stackoverflow.com/questions/28675442/switch-language-in-django-with-the-translated-url-redirect
    # https://docs.djangoproject.com/en/5.1/topics/http/urls/
    # TODO https://docs.djangoproject.com/en/5.1/topics/i18n/translation/#translating-url-patterns
    path("<int:version>", home, name="home"),
    path("commune", landing_commune, name="landing_commune"),
    path("cellular", landing_cellular, name="landing_cellular"),
    path("kwp", landing_commune, name="landing_commune_de"),
    path("index", landing_default, name="landing_default"),
    path("commune/<int:version>", landing_commune, name="landing_commune"),
    path("cellular/<int:version>", landing_cellular, name="landing_cellular"),
    path("index/<int:version>", landing_default, name="landing_default"),
    # Project
    path("project/create/", project_create, name="project_create"),
    path("notimplementedyet/", not_implemented, name="not_implemented"),
    path("project/search/", project_search, name="project_search"),
    path("project/search/<int:proj_id>", project_search, name="project_search"),
    path(
        "project/search/<int:proj_id>/scenario/<int:scen_id>",
        project_search,
        name="project_search",
    ),
    path("project/update/<int:proj_id>", project_update, name="project_update"),
    path("project/detail/<int:proj_id>", project_detail, name="project_detail"),
    path(
        "project/duplicate/<int:proj_id>", project_duplicate, name="project_duplicate"
    ),
    path("project/export/<int:proj_id>", project_export, name="project_export"),
    path("project/upload", project_upload, name="project_upload"),
    path("project/from/usecase", project_from_usecase, name="project_from_usecase"),
    path(
        "project/from/usecase/<int:usecase_id>",
        project_from_usecase,
        name="project_from_usecase",
    ),
    path("usecase/export/<int:usecase_id>", usecase_export, name="usecase_export"),
    path("project/delete/<int:proj_id>", project_delete, name="project_delete"),
    path(
        "project/project_members_list/<int:proj_id>",
        project_members_list,
        name="project_members_list",
    ),
    path("project/share/<int:proj_id>", project_share, name="project_share"),
    path(
        "project/unshare/<int:proj_id>",
        project_revoke_access,
        name="project_revoke_access",
    ),
    path("project/unshare", project_revoke_access, name="project_revoke_access"),
    path(
        "ajax/projects/viewers",
        ajax_project_viewers_form,
        name="ajax_project_viewers_form",
    ),
    # usecases
    path("usecase/search/", usecase_search, name="usecase_search"),
    path("usecase/search/<int:usecase_id>", usecase_search, name="usecase_search"),
    path(
        "usecase/search/<int:usecase_id>/scenario/<int:scen_id>",
        usecase_search,
        name="usecase_search",
    ),
    # Comment
    path("comment/create/<int:proj_id>", comment_create, name="comment_create"),
    path("comment/update/<int:com_id>", comment_update, name="comment_update"),
    path("comment/delete/<int:com_id>", comment_delete, name="comment_delete"),
    # Scenario
    path(
        "project/<int:proj_id>/scenario/create/step",
        scenario_steps,
        name="scenario_steps",
    ),
    path(
        "project/<int:proj_id>/scenario/create/step/<int:step_id>",
        scenario_steps,
        name="scenario_steps",
    ),
    path(
        "project/<int:proj_id>/scenario/<int:scen_id>/edit/step/<int:step_id>",
        scenario_steps,
        name="scenario_steps_edit",
    ),
    path(
        "scenario/select/project",
        scenario_select_project,
        name="scenario_select_project",
    ),
    path(
        "project/<int:proj_id>/scenario/create_parameters",
        scenario_create_parameters,
        name="scenario_create_parameters",
    ),
    path(
        "project/<int:proj_id>/scenario/create_topology",
        scenario_create_topology,
        name="scenario_create_topology",
    ),
    path(
        "project/<int:proj_id>/scenario/create_constraints",
        scenario_create_constraints,
        name="scenario_create_constraints",
    ),
    path(
        "project/<int:proj_id>/scenario/create_parameters/<int:scen_id>",
        scenario_create_parameters,
        name="scenario_create_parameters",
    ),
    path(
        "project/<int:proj_id>/scenario/create_parameters/<scen_id>",
        scenario_create_parameters,
        name="scenario_create_parameters",
    ),
    path(
        "project/<int:proj_id>/scenario/create_topology/<int:scen_id>",
        scenario_create_topology,
        name="scenario_create_topology",
    ),
    path(
        "project/<int:proj_id>/scenario/create_constraints/<int:scen_id>/",
        scenario_create_constraints,
        name="scenario_create_constraints",
    ),
    path(
        "project/<int:proj_id>/scenario/review/<int:scen_id>/",
        scenario_review,
        name="scenario_review",
    ),
    path(
        "project/<int:proj_id>/scenario/review/",
        back_to_scenario_review,
        name="back_to_scenario_review",
    ),
    path("scenario/update/<int:scen_id>", scenario_update, name="scenario_update"),
    path("scenario/delete/<int:scen_id>", scenario_delete, name="scenario_delete"),
    path(
        "scenario/duplicate/<int:scen_id>",
        scenario_duplicate,
        name="scenario_duplicate",
    ),
    path("scenario/export/<int:proj_id>", scenario_export, name="scenario_export"),
    path("scenario/upload/<int:proj_id>", scenario_upload, name="scenario_upload"),
    # path('scenario/upload/<int:proj_id>', LoadScenarioFromFileView.as_view(), name='scenario_upload'),
    # Timeseries Model
    path("upload/timeseries", upload_timeseries, name="upload_timeseries"),
    path("get/timeseries", get_timeseries, name="get_timeseries"),
    path("get/timeseries/<int:ts_id>", get_timeseries, name="get_timeseries"),
    path(
        "get/constant/timeseries/id",
        get_constant_timeseries_id,
        name="get_constant_timeseries_id",
    ),
    re_path(
        "get/constant/timeseries/id/(?P<ts_length>\d+)/value/(?P<value>\d+(\.\d+)?)/$",
        get_constant_timeseries_id,
        name="get_constant_timeseries_id",
    ),
    # Grid Model (Assets Creation)
    re_path(
        r"^asset/get_form/(?P<scen_id>\d+)/(?P<asset_type_name>[\w-]+)?(/(?P<asset_uuid>[0-9a-f-]+))?$",
        get_asset_create_form,
        name="get_asset_create_form",
    ),
    re_path(
        r"^asset/create_or_update_post/(?P<scen_id>\d+)/(?P<asset_type_name>[\w-]+)?(/(?P<asset_uuid>[0-9a-f-]+))?$",
        asset_create_or_update,
        name="asset_create_or_update",
    ),
    path(
        "asset/get_connection_ports_mapping",
        asset_connection_ports_mapping,
        name="asset_connection_ports_mapping",
    ),
    path(
        "asset/get_connection_ports_mapping/<str:asset_type_name>",
        asset_connection_ports_mapping,
        name="asset_connection_ports_mapping",
    ),
    path(
        "asset/get_connection_ports_info",
        asset_connection_ports_info,
        name="asset_connection_ports_info",
    ),
    path(
        "asset/get_connection_ports_info/<str:asset_type_name>",
        asset_connection_ports_info,
        name="asset_connection_ports_info",
    ),
    path(
        "asset/get_connection_ports_number",
        asset_connection_ports_number,
        name="asset_connection_ports_number",
    ),
    path(
        "asset/get_connection_ports_number/<str:asset_type_name>",
        asset_connection_ports_number,
        name="asset_connection_ports_number",
    ),
    re_path(
        r"^asset/get_cops_form/(?P<scen_id>\d+)/(?P<asset_type_name>[\w-]+)?(/(?P<asset_uuid>[0-9a-f-]+))?$",
        get_asset_cops_form,
        name="get_asset_cops_form",
    ),
    re_path(
        r"^asset/cops_create_or_update/(?P<scen_id>\d+)/(?P<asset_type_name>[\w-]+)?(/(?P<asset_uuid>[0-9a-f-]+))?$",
        asset_cops_create_or_update,
        name="asset_cops_create_or_update",
    ),
    # ParameterChangeTracker (track of simulated scenario changes)
    path(
        "reset_scenario_changes/<int:scen_id>",
        reset_scenario_changes,
        name="reset_scenario_changes",
    ),
    # MVS Simulation
    path(
        "simulation/cancel/<int:scen_id>", simulation_cancel, name="simulation_cancel"
    ),
    path(
        "view_mvs_data_input/<int:scen_id>",
        view_mvs_data_input,
        name="view_mvs_data_input",
    ),
    path(
        "test_mvs_data_input/<int:scen_id>",
        test_mvs_data_input,
        name="test_mvs_data_input",
    ),
    path(
        "topology/mvs_simulation/<int:scen_id>",
        request_mvs_simulation,
        name="request_mvs_simulation",
    ),
    path(
        "topology/update_simulation_rating/",
        update_simulation_rating,
        name="update_simulation_rating",
    ),
    # path('topology/simulation_status/<int:scen_id>', check_simulation_status, name='check_simulation_status'),
    path(
        "simulation/fetch-results/<int:sim_id>",
        fetch_simulation_results,
        name="fetch_simulation_results",
    ),
    # Sensitivity analysis
    path(
        "scenario/<int:scen_id>/sensitivity-analysis/create",
        sensitivity_analysis_create,
        name="sensitivity_analysis_create",
    ),
    path(
        "scenario/<int:scen_id>/sensitivity-analysis/<int:sa_id>",
        sensitivity_analysis_create,
        name="sensitivity_analysis_review",
    ),
    path(
        "scenario/<int:scen_id>/sensitivity-analysis/run",
        sensitivity_analysis_create,
        name="sensitivity_analysis_run",
    ),
    path(
        "scenario/<int:scen_id>/sensitivity-analysis/error",
        sensitivity_analysis_create,
        name="sensitivity_analysis_error",
    ),
    path(
        "sensitivity-analysis/fetch-results/<int:sa_id>",
        fetch_sensitivity_analysis_results,
        name="fetch_sensitivity_analysis_results",
    ),
    # User Feedback
    path("user_feedback", user_feedback, name="user_feedback"),
    path("sponsor/feature", sponsor_feature, name="sponsor_feature"),
]
