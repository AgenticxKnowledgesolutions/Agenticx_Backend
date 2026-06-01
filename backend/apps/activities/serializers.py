from rest_framework import serializers
from apps.activities.models import Activity

class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = '__all__'

    def validate_title(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Title cannot be empty.")
        return value

    def validate(self, attrs):
        is_free = attrs.get('is_free', False)
        price = attrs.get('price')

        if price is not None and price < 0:
            raise serializers.ValidationError({
                "price": "Price cannot be negative."
            })

        if is_free and price is not None and price > 0:
            raise serializers.ValidationError({
                "price": "Price must be blank or 0 for a free activity."
            })
        
        if not is_free and (price is None or price <= 0):
            raise serializers.ValidationError({
                "price": "Price must be greater than 0 for a paid activity."
            })

        return attrs
