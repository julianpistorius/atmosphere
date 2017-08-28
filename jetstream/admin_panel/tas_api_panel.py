from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db import models
from django.forms import TextInput, modelform_factory
from django.shortcuts import render

from jetstream import tas_api
from jetstream.exceptions import TASAPIException

TACC_USERNAME = 'TACC_USERNAME'
ACTIVE_ALLOCATIONS = 'ACTIVE_ALLOCATIONS'
PROJECTS = 'PROJECTS'


class TACCUserForXSEDEUsername(models.Model):
    xsede_username = models.CharField('XSEDE Username', max_length=255)

    class Meta:
        app_label = 'jetstream'
        managed = False
        verbose_name = 'TACC User for XSEDE Username'

    @staticmethod
    def admin_panel_view(request, extra_context=None):
        return _get_tacc_user_for_xsede_username(request)


@staff_member_required
def _get_tacc_user_for_xsede_username(request):
    context = {}

    form_class = modelform_factory(TACCUserForXSEDEUsername,
                                   fields=['xsede_username'],
                                   widgets={'xsede_username': TextInput})

    if request.method == 'POST':
        request.POST = request.POST.copy()
        form = form_class(request.POST)
        form.is_valid()
        xsede_username = form.cleaned_data['xsede_username']
        info, header, rows = _execute_tas_api_query(TACC_USERNAME, xsede_username)
        context['info'] = info
        context['header'] = header
        context['rows'] = rows
    else:
        form = form_class()

    context['form'] = form
    context['title'] = TACCUserForXSEDEUsername._meta.verbose_name

    return render(request, 'tas_api_query.html', context)


def _execute_tas_api_query(query_type, query=None):
    # return something like: 'Success', ['col1', 'col2'], [['row1_val1', 'row1_val2'], ['row2_val1', 'row2_val2']]
    tacc_api = settings.TACC_API_URL
    info = 'Unknown query'
    header = []
    rows = []
    if query_type == TACC_USERNAME:
        xsede_username = query
        path = '/v1/users/xsede/%s' % xsede_username
        url = tacc_api + path
        try:
            response, data = tas_api.tacc_api_get(url)
            assert isinstance(data, dict)
            info = response.__repr__()
            header = data.keys()
            row = [data[key] for key in header]
            rows = [row]
        except TASAPIException as e:
            info = e

    return info, header, rows


__all__ = ['TACCUserForXSEDEUsername']