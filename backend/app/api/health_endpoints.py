"""
Comprehensive Health Check Endpoints

This module provides detailed health check endpoints for monitoring
all system components including database, cache, external services,
and application health.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import asyncio
import time
import psutil
import structlog
from datetime import datetime, timedelta
from app.database.database import database_health_check
from app.utils.performance_monitor import performance_monitor

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def basic_health_check() -> Dict[str, Any]:
    """Basic health check for load balancer probes"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "finops-api"
    }


@router.get("/ready")
async def readiness_probe() -> Dict[str, Any]:
    """Kubernetes readiness probe - checks if service is ready to receive traffic"""
    try:
        # Check critical dependencies
        db_health = await database_health_check()
        
        if db_health["status"] != "healthy":
            raise HTTPException(status_code=503, detail="Service not ready")
        
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "database": db_health["status"]
            }
        }
    except Exception as e:
        logger.error("Readiness probe failed", error=str(e))
        raise HTTPException(status_code=503, detail=f"Service not ready: {str(e)}")


@router.get("/live")
async def liveness_probe() -> Dict[str, Any]:
    """Kubernetes liveness probe - checks if service is alive"""
    try:
        # Basic application health check
        start_time = time.time()
        
        # Simple computation to verify application is responsive
        test_computation = sum(range(1000))
        
        response_time = (time.time() - start_time) * 1000
        
        if response_time > 5000:  # 5 second threshold
            raise HTTPException(status_code=503, detail="Service too slow")
        
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat(),
            "response_time_ms": response_time,
            "test_result": test_computation
        }
    except Exception as e:
        logger.error("Liveness probe failed", error=str(e))
        raise HTTPException(status_code=503, detail=f"Service not alive: {str(e)}")


