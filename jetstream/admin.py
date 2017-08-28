from django.contrib import admin
from django.contrib.admin.options import csrf_protect_m
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator

from core.admin_panel import AbstractAdminPanel
from jetstream import models
from jetstream.admin_panel import tas_api_panel


@admin.register(models.TASAllocationReport)
class TASReportAdmin(admin.ModelAdmin):
    search_fields = ["project_name", "username", ]
    list_display = ["id", "username", "project_name", "compute_used", "start_date", "end_date", "success"]
    list_filter = ["success", "project_name"]


@admin.register(tas_api_panel.TASAPIQuery)
class TASAPIQueryAdminPanel(AbstractAdminPanel):
    @csrf_protect_m
    @method_decorator(staff_member_required)
    def changelist_view(self, request, extra_context=None):
        return tas_api_panel.run_tas_api_query(request)


@admin.register(tas_api_panel.TACCUserForXSEDEUsername)
class TACCUserForXSEDEUsernameAdminPanel(AbstractAdminPanel):
    pass
