# -*- coding: utf-8 -*-
"""
Routes for the atmosphere application
"""
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.conf import settings
from django.conf.urls import url, include
from rest_framework.authtoken.views import ObtainAuthToken
from api.auth import Authentication
from jetstream.jetstream_selfservice import run_tas_api_query

admin.autodiscover()

urlpatterns = [
    # Core endpoints
    url(r'', include("core.urls", namespace="core")),

    # Authentication endpoints
    url(r'', include("django_cyverse_auth.urls", namespace="django_cyverse_auth")),

    # API Layer endpoints
    url(r'^api/', include("api.urls", namespace="api")),

    # v2 API auth by token
    url(r'^auth$', Authentication.as_view(), name='token-auth'),

    # DRF API Login/Logout
    url(r'^api-auth/',
        include('rest_framework.urls', namespace='rest_framework')),

    # Token login (Used internally by DRF?)
    url(r'^api-token-auth/',
        ObtainAuthToken.as_view()),

    # Self-service dashboard for Jetstream admin users
    # TODO: Make this contingent on the `jetstream` app being in `INSTALLED_APPS`
    url(r'^admin/jetstream/tasapiquery/$', run_tas_api_query, name='run_tas_api_query'),

    # DB Admin Panel for admin users
    url(r'^admin/', include(admin.site.urls))
]


if settings.DEBUG and 'debug_toolbar.middleware.DebugToolbarMiddleware' in settings.MIDDLEWARE_CLASSES:
    try:
        import debug_toolbar
        urlpatterns += (
            url(r'^__debug__/', include(debug_toolbar.urls)),
            )
    except ImportError:
        pass

urlpatterns += staticfiles_urlpatterns()
