from django.conf.urls import url
from django.contrib import admin
from django.contrib.admin.options import csrf_protect_m
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator

from jetstream import models
from jetstream.jetstream_selfservice import TASAPIQuery, run_tas_api_query


@admin.register(models.TASAllocationReport)
class TASReportAdmin(admin.ModelAdmin):
    search_fields = ["project_name", "username",]
    list_display = ["id", "username", "project_name", "compute_used", "start_date", "end_date", "success"]
    list_filter = ["success", "project_name"]


class AbstractSelfServiceModelAdmin(admin.ModelAdmin):
    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name
        changelist_url_name = '%s_%s_changelist' % info
        urls = [
            url(r'^$', self.admin_site.admin_view(run_tas_api_query), name=changelist_url_name),
        ]
        return urls

    def changelist_view(self, request, extra_context=None):
        """
        The 'change list' admin view for a 'fake' model.

        Subclass this class and implement this method yourself.
        """
        raise NotImplementedError

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TASAPIQuery)
class TASAPIQueryAdmin(AbstractSelfServiceModelAdmin):
    @csrf_protect_m
    @method_decorator(staff_member_required)
    def changelist_view(self, request, extra_context=None):
        return run_tas_api_query(request)
