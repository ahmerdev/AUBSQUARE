from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.urls import include, path, re_path

from apps.billing import public_views as billing_public
from apps.outbound import public_views as outbound_public
from apps.seo import views as seo_views

urlpatterns = [
    path("api/v1/", include("apps.api.urls")),
    path("dashboard/", include("apps.accounts.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("robots.txt", seo_views.robots_txt),
    path("sitemap.xml", seo_views.sitemap_xml),
    path("healthz", lambda r: JsonResponse({"ok": True})),
    path("u/<str:token>/", include("apps.marketing.public_urls")),
    path("o/<str:token>/", outbound_public.unsubscribe, name="outbound_unsubscribe"),
    path("p/<str:token>/", outbound_public.proposal_page, name="proposal_public"),
    path("r/<str:token>/", outbound_public.report_page, name="report_public"),
    path("i/<str:token>/", billing_public.invoice_page, name="invoice_public"),
    path("i/<str:token>/pdf/", billing_public.invoice_pdf_download, name="invoice_pdf_public"),
    path("i/<str:token>/receipt/<int:pk>/", billing_public.receipt_download, name="receipt_public"),
    path("d/<str:token>/", billing_public.shared_document, name="shared_document"),
    path("billing/webhooks/<str:provider>/", billing_public.webhook, name="billing_webhook"),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif getattr(settings, "SERVE_MEDIA", False):
    from django.views.static import serve as _serve

    urlpatterns += [re_path(r"^media/(?P<path>.*)$", _serve, {"document_root": settings.MEDIA_ROOT})]
# Production media should be served by the web server / object storage (see docs/DEPLOYMENT.md).
urlpatterns += [re_path(r"^(?P<path>(?!api/|dashboard/|media/|static/|billing/).*)$", seo_views.FrontendShell.as_view())]
