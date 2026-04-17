"""Factory for initializing tracing clients based on configuration."""

from typing import Optional

from src.config import Settings, get_settings
from src.services.tracing.base import BaseTracer
import logging

logger = logging.getLogger(__name__)

_global_tracer = None

def get_tracer(settings: Optional[Settings] = None, force_new: bool = False) -> BaseTracer:
    """Factory function to create or get a tracing client based on settings.

    :param settings: Optional settings instance
    :param force_new: If True, bypasses the singleton and creates a new tracer
    :returns: BaseTracer instance
    """
    global _global_tracer
    
    if _global_tracer is not None and not force_new:
        return _global_tracer

    if settings is None:
        settings = get_settings()

    provider = settings.tracing_provider.lower()
    
    if provider == "langfuse":
        from src.services.tracing.langfuse_tracer import LangfuseTracer
        logger.debug("Initializing Langfuse Tracer")
        _global_tracer = LangfuseTracer(settings=settings.langfuse)
        return _global_tracer
        
    elif provider == "local":
        from src.services.tracing.local_tracer import LocalLogTracer
        logger.debug("Initializing Local Log Tracer")
        _global_tracer = LocalLogTracer(log_dir="logs")
        return _global_tracer
        
    else:
        raise ValueError(f"Unsupported Tracing Provider: {provider}. Options are 'langfuse' or 'local'.")

def shutdown_tracer():
    """Shutdown the global tracer."""
    global _global_tracer
    if _global_tracer is not None:
        _global_tracer.shutdown()
        _global_tracer = None
