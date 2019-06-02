# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-02-16 20:16
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('django_comments_tree', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MyComment',
            fields=[
                ('xtdcomment_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='django_comments_tree.TreeComment')),
                ('title', models.CharField(max_length=256)),
            ],
            options={
                'abstract': False,
            },
            bases=('django_comments_tree.treecomment',),
        ),
    ]
