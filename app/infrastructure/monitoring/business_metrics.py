import time
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
from app.utils.secure_logging import SecureLogger
from app.infrastructure.prometheus_metrics import prometheus_metrics

logger = logging.getLogger(__name__)

class SLAStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class SLATarget:
    name: str
    target_value: float
    threshold_warning: float
    threshold_critical: float
    unit: str = "percentage"
    description: str = ""

@dataclass
class BusinessMetric:
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

class BusinessMetricsCollector:
    """Collects and monitors business KPIs and SLAs"""
    
    def __init__(self):
        self.sla_targets = self._initialize_sla_targets()
        self.metrics_history: Dict[str, List[BusinessMetric]] = {}
        self.current_metrics: Dict[str, float] = {}
        
    def _initialize_sla_targets(self) -> Dict[str, SLATarget]:
        """Initialize SLA targets for the interview bot"""
        return {
            # Interview Processing SLAs
            "interview_success_rate": SLATarget(
                name="Interview Success Rate",
                target_value=99.5,  # 99.5% success rate
                threshold_warning=95.0,
                threshold_critical=90.0,
                unit="percentage",
                description="Percentage of interviews processed successfully"
            ),
            
            "interview_processing_time": SLATarget(
                name="Interview Processing Time",
                target_value=15.0,  # 15 minutes target
                threshold_warning=20.0,
                threshold_critical=30.0,
                unit="minutes",
                description="Average time to process complete interview"
            ),
            
            "transcription_accuracy": SLATarget(
                name="Transcription Accuracy",
                target_value=95.0,  # 95% accuracy target
                threshold_warning=90.0,
                threshold_critical=85.0,
                unit="percentage",
                description="Estimated transcription accuracy based on confidence scores"
            ),
            
            "api_availability": SLATarget(
                name="API Availability",
                target_value=99.9,  # 99.9% uptime
                threshold_warning=99.0,
                threshold_critical=95.0,
                unit="percentage",
                description="Overall API availability"
            ),
            
            "user_satisfaction": SLATarget(
                name="User Satisfaction",
                target_value=4.5,  # 4.5/5 rating
                threshold_warning=4.0,
                threshold_critical=3.5,
                unit="rating",
                description="Average user satisfaction rating"
            ),
            
            # Operational SLAs
            "response_time_p95": SLATarget(
                name="95th Percentile Response Time",
                target_value=2.0,  # 2 seconds
                threshold_warning=5.0,
                threshold_critical=10.0,
                unit="seconds",
                description="95th percentile API response time"
            ),
            
            "error_rate": SLATarget(
                name="Error Rate",
                target_value=0.1,  # 0.1% error rate
                threshold_warning=1.0,
                threshold_critical=5.0,
                unit="percentage",
                description="Percentage of requests resulting in errors"
            ),
            
            # Business KPIs
            "daily_interviews": SLATarget(
                name="Daily Interview Volume",
                target_value=100,  # 100 interviews per day
                threshold_warning=50,
                threshold_critical=20,
                unit="count",
                description="Number of interviews processed daily"
            ),
            
            "cost_per_interview": SLATarget(
                name="Cost per Interview",
                target_value=2.0,  # $2 per interview
                threshold_warning=3.0,
                threshold_critical=5.0,
                unit="USD",
                description="Average cost to process one interview"
            )
        }
    
    async def record_metric(self, metric_name: str, value: float, metadata: Dict[str, Any] = None):
        """Record a business metric"""
        metric = BusinessMetric(
            name=metric_name,
            value=value,
            metadata=metadata or {}
        )
        
        # Store in history
        if metric_name not in self.metrics_history:
            self.metrics_history[metric_name] = []
        
        self.metrics_history[metric_name].append(metric)
        
        # Keep only last 1000 metrics per type
        if len(self.metrics_history[metric_name]) > 1000:
            self.metrics_history[metric_name] = self.metrics_history[metric_name][-1000:]
        
        # Update current value
        self.current_metrics[metric_name] = value
        
        # Update Prometheus metrics
        prometheus_metrics.business_metrics.labels(metric_name=metric_name).set(value)
        
        SecureLogger.safe_log_info(logger, "Business metric recorded", {
            'metric_name': metric_name,
            'value': value,
            'metadata': metadata
        })
    
    async def record_interview_completion(self, interview_id: str, success: bool, 
                                        processing_time_minutes: float, 
                                        transcription_confidence: float = None):
        """Record interview completion metrics"""
        
        # Success rate calculation
        await self._update_success_rate(success)
        
        # Processing time
        await self.record_metric("interview_processing_time", processing_time_minutes, {
            'interview_id': interview_id,
            'success': success
        })
        
        # Transcription accuracy (if available)
        if transcription_confidence is not None:
            await self.record_metric("transcription_accuracy", transcription_confidence * 100, {
                'interview_id': interview_id
            })
        
        SecureLogger.safe_log_info(logger, "Interview completion metrics recorded", {
            'interview_id': interview_id,
            'success': success,
            'processing_time_minutes': processing_time_minutes
        })
    
    async def record_api_request(self, endpoint: str, status_code: int, response_time_ms: float):
        """Record API request metrics"""
        
        # Response time (convert to seconds)
        await self.record_metric("response_time_p95", response_time_ms / 1000, {
            'endpoint': endpoint,
            'status_code': status_code
        })
        
        # Error rate calculation
        is_error = status_code >= 400
        await self._update_error_rate(is_error)
        
        # API availability calculation
        is_available = status_code != 503  # Service unavailable
        await self._update_api_availability(is_available)
    
    async def record_user_feedback(self, interview_id: str, rating: float, feedback: str = None):
        """Record user satisfaction metrics"""
        await self.record_metric("user_satisfaction", rating, {
            'interview_id': interview_id,
            'feedback_provided': feedback is not None
        })
    
    async def record_cost_metrics(self, interview_id: str, openai_cost: float, 
                                 gemini_cost: float, infrastructure_cost: float):
        """Record cost metrics"""
        total_cost = openai_cost + gemini_cost + infrastructure_cost
        
        await self.record_metric("cost_per_interview", total_cost, {
            'interview_id': interview_id,
            'openai_cost': openai_cost,
            'gemini_cost': gemini_cost,
            'infrastructure_cost': infrastructure_cost
        })
    
    async def _update_success_rate(self, success: bool):
        """Update rolling success rate"""
        # Get last 100 interviews
        recent_metrics = self._get_recent_metrics("interview_success_rate", hours=24)
        
        # Add current result
        recent_results = [m.value for m in recent_metrics] + [100.0 if success else 0.0]
        
        # Calculate success rate
        success_rate = sum(recent_results) / len(recent_results)
        
        await self.record_metric("interview_success_rate", success_rate)
    
    async def _update_error_rate(self, is_error: bool):
        """Update rolling error rate"""
        # Get last 1000 requests
        recent_metrics = self._get_recent_metrics("error_rate", hours=1)
        
        # Add current result
        recent_results = [m.value for m in recent_metrics] + [100.0 if is_error else 0.0]
        
        # Calculate error rate
        error_rate = sum(recent_results) / len(recent_results)
        
        await self.record_metric("error_rate", error_rate)
    
    async def _update_api_availability(self, is_available: bool):
        """Update rolling API availability"""
        # Get last 1000 requests
        recent_metrics = self._get_recent_metrics("api_availability", hours=1)
        
        # Add current result
        recent_results = [m.value for m in recent_metrics] + [100.0 if is_available else 0.0]
        
        # Calculate availability
        availability = sum(recent_results) / len(recent_results)
        
        await self.record_metric("api_availability", availability)
    
    def _get_recent_metrics(self, metric_name: str, hours: int = 1) -> List[BusinessMetric]:
        """Get recent metrics within time window"""
        if metric_name not in self.metrics_history:
            return []
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        return [
            m for m in self.metrics_history[metric_name]
            if m.timestamp > cutoff_time
        ]
    
    def get_sla_status(self) -> Dict[str, Dict[str, Any]]:
        """Get current SLA status for all targets"""
        sla_status = {}
        
        for target_name, target in self.sla_targets.items():
            current_value = self.current_metrics.get(target_name, 0.0)
            
            # Determine status
            if target.unit == "percentage" or target.unit == "rating":
                # Higher is better
                if current_value >= target.target_value:
                    status = SLAStatus.HEALTHY
                elif current_value >= target.threshold_warning:
                    status = SLAStatus.WARNING
                else:
                    status = SLAStatus.CRITICAL
            else:
                # Lower is better (time, cost, error rate)
                if current_value <= target.target_value:
                    status = SLAStatus.HEALTHY
                elif current_value <= target.threshold_warning:
                    status = SLAStatus.WARNING
                else:
                    status = SLAStatus.CRITICAL
            
            sla_status[target_name] = {
                "status": status.value,
                "current_value": current_value,
                "target_value": target.target_value,
                "threshold_warning": target.threshold_warning,
                "threshold_critical": target.threshold_critical,
                "unit": target.unit,
                "description": target.description,
                "last_updated": self._get_last_updated(target_name)
            }
        
        return sla_status
    
    def _get_last_updated(self, metric_name: str) -> Optional[str]:
        """Get last update time for metric"""
        if metric_name not in self.metrics_history or not self.metrics_history[metric_name]:
            return None
        
        return self.metrics_history[metric_name][-1].timestamp.isoformat()
    
    async def generate_sla_report(self, hours: int = 24) -> Dict[str, Any]:
        """Generate SLA compliance report"""
        sla_status = self.get_sla_status()
        
        # Calculate overall health score
        status_scores = {
            SLAStatus.HEALTHY.value: 100,
            SLAStatus.WARNING.value: 60,
            SLAStatus.CRITICAL.value: 20
        }
        
        total_score = 0
        target_count = len(sla_status)
        
        violations = []
        warnings = []
        
        for target_name, status_info in sla_status.items():
            status = status_info["status"]
            total_score += status_scores.get(status, 0)
            
            if status == SLAStatus.CRITICAL.value:
                violations.append({
                    "target": target_name,
                    "current_value": status_info["current_value"],
                    "target_value": status_info["target_value"],
                    "severity": "critical"
                })
            elif status == SLAStatus.WARNING.value:
                warnings.append({
                    "target": target_name,
                    "current_value": status_info["current_value"],
                    "target_value": status_info["target_value"],
                    "severity": "warning"
                })
        
        overall_health = total_score / target_count if target_count > 0 else 0
        
        return {
            "report_generated_at": datetime.utcnow().isoformat(),
            "time_window_hours": hours,
            "overall_health_score": overall_health,
            "total_targets": target_count,
            "healthy_targets": len([s for s in sla_status.values() if s["status"] == SLAStatus.HEALTHY.value]),
            "warning_targets": len(warnings),
            "critical_targets": len(violations),
            "sla_violations": violations,
            "sla_warnings": warnings,
            "detailed_status": sla_status
        }

# Global business metrics collector
business_metrics = BusinessMetricsCollector()