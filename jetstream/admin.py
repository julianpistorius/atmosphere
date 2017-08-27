from django.conf.urls import url
from django.contrib import admin
from jetstream import models
from jetstream.jetstream_selfservice import TASAPIQuery, run_tas_api_query


@admin.register(models.TASAllocationReport)
class TASReportAdmin(admin.ModelAdmin):
    search_fields = ["project_name", "username",]
    list_display = ["id", "username", "project_name", "compute_used", "start_date", "end_date", "success"]
    list_filter = ["success", "project_name"]


@admin.register(TASAPIQuery)
class TASAPIQueryAdmin(admin.ModelAdmin):
    def get_urls(self):
        my_urls = [
            url(r'^$', self.admin_site.admin_view(run_tas_api_query), name='jetstream_tasapiquery_changelist'),
        ]
        return my_urls

    def has_add_permission(self, request):
        return False