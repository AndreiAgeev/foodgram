# Generated by Django 3.2.3 on 2024-09-28 09:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0006_user_favorites'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='shopping_cart',
            field=models.ManyToManyField(related_name='in_shopping_cart', to='recipes.Recipe', verbose_name='Список покупок'),
        ),
    ]
