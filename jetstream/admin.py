from django.contrib import admin
from django.contrib.admin.options import csrf_protect_m
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator

from jetstream import models
from jetstream.selfservice import TASAPIQuery, run_tas_api_query, AbstractSelfServiceModelAdmin


@admin.register(models.TASAllocationReport)
class TASReportAdmin(admin.ModelAdmin):
    search_fields = ["project_name", "username", ]
    list_display = ["id", "username", "project_name", "compute_used", "start_date", "end_date", "success"]
    list_filter = ["success", "project_name"]


@admin.register(TASAPIQuery)
class TASAPIQueryAdmin(AbstractSelfServiceModelAdmin):
    @csrf_protect_m
    @method_decorator(staff_member_required)
    def changelist_view(self, request, extra_context=None):
        return run_tas_api_query(request)
