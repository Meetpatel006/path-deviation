"""
FastAPI application entry point
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time

from app.config import settings
from app.database import init_db, close_pg_pool
from app.utils.logger import logger
from app.api import routes
from app.api import websocket as websocket_routes
from app.services.redis_client import get_redis, close_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events
    """
    # Startup
    logger.info("Starting Path Deviation Detection System...")
    logger.info(f"Log level: {settings.LOG_LEVEL}")
    
    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    # Validate Mapbox API key
    if not settings.MAPBOX_API_KEY or settings.MAPBOX_API_KEY == "your_mapbox_api_key_here":
        logger.warning("Mapbox API key not configured! Please set MAPBOX_API_KEY in .env file")
    else:
        logger.info("Mapbox API key configured")

    # Initialize Redis (Upstash) if configured
    try:
        await get_redis()
    except Exception as e:
        logger.error(f"Failed to initialize Upstash Redis: {e}", exc_info=True)
    
    logger.info("Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    await close_redis()
    await close_pg_pool()  # Close PostgreSQL connection pool
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="GPS Path Deviation Detection System",
    description="Real-time GPS tracking system that detects when users deviate from planned routes",
    version="1.0.0",
    lifespan=lifespan
)


# CORS middleware (allow frontend to access API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests"""
    start_time = time.time()
    
    # Log request
    logger.info(f"→ {request.method} {request.url.path}")
    
    # Process request
    response = await call_next(request)
    
    # Log response
    duration = time.time() - start_time
    logger.info(
        f"← {request.method} {request.url.path} "
        f"[{response.status_code}] ({duration:.3f}s)"
    )
    
    return response


# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle validation errors"""
    logger.error(f"Validation error: {exc}")
    return JSONResponse(
        status_code=400,
        content={"error": "Validation Error", "detail": str(exc)}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors"""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": "An unexpected error occurred"}
    )


# Include routers
app.include_router(routes.router)
app.include_router(websocket_routes.router)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    redis_status = "disabled"
    try:
        redis = await get_redis()
        if redis is not None:
            redis_ok = await redis.ping()
            redis_status = "connected" if redis_ok else "disconnected"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}", exc_info=True)
        redis_status = "disconnected"
    
    return {
        "status": "healthy",
        "version": "1.0.0",
        "database": "connected",
        "redis": redis_status
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "GPS Path Deviation Detection System API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}")
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,  # Development mode
        log_level=settings.LOG_LEVEL.lower()
    )
