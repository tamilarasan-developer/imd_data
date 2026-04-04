from rest_framework import serializers
from imd.models import imd_data


class ImdDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = imd_data
        fields = ['date',"cluster","maximum_past_24hrs","minimum_past_24hrs"]