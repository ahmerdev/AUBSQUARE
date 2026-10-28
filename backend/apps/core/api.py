from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_handler


class StandardPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 60

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "page": self.page.number,
                "pages": self.page.paginator.num_pages,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )


def exception_handler(exc, context):
    """Consistent error envelope: {"error": {"code", "message", "details"}}."""
    response = drf_handler(exc, context)
    if response is None:
        return None
    data = response.data
    message = "Request failed."
    details = None
    if isinstance(data, dict) and "detail" in data and len(data) == 1:
        message = str(data["detail"])
    else:
        details = data
        message = "Please correct the highlighted fields." if response.status_code == 400 else message
    code = {400: "validation_error", 401: "unauthenticated", 403: "forbidden", 404: "not_found", 405: "method_not_allowed", 429: "rate_limited"}.get(
        response.status_code, "error"
    )
    if response.status_code == 429:
        message = "Too many requests. Please wait a moment and try again."
    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response
