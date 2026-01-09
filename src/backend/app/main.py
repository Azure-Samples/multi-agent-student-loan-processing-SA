from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import chat_routes, status_routes
from app.config.settings import settings
from app.config.logging_config import get_logger, setup_logging
from app.config.azure_chat_client_factory import Container



def create_app() -> FastAPI:
    # Initialize logging for the app
    setup_logging()
    # Get logger for this module
    logger = get_logger(__name__)

    # Setup agent framework observability (optional - if available)
    if settings.ENABLE_OTEL:
        try:
            from agent_framework.observability import setup_observability
            setup_observability(enable_sensitive_data=settings.ENABLE_OTEL,applicationinsights_connection_string=settings.APPLICATIONINSIGHTS_CONNECTION_STRING)
        except ImportError:
            logger.warning("Observability setup unavailable - continuing without it")

    logger.info(f"Creating FastAPI application: {settings.APP_NAME}")
    
    app = FastAPI(title=settings.APP_NAME)
   
    # Add CORS middleware with explicit configuration
    logger.info("Configuring CORS middleware to allow all origins")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
   
    # Initialize dependency injection container
    container = Container()
    
    # Wire dependencies to modules that need them
    container.wire(modules=[chat_routes, status_routes])
    
    # Store container in app state for potential cleanup
    app.state.container = container

    # Use FastAPI lifespan for startup and shutdown events
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        logger.info("Shutting down application...")
        container.unwire()

    app.router.lifespan_context = lifespan

    # Include routers
    app.include_router(chat_routes.router, prefix="/api", tags=["chat"])
    app.include_router(status_routes.router, prefix="/api", tags=["status"])


    logger.info("FastAPI application created successfully")
    return app


app = create_app()
