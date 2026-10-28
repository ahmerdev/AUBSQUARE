from django.urls import path
from django.views.generic import TemplateView

from . import views as v

app_name = "accounts"
urlpatterns = [
    path("login/", v.login_view, name="login"),
    path("logout/", v.logout_view, name="logout"),
    path("register/", v.register_view, name="register"),
    path("verify-email/<str:token>/", v.verify_email, name="verify_email"),
    path("invite/<str:token>/", v.accept_invite, name="accept_invite"),
    path("password-reset/", v.ResetRequest.as_view(), name="reset"),
    path("password-reset/sent/", TemplateView.as_view(template_name="accounts/reset_sent.html"), name="reset_sent"),
    path("password-reset/<uidb64>/<token>/", v.ResetConfirm.as_view(), name="reset_confirm"),
    path("password-reset/complete/", TemplateView.as_view(template_name="accounts/reset_done.html"), name="reset_done"),
    path("profile/", v.profile, name="profile"),
]
