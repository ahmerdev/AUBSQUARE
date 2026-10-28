from django.urls import path

from apps.outbound import api as audit_api

from . import views as v

urlpatterns = [
    path("bootstrap/", v.BootstrapView.as_view()),
    path("form-token/", v.FormTokenView.as_view()),
    path("services/", v.ServiceList.as_view()),
    path("services/<slug:slug>/", v.ServiceDetail.as_view()),
    path("projects/", v.ProjectList.as_view()),
    path("projects/<slug:slug>/", v.ProjectDetail.as_view()),
    path("case-studies/", v.CaseStudyList.as_view()),
    path("case-studies/<slug:slug>/", v.CaseStudyDetail.as_view()),
    path("posts/", v.PostList.as_view()),
    path("posts/<slug:slug>/", v.PostDetail.as_view()),
    path("posts/<slug:slug>/comments/", v.CommentsView.as_view()),
    path("taxonomy/", v.TaxonomyView.as_view()),
    path("leads/", v.LeadCreateView.as_view()),
    path("audit/", audit_api.AuditRunView.as_view()),
    path("audit/<str:token>/", audit_api.AuditDetailView.as_view()),
    path("audit/<str:token>/lead/", audit_api.AuditLeadView.as_view()),
    path("chat/start/", v.ChatStartView.as_view()),
    path("chat/<str:token>/messages/", v.ChatMessagesView.as_view()),
    path("chat/<str:token>/handoff/", v.ChatHandoffView.as_view()),
    path("chat/<str:token>/contact/", v.ChatContactView.as_view()),
    path("analytics/pageview/", v.PageViewView.as_view()),
    path("seo/", v.SeoMetaView.as_view()),
    path("newsletter/subscribe/", v.SubscribeView.as_view()),
]
