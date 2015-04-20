from datetime import timedelta

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as AuthUserAdmin
from django.contrib.auth.models import User as DjangoUser
from django.contrib.auth.models import Group as DjangoGroup
from django.contrib.sessions.models import Session as DjangoSession
from django.utils import timezone

from core.models.abstract import InstanceSource
from core.models.application import Application
from core.models.credential import Credential, ProviderCredential
from core.models.group import Group, IdentityMembership, ProviderMembership
from core.models.identity import Identity
from core.models.instance import Instance, InstanceStatusHistory
from core.models.machine import ProviderMachine, ProviderMachineMembership
from core.models.machine_request import MachineRequest
from core.models.maintenance import MaintenanceRecord
from core.models.node import NodeController
from core.models.profile import UserProfile
from core.models.provider import Provider, ProviderType
from core.models.quota import Quota
from core.models.allocation import Allocation
from core.models.size import Size
from core.models.step import Step
from core.models.tag import Tag
from core.models.user import AtmosphereUser
from core.models.volume import Volume

from core.application import save_app_to_metadata
from threepio import logger

def private_object(modeladmin, request, queryset):
        queryset.update(private=True)
private_object.short_description = 'Make objects private True'

def end_date_object(modeladmin, request, queryset):
        queryset.update(end_date=timezone.now())
end_date_object.short_description = 'Add end-date to objects'


class NodeControllerAdmin(admin.ModelAdmin):
    actions = [end_date_object, ]
    list_display = ("alias", "hostname",
                    "start_date", "end_date",
                    "ssh_key_added")


class MaintenanceAdmin(admin.ModelAdmin):
    actions = [end_date_object, ]
    list_display = ("title", "provider", "start_date",
                    "end_date", "disable_login")


class QuotaAdmin(admin.ModelAdmin):
    list_display = ("__unicode__", "cpu", "memory", "storage", "storage_count", "suspended_count")


