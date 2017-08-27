from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db import models
from django.forms import ModelForm, Textarea
from django.shortcuts import render

from jetstream import tas_api
from jetstream.exceptions import TASAPIException


class TASAPIQuery(models.Model):
    TACC_USERNAME = 'TACC_USERNAME'
    ACTIVE_ALLOCATIONS = 'ACTIVE_ALLOCATIONS'
    PROJECTS = 'PROJECTS'
    QUERY_CHOICES = (
        (TACC_USERNAME, 'TACC Username'),
        (ACTIVE_ALLOCATIONS, 'Active Allocations'),
        (PROJECTS, 'Projects'),
    )
    query_type = models.CharField(
        max_length=30,
        choices=QUERY_CHOICES,
        default=TACC_USERNAME,
    )

    query = models.TextField('Query')

    class Meta:
        managed = False
        verbose_name = 'TAS API Query'
        verbose_name_plural = 'TAS API Queries'


class TASAPIQueryForm(ModelForm):
    class Meta:
        model = TASAPIQuery
        fields = '__all__'
        widgets = {
            'query': Textarea(attrs={
                'id': 'query',
                'autofocus': True,
                'cols': '40',
                'rows': '1'
            })
        }


@staff_member_required
def run_tas_api_query(request):
    context = {}

    if request.method == 'POST':
        request.POST = request.POST.copy()
        form = TASAPIQueryForm(request.POST)
        form.is_valid()
        info, header, rows = _execute_tas_api_query(form.cleaned_data['query_type'], form.cleaned_data['query'])
        context['info'] = info
        context['header'] = header
        context['rows'] = rows
    else:
        form = TASAPIQueryForm()

    context['form'] = form
    context['title'] = TASAPIQuery._meta.verbose_name

    return render(request, 'tas_api_query.html', context)


def _execute_tas_api_query(query_type, query=None):
    # return something like: 'Success', ['col1', 'col2'], [['row1_val1', 'row1_val2'], ['row2_val1', 'row2_val2']]
    tacc_api = settings.TACC_API_URL
    info = 'Unknown query'
    header = []
    rows = []
    if query_type == TASAPIQuery.TACC_USERNAME:
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
