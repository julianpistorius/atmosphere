from core.models import Project, AtmosphereUser
from rest_framework import serializers
from .instance_summary_serializer import InstanceSummarySerializer
from .volume_summary_serializer import VolumeSummarySerializer
from .user_serializer import UserSerializer


class UserRelatedField(serializers.RelatedField):

    def __init__(self, **kwargs):
        kwargs['read_only'] = True
        super(UserRelatedField, self).__init__(**kwargs)

    def to_representation(self, value):
        username = value.__str__()
        user = AtmosphereUser.objects.get(username=username)
        serializer = UserSerializer(user)
        return serializer.data


class ProjectSerializer(serializers.ModelSerializer):
    instances = InstanceSummarySerializer(many=True, read_only=True)
    volumes = VolumeSummarySerializer(many=True, read_only=True)
    # note: both of these requests become a single DB query, but I'm choosing the
    # owner.name rate so the API doesn't break when we start adding users to groups
    # owner = UserSerializer(source='owner.user_set.first')
    owner = UserRelatedField(source='owner.name')

    class Meta:
        model = Project
        fields = ('id', 'name', 'description', 'owner', 'instances', 'volumes', 'start_date', 'end_date')
