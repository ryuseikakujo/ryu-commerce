# Generated by Django 3.1.1 on 2020-10-04 23:56

from django.db import migrations
import stdimage.models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_auto_20201005_0848'),
    ]

    operations = [
        migrations.AlterField(
            model_name='item',
            name='image',
            field=stdimage.models.StdImageField(upload_to='media/'),
        ),
    ]
