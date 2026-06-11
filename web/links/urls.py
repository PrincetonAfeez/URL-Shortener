"""URLs for the links app. """

from __future__ import annotations

from django.urls import path

from links import views

app_name = "links"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("links/<str:code>/disable", views.disable_link, name="disable"),
    path("links/<str:code>/delete", views.delete_link, name="delete"),
    path("links/<str:code>/stats", views.stats_panel, name="stats_panel"),
    path("api/links", views.api_create, name="api_create"),
    path("api/links/<str:code>", views.api_detail, name="api_detail"),
    path("api/links/<str:code>/disable", views.api_disable, name="api_disable"),
    path("api/links/<str:code>/expire", views.api_expire, name="api_expire"),
    path("api/links/<str:code>/stats", views.api_stats, name="api_stats"),
    path("<str:code>", views.redirect_link, name="redirect"),
]
