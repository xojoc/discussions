from django.contrib.auth.models import User, Group
from rest_framework import serializers


class UserSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="web:api:user-detail")

    class Meta:
        model = User
        fields = ['url', 'username', 'email', 'groups']


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ['url', 'name']


class DiscussionsOfURLSerializer(serializers.Serializer):
    platform_name = serializers.CharField()
    story_url = serializers.CharField()
    comment_count = serializers.IntegerField()
