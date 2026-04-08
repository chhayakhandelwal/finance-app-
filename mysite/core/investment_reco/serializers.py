from rest_framework import serializers
from core.models import InvestmentRecommendation


class InvestmentRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentRecommendation
        fields = "__all__"