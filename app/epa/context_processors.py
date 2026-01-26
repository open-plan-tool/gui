from django.conf import settings


def debug(context):
    return {"DEBUG": settings.DEBUG}


def app_version(request):
    """Expose version number in templates."""
    return {
        "APP_VERSION_NUMBER": settings.APP_VERSION_NUMBER,
    }
