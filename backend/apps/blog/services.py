import re

from django.utils import timezone

from apps.core.models import SiteSettings
from apps.core.sanitize import clean_plain
from apps.core.services import notify, visitor_hash
from .models import Comment

LINK_RE = re.compile(r"https?://|www\.", re.I)


def submit_comment(post, data, request, token_check):
    """Create a PENDING comment (or SPAM if heuristics trip). Returns (comment, error_dict|None)."""
    errors = {}
    name = clean_plain(data.get("name", ""), 80)
    email = clean_plain(data.get("email", ""), 254).lower()
    body = clean_plain(data.get("message", ""), 2000)
    if len(name) < 2:
        errors["name"] = "Please enter your name."
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email

    try:
        validate_email(email)
    except ValidationError:
        errors["email"] = "Please enter a valid email."
    if len(body) < 3:
        errors["message"] = "Please write a comment."
    if errors:
        return None, errors
    parent = None
    if data.get("parentId"):
        parent = Comment.objects.filter(pk=data["parentId"], post=post, status=Comment.APPROVED, parent__isnull=True).first()
    reasons = []
    if data.get("website"):
        reasons.append("honeypot")
    ok, why = token_check(data.get("formToken", ""))
    if not ok:
        reasons.append(why)
    if len(LINK_RE.findall(body)) > 1:
        reasons.append("multiple links")
    blocklist = [w.strip().lower() for w in SiteSettings.load().comment_blocklist.splitlines() if w.strip()]
    if any(w in body.lower() for w in blocklist):
        reasons.append("blocked word")
    if Comment.objects.filter(post=post, email=email, body=body).exists():
        return None, {"message": "You already posted this comment."}
    c = Comment.objects.create(post=post, parent=parent, name=name, email=email, body=body, visitor_hash=visitor_hash(request),
                               status=Comment.SPAM if reasons else Comment.PENDING, spam_reason=", ".join(reasons)[:160])
    if not reasons:
        notify("comment", f"New comment on “{post.title[:50]}”", f"{name}: {body[:100]}", f"/dashboard/comments/?status=pending", module="blog")
        try:
            from apps.mailer.service import notify_staff_by_email

            notify_staff_by_email("comment", f"[AUB SQUARE] Comment awaiting moderation: {post.title[:60]}", f"{name} <{email}> wrote:\n\n{body}\n\nModerate: /dashboard/comments/?status=pending")
        except Exception:
            pass
    return c, None
