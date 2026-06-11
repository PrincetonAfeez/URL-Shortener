"""URLs for the sniplink web app. """

from __future__ import annotations

from django.urls import include, path

urlpatterns = [
    path("", include("links.urls")),
]
