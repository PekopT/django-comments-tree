# Generated by Django 2.2.6 on 2019-10-23 16:25

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('django_comments_tree', '0005_treecomment_assoc'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commentassociation',
            name='root',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, to='django_comments_tree.TreeComment'),
        ),
    ]
