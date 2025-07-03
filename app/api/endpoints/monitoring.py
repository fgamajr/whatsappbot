from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any
import asyncio
import logging
from app.infrastructure.metrics_collector import metrics_collector
from app.infrastructure.auto_scaler import auto_scaler
from app.infrastructure.websocket_manager import websocket_manager
from app.infrastructure.prometheus_metrics import prometheus_metrics
from app.utils.secure_logging import SecureLogger

router = APIRouter(prefix="/monitoring", tags=["monitoring"])
logger = logging.getLogger(__name__)

@router.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": "2025-01-03T12:00:00Z",
        "services": {
            "metrics_collector": metrics_collector.running,
            "auto_scaler": auto_scaler.running,
            "websocket_manager": len(websocket_manager.active_connections) > 0 or True
        }
    }

@router.get("/metrics/current")
async def get_current_metrics():
    """Get current system metrics"""
    try:
        current_metrics = metrics_collector.get_current_metrics()
        return {
            "status": "success",
            "data": current_metrics,
            "timestamp": "2025-01-03T12:00:00Z"
        }
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to get current metrics", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")

@router.get("/auto-scaling/status")
async def get_auto_scaling_status():
    """Get auto-scaling status and recent decisions"""
    try:
        status = auto_scaler.get_scaling_status()
        return {
            "status": "success",
            "data": status,
            "timestamp": "2025-01-03T12:00:00Z"
        }
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to get auto-scaling status", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve auto-scaling status")

@router.post("/auto-scaling/toggle")
async def toggle_auto_scaling(enable: bool = True):
    """Enable or disable auto-scaling"""
    try:
        if enable:
            auto_scaler.enable_auto_scaling()
            message = "Auto-scaling enabled"
        else:
            auto_scaler.disable_auto_scaling()
            message = "Auto-scaling disabled"
        
        return {
            "status": "success",
            "message": message,
            "enabled": auto_scaler.enabled
        }
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to toggle auto-scaling", e)
        raise HTTPException(status_code=500, detail="Failed to toggle auto-scaling")

@router.get("/websockets/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics"""
    try:
        stats = websocket_manager.get_connection_stats()
        return {
            "status": "success",
            "data": stats,
            "timestamp": "2025-01-03T12:00:00Z"
        }
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to get WebSocket stats", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve WebSocket statistics")

@router.post("/prometheus/start")
async def start_prometheus_server(port: int = 8001):
    """Start Prometheus metrics server"""
    try:
        prometheus_metrics.start_metrics_server(port)
        return {
            "status": "success",
            "message": f"Prometheus metrics server started on port {port}",
            "endpoint": f"http://localhost:{port}/metrics"
        }
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to start Prometheus server", e)
        raise HTTPException(status_code=500, detail="Failed to start Prometheus metrics server")

@router.get("/system/overview")
async def get_system_overview():
    """Get comprehensive system overview"""
    try:
        metrics = metrics_collector.get_current_metrics()
        scaling_status = auto_scaler.get_scaling_status()
        websocket_stats = websocket_manager.get_connection_stats()
        
        # Calculate system health score
        health_score = calculate_system_health(metrics)
        
        return {
            "status": "success",
            "data": {
                "health_score": health_score,
                "metrics": metrics,
                "auto_scaling": scaling_status,
                "websockets": websocket_stats,
                "recommendations": generate_recommendations(metrics, scaling_status)
            },
            "timestamp": "2025-01-03T12:00:00Z"
        }
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to get system overview", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve system overview")

@router.post("/alerts/webhook")
async def handle_alert_webhook(request: Request):
    """Handle incoming alerts from Alertmanager"""
    try:
        alert_data = await request.json()
        
        SecureLogger.safe_log_info(logger, "Alert received", {
            "alert_count": len(alert_data.get("alerts", [])),
            "status": alert_data.get("status", "unknown")
        })
        
        # Process alerts and potentially trigger notifications
        await process_alerts(alert_data)
        
        return {"status": "success", "message": "Alert processed"}
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to process alert webhook", e)
        raise HTTPException(status_code=500, detail="Failed to process alert")

