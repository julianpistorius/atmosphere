from django.contrib import admin
from jetstream import models
from jetstream.jetstream_selfservice import TASAPIQuery


@admin.register(models.TASAllocationReport)
class TASReportAdmin(admin.ModelAdmin):
    search_fields = ["project_name", "username",]
    list_display = ["id", "username", "project_name", "compute_used", "start_date", "end_date", "success"]
    list_filter = ["success", "project_name"]


@admin.register(TASAPIQuery)
class TASAPIQueryAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False