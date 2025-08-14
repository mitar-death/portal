
import sentry_sdk
from server.app.core.config import settings

def init_sentry():
    """
    Initialize Sentry for error tracking and performance monitoring.
    This function should be called at the start of the application.
    """
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            send_default_pii=True,  # Send personally identifiable information
        )  
