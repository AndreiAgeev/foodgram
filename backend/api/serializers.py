import base64

from django.db import transaction
from django.core.files.base import ContentFile
from rest_framework import serializers

from api import utils
from recipes.models import Ingredient, Recipe, RecipeComposition, Tag, User


class Base64ImageField(serializers.ImageField):
    """Поле ImageField для декодирования полученной байтстроки
    в файл изображения."""

    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            mediatype, imgstr = data.split(';base64,')
            extension = mediatype.split('/')[-1]
            data = ContentFile(
                base64.b64decode(imgstr), name='image.' + extension
            )
            return super().to_internal_value(data)


class GetUserSerializer(serializers.ModelSerializer):
    """Сериализатор для просмотра пользователей."""
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('email', 'id', 'username', 'first_name',
                  'last_name', 'is_subscribed', 'avatar')

    def get_is_subscribed(self, obj):
        user = self.context['request'].user
        if not user.is_authenticated:
            return False
        return obj.user_subscribers.filter(subscriber=user).exists()


class PostUserSerializer(serializers.ModelSerializer):
    """Сериализатор для создания пользователей."""
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('email', 'username', 'first_name',
                  'last_name', 'password', 'id')


class AvatarSerializer(serializers.ModelSerializer):
    """Сериализатор для изиенения ававтаров пользователей."""
    avatar = Base64ImageField(required=False)

    class Meta:
        model = User
        fields = ('avatar',)

    def validate(self, attrs):
        if 'avatar' not in attrs and self.context['request'].method == 'PUT':
            raise serializers.ValidationError('Добавьте аватар')
        return super().validate(attrs)

    @transaction.atomic
    def update(self, instance, validated_data):
        if self.context['request'].method == 'PUT':
            instance.avatar = validated_data['avatar']
            instance.save()
        elif self.context['request'].method == 'DELETE':
            instance.avatar.delete()
        return instance


