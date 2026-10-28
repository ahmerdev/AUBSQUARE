from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class ApprovedEmailBackend(ModelBackend):
    """Email + password login that only ever authenticates APPROVED, active users."""

    def authenticate(self, request, email=None, password=None, username=None, **kwargs):
        User = get_user_model()
        email = (email or username or "").strip().lower()
        if not email or not password:
            return None
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            User().set_password(password)  # equalise timing
            return None
        if user.check_password(password) and user.is_active and user.status == User.APPROVED:
            return user
        return None

    def user_can_authenticate(self, user):
        return bool(user.is_active and getattr(user, "status", None) == "approved")

    def get_user(self, user_id):
        user = super().get_user(user_id)
        # A user suspended/rejected mid-session loses access immediately.
        if user is not None and user.status != "approved":
            return None
        return user