@router.get("/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """Comprehensive health check with detailed component status"""
    try:
        start_time = time.time()
        
        # Run all health checks concurrently
        db_task = asyncio.create_task(database_health_check())
        system_task = asyncio.create_task(get_system_metrics())
        performance_task = asyncio.create_task(get_performance_health())
        
        # Wait for all checks to complete
        db_health, system_metrics, performance_health = await asyncio.gather(
            db_task, system_task, performance_task,
            return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(db_health, Exception):
            db_health = {"status": "unhealthy", "error": str(db_health)}
        if isinstance(system_metrics, Exception):
            system_metrics = {"status": "unhealthy", "error": str(system_metrics)}
        if isinstance(performance_health, Exception):
            performance_health = {"status": "unhealthy", "error": str(performance_health)}
        
        # Determine overall health
        overall_status = "healthy"
        critical_components = [db_health]
        
        for component in critical_components:
            if component.get("status") != "healthy":
                overall_status = "unhealthy"
                break
        
        # Check for degraded performance
        if overall_status == "healthy":
            if (system_metrics.get("cpu_percent", 0) > 80 or 
                system_metrics.get("memory_percent", 0) > 85):
                overall_status = "degraded"
        
        total_time = (time.time() - start_time) * 1000
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "response_time_ms": total_time,
            "version": "1.0.0",
            "environment": "production",
            "components": {
                "database": db_health,
                "system": system_metrics,
                "performance": performance_health
            },
            "uptime": get_uptime(),
            "build_info": {
                "version": "1.0.0",
                "build_date": "2024-01-01",
                "git_commit": "unknown"
            }
        }
        
    except Exception as e:
        logger.error("Detailed health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "error_type": type(e).__name__
        }


@router.get("/dependencies")
async def dependencies_health_check() -> Dict[str, Any]:
    """Check health of external dependencies"""
    try:
        dependencies = {}
        
        # Database dependency
        db_health = await database_health_check()
        dependencies["postgresql"] = {
            "status": db_health["status"],
            "response_time_ms": db_health.get("response_time_ms", 0),
            "required": True
        }
        
        # Redis dependency
        redis_health = await redis_manager.health_check()
        dependencies["redis"] = {
            "status": redis_health["status"],
            "response_time_ms": redis_health.get("response_time_ms", 0),
            "required": True
        }
        
        # Check external APIs (mock for now)
        dependencies["aws_cost_explorer"] = await check_aws_api_health()
        dependencies["external_apis"] = await check_external_apis_health()
        
        # Determine overall dependency health
        critical_deps = ["postgresql", "redis"]
        overall_status = "healthy"
        
        for dep_name in critical_deps:
            if dependencies[dep_name]["status"] != "healthy":
                overall_status = "unhealthy"
                break
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "dependencies": dependencies
        }
        
    except Exception as e:
        logger.error("Dependencies health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


async def get_system_metrics() -> Dict[str, Any]:
    """Get system resource metrics"""
    try:
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Memory metrics
        memory = psutil.virtual_memory()
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        
        # Network metrics (if available)
        try:
            network = psutil.net_io_counters()
            network_stats = {
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
                "packets_sent": network.packets_sent,
                "packets_recv": network.packets_recv
            }
        except:
            network_stats = {}
        
        return {
            "status": "healthy",
            "cpu_percent": cpu_percent,
            "cpu_count": cpu_count,
            "memory_total": memory.total,
            "memory_available": memory.available,
            "memory_percent": memory.percent,
            "disk_total": disk.total,
            "disk_used": disk.used,
            "disk_free": disk.free,
            "disk_percent": (disk.used / disk.total) * 100,
            "network": network_stats
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def get_performance_health() -> Dict[str, Any]:
    """Get application performance health"""
    try:
        # Get performance metrics from monitor
        if hasattr(performance_monitor, 'get_performance_summary'):
            perf_summary = await performance_monitor.get_performance_summary()
            
            # Analyze performance health
            status = "healthy"
            issues = []
            
            # Check API response times
            api_metrics = perf_summary.get("api_metrics", {})
            for endpoint, metrics in api_metrics.items():
                avg_time = metrics.get("average_response_time", 0)
                if avg_time > 2.0:  # 2 second threshold
                    status = "degraded"
                    issues.append(f"Slow response time for {endpoint}: {avg_time:.2f}s")
            
            # Check cache performance
            cache_metrics = perf_summary.get("cache_metrics", {})
            hit_ratio = cache_metrics.get("hit_ratio", 1.0)
            if hit_ratio < 0.7:  # 70% threshold
                status = "degraded"
                issues.append(f"Low cache hit ratio: {hit_ratio:.2%}")
            
            return {
                "status": status,
                "issues": issues,
                "metrics": perf_summary
            }
        else:
            return {
                "status": "healthy",
                "message": "Performance monitoring not available"
            }
            
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def check_aws_api_health() -> Dict[str, Any]:
    """Check AWS API connectivity (mock implementation)"""
    try:
        # This would normally test AWS API connectivity
        # For now, return a mock healthy status
        return {
            "status": "healthy",
            "response_time_ms": 150,
            "required": False,
            "last_check": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "required": False
        }


async def check_external_apis_health() -> Dict[str, Any]:
    """Check other external API dependencies"""
    try:
        # Mock implementation for external API health checks
        return {
            "status": "healthy",
            "apis_checked": 0,
            "apis_healthy": 0,
            "last_check": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


def get_uptime() -> Dict[str, Any]:
    """Get application uptime information"""
    try:
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        
        return {
            "uptime_seconds": uptime_seconds,
            "uptime_human": str(timedelta(seconds=int(uptime_seconds))),
            "boot_time": datetime.fromtimestamp(boot_time).isoformat()
        }
    except Exception as e:
        return {
            "error": str(e)
        }


@router.get("/metrics")
async def get_health_metrics() -> Dict[str, Any]:
    """Get health metrics in Prometheus format"""
    try:
        # Get basic health status
        db_health = await database_health_check()
        redis_health = await redis_manager.health_check()
        system_metrics = await get_system_metrics()
        
        # Convert to Prometheus-style metrics
        metrics = []
        
        # Health status metrics (1 = healthy, 0 = unhealthy)
        metrics.append(f'finops_database_health{{status="{db_health["status"]}"}} {1 if db_health["status"] == "healthy" else 0}')
        metrics.append(f'finops_redis_health{{status="{redis_health["status"]}"}} {1 if redis_health["status"] == "healthy" else 0}')
        
        # System metrics
        if system_metrics.get("status") == "healthy":
            metrics.append(f'finops_cpu_usage_percent {system_metrics.get("cpu_percent", 0)}')
            metrics.append(f'finops_memory_usage_percent {system_metrics.get("memory_percent", 0)}')
            metrics.append(f'finops_disk_usage_percent {system_metrics.get("disk_percent", 0)}')
        
        # Response time metrics
        if "response_time_ms" in db_health:
            metrics.append(f'finops_database_response_time_ms {db_health["response_time_ms"]}')
        if "response_time_ms" in redis_health:
            metrics.append(f'finops_redis_response_time_ms {redis_health["response_time_ms"]}')
        
        return {
            "metrics": "\n".join(metrics),
            "content_type": "text/plain"
        }
        
    except Exception as e:
        logger.error("Health metrics generation failed", error=str(e))
        return {
            "error": str(e),
            "metrics": f'finops_health_check_error{{error="{str(e)}"}} 1'
        }