class TagSerializer(serializers.ModelSerializer):
    """Сериализатор для просмотра тегов."""

    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для просмотра ингредиентов."""

    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class IngredientInputSerializer(serializers.ModelSerializer):
    """Сериализатор для обработки полученого списка ингредиентов
    рецепта при его создании."""
    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(), source='ingredient', required=True
    )
    amount = serializers.IntegerField(min_value=1, required=True)
    name = serializers.CharField(source='ingredient.name', read_only=True)
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit',
        read_only=True
    )

    class Meta:
        model = RecipeComposition
        fields = ('id', 'name', 'measurement_unit', 'amount')
        read_only_fields = ('name', 'measurement_unit')


class RecipeSerializer(serializers.ModelSerializer):
    """Сериализатор для рецептов"""
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    author = GetUserSerializer(read_only=True)
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True,
        allow_null=False,
    )
    ingredients = IngredientInputSerializer(
        many=True,
        source='composition',
        allow_empty=False
    )
    image = Base64ImageField(allow_null=False, allow_empty_file=False)
    cooking_time = serializers.IntegerField(min_value=1)

    class Meta:
        model = Recipe
        fields = ('id', 'tags', 'author', 'ingredients', 'is_favorited',
                  'is_in_shopping_cart', 'name', 'image', 'text',
                  'cooking_time')
        read_only_fields = ('is_favorited', 'is_in_shopping_cart')

    def validate_tags(self, value):
        if not value:
            raise serializers.ValidationError('Укажите теги')
        if len(value) != len(set(value)):
            raise serializers.ValidationError('Теги не должны повторяться')
        return value

    def validate_image(self, value):
        if not value:
            raise serializers.ValidationError('Добавьте изображение')
        return value

    def validate_ingredients(self, value):
        ingredient_ids = map(lambda x: x['ingredient'].id, value)
        if len(value) != len(set(ingredient_ids)):
            raise serializers.ValidationError(
                'Ингредиенты не должны повторяться'
            )
        return value

    def validate(self, attrs):
        if 'composition' not in attrs:
            raise serializers.ValidationError(
                {'ingredients': 'Укажите ингредиенты'}
            )
        if 'tags' not in attrs:
            raise serializers.ValidationError(
                {'tags': 'Укажите теги'}
            )
        return super().validate(attrs)

    def get_is_favorited(self, obj):
        user = self.context['request'].user
        if not user.is_authenticated:
            return False
        return user.favorites.filter(id=obj.id).exists()

    def get_is_in_shopping_cart(self, obj):
        user = self.context['request'].user
        if not user.is_authenticated:
            return False
        return user.shopping_cart.filter(id=obj.id).exists()

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['tags'] = TagSerializer(
            instance.tags.all(), many=True
        ).data
        return representation

    @transaction.atomic
    def create(self, validated_data):
        tags = validated_data.pop('tags')
        ingredients = validated_data.pop('composition')
        recipe = Recipe.objects.create(
            author=self.context['request'].user,
            **validated_data
        )
        recipe.short_link = base64.b64encode(str(recipe.id).encode()).decode()
        recipe.save()
        recipe.tags.add(*tags)
        utils.save_ingredients(recipe, ingredients)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        tags = validated_data.pop('tags')
        ingredients = validated_data.pop('composition')
        recipe = super().update(instance, validated_data)
        recipe.tags.set(tags)
        recipe.composition.all().delete()
        utils.save_ingredients(recipe, ingredients)
        return recipe


class ShortLinkSerializer(serializers.ModelSerializer):
    """Сериализатор, возвращающий короткую ссылку на рецепт."""

    class Meta:
        model = Recipe
        fields = ('short_link',)
        read_only_fields = ('short_link',)

    def to_representation(self, instance):
        response = super().to_representation(instance)
        response['short-link'] = (
            self.context['request'].get_host()
            + '/s/'
            + response.pop('short_link')
        )
        return response


class FavoriteRecipeSerializer(serializers.ModelSerializer):
    """Сериализатор для обработки списка избранных и списка покупок"""

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
        read_only_fields = ('id', 'name', 'image', 'cooking_time')

    def get_obj_list(self, action):
        if action == 'favorite':
            return User.objects.filter(
                favorites=self.instance,
                id=self.context['request'].user.id
            )
        elif action == 'shopping_cart':
            return User.objects.filter(
                shopping_cart=self.instance,
                id=self.context['request'].user.id
            )

    def validate(self, attrs):
        VIEW_ACTION_NAME = {
            'favorite': 'избранном',
            'shopping_cart': 'списке покупок'
        }
        obj_list = utils.get_obj_list(
            self.instance,
            self.context['request'],
            self.context['view'].action
        )
        if (self.context['request'].method == 'DELETE'
                and not obj_list):
            raise serializers.ValidationError(
                "Данный рецепт не находится в "
                f"{VIEW_ACTION_NAME[self.context['view'].action]}"
            )
        elif (self.context['request'].method == 'POST'
                and obj_list):
            raise serializers.ValidationError(
                "Данный рецепт уже находится в "
                f"{VIEW_ACTION_NAME[self.context['view'].action]}"
            )
        return super().validate(attrs)


class DownloadShoppingCartSerializer(serializers.Serializer):
    """Возращает в виде объекта данные ингредиента и его количество."""
    name = serializers.CharField()
    measurement_unit = serializers.CharField()
    amount = serializers.IntegerField()


class SubscriptionSerializer(GetUserSerializer):
    """Сериализатор, изспользуемый для отображения списке подписок."""
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(
        source='recipes.count',
        read_only=True
    )

    class Meta(GetUserSerializer.Meta):
        fields = ('email', 'id', 'username', 'first_name',
                  'last_name', 'is_subscribed', 'avatar',
                  'recipes', 'recipes_count')
        read_only_fields = ('email', 'username', 'first_name',
                            'last_name', 'avatar', 'is_subscribed')

    def get_recipes(self, obj):
        recipes_limit = self.context['request'].GET.get('recipes_limit')
        if recipes_limit:
            try:
                recipes_limit = int(recipes_limit)
                return FavoriteRecipeSerializer(
                    obj.recipes.all()[:recipes_limit],
                    many=True
                ).data
            except ValueError:
                pass
        return FavoriteRecipeSerializer(obj.recipes.all(), many=True).data

    def validate(self, attrs):
        subscriber_list = User.objects.filter(
            subscribers=self.context['request'].user,
            id=self.instance.id
        )
        if self.instance == self.context['request'].user:
            raise serializers.ValidationError(
                'Нельзя подписаться на самого себя'
            )
        elif (self.context['request'].method == 'DELETE'
                and not subscriber_list):
            raise serializers.ValidationError(
                'Вы не подписаны на данного пользователя'
            )
        elif (self.context['request'].method == 'POST'
              and subscriber_list):
            raise serializers.ValidationError(
                'Вы уже подписаны на данного пользователя'
            )
        return super().validate(attrs)

    @transaction.atomic
    def update(self, instance, validated_data):
        if self.context['request'].method == 'POST':
            instance.subscribers.add(self.context['request'].user)
        elif self.context['request'].method == 'DELETE':
            instance.subscribers.remove(self.context['request'].user)
        return instance
