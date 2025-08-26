from django.apps import AppConfig

class CommunicationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'communication'
    verbose_name = 'Communication Module'

    def ready(self):
        """Import signals when the app is ready"""
        try:
            import communication.signals
        except ImportError:
            pass
