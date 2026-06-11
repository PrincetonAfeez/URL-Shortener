"""Storage adapter for the links app. """

from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from sniplink.core.lifecycle import ensure_click_quota_available, ensure_link_available
from sniplink.exceptions import AliasTaken, CodeExpired, CodeNotFound
from sniplink.models import HealthCheckResult as CoreHealthCheckResult
from sniplink.models import Link as CoreLink

from links import models


class DjangoStorage:
    def initialize(self) -> None:
        return None

    def insert_link(
        self,
        *,
        short_code: str,
        destination_url: str,
        redirect_status: int,
        expires_at: datetime | None = None,
        max_clicks: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CoreLink:
        try:
            with transaction.atomic():
                link = models.Link.objects.create(
                    short_code=short_code,
                    destination_url=destination_url,
                    redirect_status=redirect_status,
                    expires_at=expires_at,
                    max_clicks=max_clicks,
                    metadata=metadata or {},
                )
        except IntegrityError as exc:
            raise AliasTaken(f"short code already exists: {short_code}") from exc
        return self._to_core(link)

    def insert_pending_link(
        self,
        *,
        destination_url: str,
        redirect_status: int,
        expires_at: datetime | None = None,
        max_clicks: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CoreLink:
        import uuid

        return self.insert_link(
            short_code=f"__pending_{uuid.uuid4().hex}",
            destination_url=destination_url,
            redirect_status=redirect_status,
            expires_at=expires_at,
            max_clicks=max_clicks,
            metadata=metadata,
        )

    def update_short_code(self, link_id: int, short_code: str) -> CoreLink:
        try:
            with transaction.atomic():
                link = models.Link.objects.select_for_update().get(id=link_id)
                link.short_code = short_code
                link.save(update_fields=["short_code"])
        except models.Link.DoesNotExist as exc:
            raise CodeNotFound(f"link id not found: {link_id}") from exc
        except IntegrityError as exc:
            raise AliasTaken(f"short code already exists: {short_code}") from exc
        return self._to_core(link)

    def delete_pending_link(self, link_id: int) -> None:
        with transaction.atomic():
            deleted, _ = models.Link.objects.filter(
                id=link_id, short_code__startswith="__pending_"
            ).delete()
            if not deleted:
                raise CodeNotFound(f"pending link id not found: {link_id}")

    def cleanup_stale_pending_links(self, *, max_age_hours: int = 24) -> int:
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(hours=max_age_hours)
        deleted, _ = models.Link.objects.filter(
            short_code__startswith="__pending_", created_at__lt=cutoff
        ).delete()
        return int(deleted)

    def get_link(self, short_code: str) -> CoreLink:
        try:
            return self._to_core(models.Link.objects.get(short_code=short_code))
        except models.Link.DoesNotExist as exc:
            raise CodeNotFound(f"short code not found: {short_code}") from exc

    def get_link_by_id(self, link_id: int) -> CoreLink:
        try:
            return self._to_core(models.Link.objects.get(id=link_id))
        except models.Link.DoesNotExist as exc:
            raise CodeNotFound(f"link id not found: {link_id}") from exc

    def list_links(self, include_deleted: bool = False) -> list[CoreLink]:
        query = models.Link.objects.all()
        if not include_deleted:
            query = query.filter(deleted_at__isnull=True)
        return [self._to_core(link) for link in query.order_by("-created_at", "-id")]

    def mark_disabled(self, short_code: str) -> CoreLink:
        return self._touch(short_code, "disabled_at")

    def mark_deleted(self, short_code: str) -> CoreLink:
        return self._touch(short_code, "deleted_at")

    def set_expiry(self, short_code: str, expires_at: datetime) -> CoreLink:
        with transaction.atomic():
            updated = models.Link.objects.filter(short_code=short_code).update(
                expires_at=expires_at
            )
            if not updated:
                raise CodeNotFound(f"short code not found: {short_code}")
            return self.get_link(short_code)

    def record_click(
        self,
        link_id: int,
        *,
        referrer: str | None = None,
        user_agent: str | None = None,
    ) -> CoreLink:
        """Atomic max_clicks gate + click row insert.

        Mirrors ``SQLiteStorage.record_click``: the conditional UPDATE serves
        as both the cap check and the increment, so two concurrent requests
        can never both pass and both bust the cap (bug #1 in the code
        review).
        """

        now = timezone.now()
        with transaction.atomic():
            updated = (
                models.Link.objects.filter(id=link_id)
                .filter(disabled_at__isnull=True, deleted_at__isnull=True)
                .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
                .filter(Q(max_clicks__isnull=True) | Q(click_count__lt=F("max_clicks")))
                .update(click_count=F("click_count") + 1)
            )
            if updated == 0:
                link = self.get_link_by_id(link_id)
                ensure_link_available(link)
                ensure_click_quota_available(link)
                raise CodeExpired(f"link reached max_clicks: {link_id}")
            models.Click.objects.create(
                link_id=link_id,
                referrer=referrer,
                user_agent=user_agent,
            )
        return self.get_link_by_id(link_id)

    def stats(self, short_code: str) -> dict[str, Any]:
        try:
            link = models.Link.objects.get(short_code=short_code)
        except models.Link.DoesNotExist as exc:
            raise CodeNotFound(f"short code not found: {short_code}") from exc
        last_click = link.clicks.order_by("-clicked_at").first()
        return {
            "short_code": link.short_code,
            "destination_url": link.destination_url,
            "click_count": link.click_count,
            "recorded_clicks": link.clicks.count(),
            "last_clicked_at": (
                last_click.clicked_at.astimezone(dt_timezone.utc).isoformat()
                if last_click
                else None
            ),
            "disabled": link.disabled_at is not None,
            "deleted": link.deleted_at is not None,
            "expires_at": (
                link.expires_at.astimezone(dt_timezone.utc).isoformat()
                if link.expires_at
                else None
            ),
        }

    def save_health_result(self, result: CoreHealthCheckResult) -> None:
        models.HealthCheckResult.objects.create(
            link_id=result.link_id,
            checked_at=result.checked_at,
            status_code=result.status_code,
            error=result.error,
            elapsed_ms=result.elapsed_ms,
            redirect_count=result.redirect_count,
        )

    def _touch(self, short_code: str, field: str) -> CoreLink:
        with transaction.atomic():
            updated = models.Link.objects.filter(short_code=short_code).update(
                **{field: timezone.now()}
            )
            if not updated:
                raise CodeNotFound(f"short code not found: {short_code}")
            return self.get_link(short_code)

    def _to_core(self, link: models.Link) -> CoreLink:
        return CoreLink(
            id=link.id,
            short_code=link.short_code,
            destination_url=link.destination_url,
            redirect_status=link.redirect_status,
            created_at=link.created_at,
            expires_at=link.expires_at,
            disabled_at=link.disabled_at,
            deleted_at=link.deleted_at,
            max_clicks=link.max_clicks,
            click_count=link.click_count,
            metadata=link.metadata or {},
        )
