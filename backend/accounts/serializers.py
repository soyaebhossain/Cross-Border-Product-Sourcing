from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ["username", "email", "phone", "password", "role"]

    def validate(self, data):
        if not data.get("email") and not data.get("phone"):
            raise serializers.ValidationError(
                "Either email or phone is required"
            )
        return data

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "phone", "role"]

class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()  # email OR phone
    password = serializers.CharField(write_only=True)