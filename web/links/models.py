"""Models for the links app. """

from __future__ import annotations

from django.db import models


class Link(models.Model):
    short_code = models.CharField(max_length=128, unique=True)
    destination_url = models.URLField(max_length=2048)
    redirect_status = models.PositiveSmallIntegerField(default=302)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    max_clicks = models.PositiveIntegerField(null=True, blank=True)
    click_count = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "links"
        indexes = [
            models.Index(fields=["created_at"], name="links_created_at_idx"),
            models.Index(
                fields=["disabled_at", "deleted_at", "expires_at"],
                name="links_lifecycle_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.short_code} -> {self.destination_url}"


class Click(models.Model):
    link = models.ForeignKey(
        Link,
        on_delete=models.CASCADE,
        related_name="clicks",
        db_column="link_id",
    )
    clicked_at = models.DateTimeField(auto_now_add=True)
    referrer = models.TextField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "clicks"
        indexes = [
            models.Index(
                fields=["link", "clicked_at"],
                name="clicks_link_clicked_idx",
            ),
        ]


class HealthCheckResult(models.Model):
    link = models.ForeignKey(
        Link,
        on_delete=models.CASCADE,
        related_name="health_results",
        db_column="link_id",
    )
    checked_at = models.DateTimeField()
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    elapsed_ms = models.FloatField()
    redirect_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "health_check_results"
        indexes = [
            models.Index(
                fields=["link", "checked_at"],
                name="health_link_checked_idx",
            ),
        ]
