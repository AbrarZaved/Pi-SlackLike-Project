from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import Communication.models


class Migration(migrations.Migration):

    dependencies = [
        ('Communication', '0006_directmessagethread_chatmessage_chatreaction_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ChatAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to=Communication.models._chat_attachment_upload_to)),
                ('kind', models.CharField(choices=[('image', 'Image'), ('audio', 'Audio'), ('video', 'Video'), ('file', 'File')], default='file', max_length=20)),
                ('original_name', models.CharField(blank=True, max_length=255)),
                ('content_type', models.CharField(blank=True, max_length=128)),
                ('size', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('message', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='Communication.chatmessage')),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_attachments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
