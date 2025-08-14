from django.shortcuts import render
from django.views.decorators.http import require_http_methods
import logging
from projects.services import excuses_design_under_development

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def imprint(request):
    return render(request, "legal/imprint.html")


@require_http_methods(["GET"])
def privacy(request):
    return render(request, "legal/privacy.html")


@require_http_methods(["GET"])
def about(request):
    return render(request, "legal/about.html")


@require_http_methods(["GET"])
def contact(request):
    return render(request, "legal/contact.html")


@require_http_methods(["GET"])
def license(request):
    return render(request, "legal/license.html")


@require_http_methods(["GET"])
def publications(request):
    return render(request, "landing/publications.html")

@require_http_methods(["GET"])
def newsletter(request):
    return render(request, "landing/newsletter.html")

@require_http_methods(["GET"])
def courses(request):
    return render(request, "landing/courses.html")
