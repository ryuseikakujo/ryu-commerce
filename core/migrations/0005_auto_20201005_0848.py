# Generated by Django 3.1.1 on 2020-10-04 23:48

from django.db import migrations
import stdimage.models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_auto_20201004_1135'),
    ]

    operations = [
        migrations.AlterField(
            model_name='item',
            name='image',
            field=stdimage.models.StdImageField(upload_to='path/to/img'),
        ),
    ]