@router.get("/performance/report")
async def get_performance_report():
    """Get detailed performance report"""
    try:
        metrics = metrics_collector.get_current_metrics()
        
        # Calculate performance metrics
        total_tasks = sum(q.get('tasks_processing', 0) for q in metrics.get('queues', {}).values())
        total_queued = sum(q.get('length', 0) for q in metrics.get('queues', {}).values())
        
        system_metrics = metrics.get('system', {})
        throughput = system_metrics.get('throughput_per_minute', 0)
        error_rate = system_metrics.get('error_rate', 0)
        
        # Performance analysis
        performance_analysis = {
            "overall_health": "good" if error_rate < 5 else "warning" if error_rate < 15 else "critical",
            "queue_health": "good" if total_queued < 10 else "warning" if total_queued < 50 else "critical",
            "throughput_status": "good" if throughput > 5 else "warning" if throughput > 1 else "low",
            "bottlenecks": identify_bottlenecks(metrics),
            "recommendations": generate_performance_recommendations(metrics)
        }
        
        return {
            "status": "success",
            "data": {
                "metrics": metrics,
                "analysis": performance_analysis,
                "summary": {
                    "total_active_tasks": total_tasks,
                    "total_queued_tasks": total_queued,
                    "throughput_per_minute": throughput,
                    "error_rate_percent": error_rate
                }
            },
            "timestamp": "2025-01-03T12:00:00Z"
        }
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to generate performance report", e)
        raise HTTPException(status_code=500, detail="Failed to generate performance report")

def calculate_system_health(metrics: Dict[str, Any]) -> int:
    """Calculate system health score (0-100)"""
    score = 100
    
    system_metrics = metrics.get('system', {})
    error_rate = system_metrics.get('error_rate', 0)
    total_queued = system_metrics.get('total_queued_tasks', 0)
    total_workers = system_metrics.get('total_workers', 0)
    
    # Deduct points for issues
    if error_rate > 10:
        score -= 30
    elif error_rate > 5:
        score -= 15
    
    if total_queued > 50:
        score -= 25
    elif total_queued > 20:
        score -= 10
    
    if total_workers == 0:
        score -= 50
    
    return max(0, score)

def identify_bottlenecks(metrics: Dict[str, Any]) -> list:
    """Identify system bottlenecks"""
    bottlenecks = []
    
    queues = metrics.get('queues', {})
    for queue_name, queue_data in queues.items():
        length = queue_data.get('length', 0)
        if length > 10:
            bottlenecks.append(f"High queue length in {queue_name}: {length} tasks")
    
    system_metrics = metrics.get('system', {})
    if system_metrics.get('total_workers', 0) == 0:
        bottlenecks.append("No active workers available")
    
    if system_metrics.get('error_rate', 0) > 10:
        bottlenecks.append("High error rate detected")
    
    return bottlenecks

def generate_recommendations(metrics: Dict[str, Any], scaling_status: Dict[str, Any]) -> list:
    """Generate system recommendations"""
    recommendations = []
    
    system_metrics = metrics.get('system', {})
    total_queued = system_metrics.get('total_queued_tasks', 0)
    
    if total_queued > 20:
        recommendations.append("Consider scaling up workers to handle queue backlog")
    
    if not scaling_status.get('enabled', False):
        recommendations.append("Enable auto-scaling for automatic capacity management")
    
    if system_metrics.get('error_rate', 0) > 5:
        recommendations.append("Investigate and fix recurring task failures")
    
    return recommendations

def generate_performance_recommendations(metrics: Dict[str, Any]) -> list:
    """Generate performance-specific recommendations"""
    recommendations = []
    
    system_metrics = metrics.get('system', {})
    throughput = system_metrics.get('throughput_per_minute', 0)
    
    if throughput < 2:
        recommendations.append("Low throughput detected - consider optimizing task processing")
    
    queues = metrics.get('queues', {})
    audio_queue = queues.get('audio_processing', {})
    if audio_queue.get('avg_processing_time', 0) > 600:  # 10 minutes
        recommendations.append("Audio processing taking too long - consider pipeline optimization")
    
    workers = metrics.get('workers', {})
    if len(workers) < 3:
        recommendations.append("Consider adding more workers for better parallelization")
    
    return recommendations

async def process_alerts(alert_data: Dict[str, Any]):
    """Process incoming alerts"""
    alerts = alert_data.get("alerts", [])
    
    for alert in alerts:
        alert_name = alert.get("labels", {}).get("alertname", "Unknown")
        severity = alert.get("labels", {}).get("severity", "unknown")
        
        # Send alert via WebSocket to dashboard
        if websocket_manager:
            alert_message = {
                "type": "system_alert",
                "data": {
                    "alert_name": alert_name,
                    "severity": severity,
                    "summary": alert.get("annotations", {}).get("summary", ""),
                    "description": alert.get("annotations", {}).get("description", "")
                }
            }
            
            await websocket_manager.broadcast_to_dashboard(alert_message)
        
        SecureLogger.safe_log_warning(logger, f"Alert processed: {alert_name}", {
            "severity": severity,
            "status": alert.get("status", "unknown")
        })