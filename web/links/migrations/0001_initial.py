"""Initial migration for the links app. """

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Link",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("short_code", models.CharField(max_length=128, unique=True)),
                ("destination_url", models.URLField(max_length=2048)),
                ("redirect_status", models.PositiveSmallIntegerField(default=302)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("disabled_at", models.DateTimeField(blank=True, null=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("max_clicks", models.PositiveIntegerField(blank=True, null=True)),
                ("click_count", models.PositiveIntegerField(default=0)),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "db_table": "links",
            },
        ),
        migrations.CreateModel(
            name="HealthCheckResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("checked_at", models.DateTimeField()),
                ("status_code", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("error", models.TextField(blank=True, null=True)),
                ("elapsed_ms", models.FloatField()),
                ("redirect_count", models.PositiveSmallIntegerField(default=0)),
                (
                    "link",
                    models.ForeignKey(
                        db_column="link_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="health_results",
                        to="links.link",
                    ),
                ),
            ],
            options={
                "db_table": "health_check_results",
            },
        ),
        migrations.CreateModel(
            name="Click",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("clicked_at", models.DateTimeField(auto_now_add=True)),
                ("referrer", models.TextField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, null=True)),
                (
                    "link",
                    models.ForeignKey(
                        db_column="link_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="clicks",
                        to="links.link",
                    ),
                ),
            ],
            options={
                "db_table": "clicks",
            },
        ),
        migrations.AddIndex(
            model_name="link",
            index=models.Index(fields=["short_code"], name="links_link_short_c_8ec64e_idx"),
        ),
        migrations.AddIndex(
            model_name="link",
            index=models.Index(fields=["created_at"], name="links_link_created_789b6d_idx"),
        ),
        migrations.AddIndex(
            model_name="link",
            index=models.Index(fields=["disabled_at", "deleted_at", "expires_at"], name="links_link_disable_02489a_idx"),
        ),
        migrations.AddIndex(
            model_name="healthcheckresult",
            index=models.Index(fields=["link", "checked_at"], name="links_healt_link_id_d8db9b_idx"),
        ),
        migrations.AddIndex(
            model_name="click",
            index=models.Index(fields=["link", "clicked_at"], name="links_click_link_id_a8dd16_idx"),
        ),
    ]
