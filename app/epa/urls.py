"""EPA URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.conf.urls.i18n import i18n_patterns
from django.urls import path, re_path, include
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

from .views import imprint, privacy, about, license, contact, publications, newsletter, courses

urlpatterns = (
    i18n_patterns(
        path("admin/", admin.site.urls),
        path("users/", include("django.contrib.auth.urls")),
        path("users/", include("users.urls")),
        path("", include("projects.urls")),
        path("dashboard/", include("dashboard.urls")),
        path("imprint/", imprint, name="imprint"),
        path("privacy/", privacy, name="privacy"),
        path("about/", about, name="about"),
        path("contact/", contact, name="contact"),
        path("license/", license, name="license"),
        path("publications/", publications, name="publications"),
        path("newsletter/", newsletter, name="newsletter"),
        path("courses/", courses, name="courses"),
        path("schulungen/", courses, name="courses_de"),
    )
    + [re_path(r"^i18n/", include("django.conf.urls.i18n"))]
    + staticfiles_urlpatterns()
)