class AllocationAdmin(admin.ModelAdmin):

    list_display = ("threshold_str", "delta_str")

    def threshold_str(self, obj):
        td = timedelta(minutes=obj.threshold)
        return '%s days, %s hours, %s minutes' % (td.days,
                                                  td.seconds // 3600,
                                                  (td.seconds // 60) % 60)
    threshold_str.short_description = 'Threshold'

    def delta_str(self, obj):
        td = timedelta(minutes=obj.delta)
        return '%s days, %s hours, %s minutes' % (td.days,
                                                  td.seconds // 3600,
                                                  (td.seconds // 60) % 60)
    delta_str.short_description = 'Delta'


class ProviderMachineAdmin(admin.ModelAdmin):
    actions = [end_date_object, ]
    search_fields = ["application__name", "provider__location", "identifier"]
    list_display = ["source_identifier",
            "source_provider", "application",
            "source_end_date"]
    list_filter = [
        "instancesource_ptr__provider__location",
        "application__private",
    ]
    def render_change_form(self, request, context, *args, **kwargs):
        pm = context['original']
        #context['adminform'].form.fields['instance_source'].queryset = InstanceSource.objects.filter(id=pm.instancesource_ptr.id)
        return super(ProviderMachineAdmin, self).render_change_form(request, context, *args, **kwargs)

class ProviderMachineMembershipAdmin(admin.ModelAdmin):
    list_display = ["id", "_pm_provider", "_pm_identifier", "_pm_name",
                    "_pm_private", "group"]
    list_filter = [
            "provider_machine__provider__location",
            "provider_machine__identifier",
            "group__name"
            ]
    def _pm_provider(self, obj):
        return obj.provider_machine.provider.location
    def _pm_private(self, obj):
        return obj.provider_machine.application.private
    _pm_private.boolean = True
    def _pm_identifier(self, obj):
        return obj.provider_machine.identifier
    def _pm_name(self, obj):
        return obj.provider_machine.application.name
    pass

class ProviderCredentialInline(admin.TabularInline):
    model = ProviderCredential
    extra = 1


class ProviderAdmin(admin.ModelAdmin):
    inlines = [ProviderCredentialInline, ]
    actions = [end_date_object, ]
    list_display = ["location", "id", "provider_type", "active",
                    "public", "start_date", "end_date", "_credential_info"]
    list_filter = ["active", "public", "type__name"]
    def _credential_info(self, obj):
        return_text = ""
        for cred in obj.providercredential_set.order_by('key'):
            return_text += "<strong>%s</strong>:%s<br/>" % (cred.key, cred.value)
        return return_text
    _credential_info.allow_tags = True
    _credential_info.short_description = 'Provider Credentials'

    def provider_type(self, provider):
        if provider.type:
            return provider.type.name
        return None


class SizeAdmin(admin.ModelAdmin):
    actions = [end_date_object, ]
    search_fields = ["name", "alias", "provider__location"]
    list_display = ["name", "provider", "cpu", "mem", "disk",
                    "start_date", "end_date"]
    list_filter = ["provider__location"]


class StepAdmin(admin.ModelAdmin):
    search_fields = ["name", "alias", "created_by__username",
                     "instance__provider_alias"]
    list_display = ["alias", "name", "start_date", "end_date"]


class TagAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    list_display = ["name", "description"]


class VolumeAdmin(admin.ModelAdmin):
    actions = [end_date_object, ]
    search_fields = ["source_identifier", "name", "source_location"]
    list_display = ["source_identifier", "size", "source_provider",
            "source_start_date", "source_end_date"]
    list_filter = ["instancesource_ptr__provider__location"]


class ApplicationAdmin(admin.ModelAdmin):
    actions = [end_date_object, private_object]
    search_fields = ["name", "id", "providermachine__identifier"]
    list_display = ["uuid", "_current_machines", "name", "private", "created_by", "start_date", "end_date" ]
    filter_vertical = ["tags",]
    def save_model(self, request, obj, form, change):
        user = request.user
        application = form.save(commit=False)
        application.save()
        form.save_m2m()
        if change:
            try:
                save_app_to_metadata(application)
            except Exception, e:
                logger.exception("Could not update metadata for application %s"
                                 % application)
        return application

    def render_change_form(self, request, context, *args, **kwargs):
        application = context['original']
        context['adminform'].form.fields['created_by_identity'].queryset = Identity.objects.filter(created_by=application.created_by)
        return super(ApplicationAdmin, self).render_change_form(request, context, *args, **kwargs)

class CredentialInline(admin.TabularInline):
    model = Credential
    extra = 1


class IdentityAdmin(admin.ModelAdmin):
    inlines = [CredentialInline, ]
    list_display = ("created_by", "provider", "_credential_info")
    search_fields = ["created_by__username"]
    list_filter = ["provider__location"]

    def _credential_info(self, obj):
        return_text = ""
        for cred in obj.credential_set.order_by('key'):
            return_text += "<strong>%s</strong>:%s<br/>" % (cred.key, cred.value)
        return return_text
    _credential_info.allow_tags = True
    _credential_info.short_description = 'Credentials'


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    max_num = 1
    can_delete = False
    extra = 0
    verbose_name_plural = 'profile'


class UserAdmin(AuthUserAdmin):
    inlines = [UserProfileInline]

#admin.site.unregister(DjangoUser)
admin.site.register(AtmosphereUser, UserAdmin)


class ProviderMembershipAdmin(admin.ModelAdmin):
    search_fields = ["member__name"]
    list_filter = ["provider__location"]

#class IdentityMembershipForm(forms.ModelForm):
#    def __init__(self, instance, *args, **kwargs):
#        super(IdentityMembershipForm, self).__init__(*args, **kwargs)
#        self.fields['identity'].queryset =

class IdentityMembershipAdmin(admin.ModelAdmin):
    search_fields = ["identity__created_by__username", ]
    list_display = ["_identity_user", "_identity_provider",
                    "quota", "allocation"]
    list_filter = ["identity__provider__location", "allocation"]

    def render_change_form(self, request, context, *args, **kwargs):
        identity_membership = context['original']
        #TODO: Change when created_by is != the user who 'owns' this identity...
        user = identity_membership.identity.created_by
        context['adminform'].form.fields['identity'].queryset = user.identity_set.all()
        context['adminform'].form.fields['member'].queryset = user.group_set.all()
        return super(IdentityMembershipAdmin, self).render_change_form(request, context, *args, **kwargs)

    def _identity_provider(self, obj):
        return obj.identity.provider.location
    _identity_provider.short_description = 'Provider'

    def _identity_user(self, obj):
        return obj.identity.created_by.username
    _identity_user.short_description = 'Username'


class MachineRequestAdmin(admin.ModelAdmin):
    search_fields = ["new_machine_owner__username", "new_machine_name", "instance__provider_alias"]
    list_display = ["new_machine_name", "instance_alias", "opt_new_machine", "new_machine_owner", "old_provider",
                    "new_machine_provider",  "start_date",
                    "end_date", "status", "opt_parent_machine", "opt_machine_visibility"]
    list_filter = ["instance__source__provider__location",
                   "new_machine_provider__location",
                   "new_machine_visibility",
                   "status"]

    #Overwrite
    def render_change_form(self, request, context, *args, **kwargs):
        machine_request = context['original']
        #TODO: Change when created_by is != the user who 'owns' this identity...
        instance = machine_request.instance
        user = machine_request.new_machine_owner
        provider = machine_request.new_machine_provider
        context['adminform'].form.fields['new_machine_owner'].queryset = provider.list_users()
        context['adminform'].form.fields['new_machine'].queryset = ProviderMachine.objects.filter(instancesource_ptr__provider=provider)
        context['adminform'].form.fields['instance'].queryset = user.instance_set.all()
        #NOTE: Can't reliably refine 'parent_machine' -- Since the parent could be from another provider.
        context['adminform'].form.fields['parent_machine'].queryset = ProviderMachine.objects.filter(instancesource_ptr__identifier=instance.source.identifier)

        return super(MachineRequestAdmin, self).render_change_form(request, context, *args, **kwargs)

    def opt_machine_visibility(self, machine_request):
        if machine_request.new_machine_visibility.lower() != 'public':
            return "%s\nUsers:%s" % (machine_request.new_machine_visibility,
                                        machine_request.access_list)
        return machine_request.new_machine_visibility
    opt_machine_visibility.allow_tags = True

    def opt_parent_machine(self, machine_request):
        if machine_request.parent_machine:
            return machine_request.parent_machine.identifier
        return None

    def opt_new_machine(self, machine_request):
        if machine_request.new_machine:
            return machine_request.new_machine.identifier
        return None


class InstanceStatusHistoryAdmin(admin.ModelAdmin):
    search_fields = ["instance__created_by__username",
            "instance__provider_alias", "status__name"]
    list_display = ["instance_alias", "status", "start_date", "end_date"]
    list_filter = ["instance__source__provider__location",
                   "status__name"]
    ordering = ('-start_date',)
    def instance_alias(self, model):
        return model.instance.provider_alias


class InstanceAdmin(admin.ModelAdmin):
    search_fields = ["created_by__username", "provider_alias", "ip_address"]
    list_display = ["provider_alias", "name", "created_by", "ip_address"]
    list_filter = ["source__provider__location"]

class SessionAdmin(admin.ModelAdmin):
    def _session_data(self, obj):
        return obj.get_decoded()
    list_display = ['session_key', '_session_data', 'expire_date']
    search_fields = ["session_key", ]

admin.site.register(DjangoSession, SessionAdmin)
admin.site.register(Credential)
admin.site.unregister(DjangoGroup)
admin.site.register(Group)
admin.site.register(Application, ApplicationAdmin)
admin.site.register(Allocation, AllocationAdmin)
admin.site.register(Identity, IdentityAdmin)
admin.site.register(IdentityMembership, IdentityMembershipAdmin)
admin.site.register(Instance, InstanceAdmin)
admin.site.register(InstanceStatusHistory, InstanceStatusHistoryAdmin)
admin.site.register(MachineRequest, MachineRequestAdmin)
admin.site.register(MaintenanceRecord, MaintenanceAdmin)
admin.site.register(NodeController, NodeControllerAdmin)
admin.site.register(Provider, ProviderAdmin)
admin.site.register(ProviderMachine, ProviderMachineAdmin)
admin.site.register(ProviderMachineMembership, ProviderMachineMembershipAdmin)
admin.site.register(ProviderMembership, ProviderMembershipAdmin)
admin.site.register(ProviderType)
admin.site.register(Quota, QuotaAdmin)
admin.site.register(Size, SizeAdmin)
admin.site.register(Step, StepAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(Volume, VolumeAdmin)
