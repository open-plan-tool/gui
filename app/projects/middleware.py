import json
from django.utils.deprecation import MiddlewareMixin
from django.contrib.messages import get_messages


class HtmxMessageMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if "HX-Request" in request.headers:
            messages = [
                {"message": m.message, "tags": m.tags} for m in get_messages(request)
            ]
            if messages:
                response.headers["HX-Trigger"] = json.dumps({"messages": messages})
        return response
