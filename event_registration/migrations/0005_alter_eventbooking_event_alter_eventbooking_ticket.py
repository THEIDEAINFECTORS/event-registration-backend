# Generated by Django 5.1.1 on 2024-09-19 18:02

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event_registration', '0004_alter_eventbooking_address_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='eventbooking',
            name='event',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='event_registration.event'),
        ),
        migrations.AlterField(
            model_name='eventbooking',
            name='ticket',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='event_registration.ticket'),
        ),
    ]
