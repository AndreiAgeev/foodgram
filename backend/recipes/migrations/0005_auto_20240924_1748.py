# Generated by Django 3.2.3 on 2024-09-24 17:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0004_auto_20240924_1445'),
    ]

    operations = [
        migrations.AlterField(
            model_name='recipe',
            name='author',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='recipes', to='recipes.user', verbose_name='Автор'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='subscribtions',
            name='subscriber',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='user_subscriptions', to='recipes.user'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='subscribtions',
            name='user',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='user_subscribers', to='recipes.user'),
            preserve_default=False,
        ),
    ]
