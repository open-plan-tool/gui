from django.urls import path, re_path
from .views import *

urlpatterns = [
    path("", home_cpn, name="home_cpn"),
    # steps
    path("<int:proj_id>/edit/step/<int:step_id>", cpn_steps, name="cpn_steps"),
    path("<int:proj_id>/review/<int:scen_id>", cpn_review, name="cpn_review"),

]
