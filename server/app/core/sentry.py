import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.asyncio import AsyncioIntegration

from server.app.core.config import settings

def init_sentry():
    """
    Initialize Sentry for error tracking and performance monitoring.
    This function should be called at the start of the application.
    
    Configures Sentry to capture logger.error calls and other exceptions.
    """
    if settings.SENTRY_DSN:

        # Initialize Sentry with proper integrations
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            
            # Add essential integrations
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                StarletteIntegration(),
                SqlalchemyIntegration(),
                AsyncioIntegration(),
            ],
            
            # Additional configuration
            send_default_pii=False,  # Don't send PII by default for privacy
            attach_stacktrace=True,  # Attach stacktraces to messages
            max_breadcrumbs=50,      # Store up to 50 breadcrumbs
            
            # Customize behavior
            before_send=before_send_event,
        )
        
        # Log successful initialization
        return True
    
    return False

def before_send_event(event, hint):
    """
    Filter and process events before sending to Sentry.
    This allows scrubbing sensitive data or ignoring certain errors.
    
    Args:
        event: The event dictionary
        hint: A dictionary containing additional information about the event
        
    Returns:
        Modified event or None if the event should be discarded
    """
    # Example: Ignore certain errors if needed
    if 'exc_info' in hint:
        exc_type, exc_value, tb = hint['exc_info']
        
        # Example: Ignore some expected exceptions (customize as needed)
        if isinstance(exc_value, (ConnectionResetError, ConnectionAbortedError)):
            # Don't report common connection issues
            return None
    
    # Scrub potential sensitive data from events
    if 'request' in event and 'headers' in event['request']:
        # Remove authentication headers
        headers = event['request']['headers']
        if 'authorization' in headers:
            headers['authorization'] = '[FILTERED]'
        if 'cookie' in headers:
            headers['cookie'] = '[FILTERED]'
    
    return event
