import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import statistics
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
import pandas as pd

from app.infrastructure.monitoring.business_metrics import business_metrics
from app.infrastructure.metrics_collector import metrics_collector
from app.utils.secure_logging import SecureLogger

logger = logging.getLogger(__name__)

class ResourceType(Enum):
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    WORKERS = "workers"
    QUEUES = "queues"

class TrendDirection(Enum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"

@dataclass
class ResourceMetric:
    resource_type: ResourceType
    current_usage: float
    current_capacity: float
    utilization_percent: float
    trend: TrendDirection
    growth_rate_per_day: float
    projected_exhaustion_days: Optional[int]
    recommended_action: str

@dataclass
class CapacityForecast:
    resource_type: ResourceType
    forecast_horizon_days: int
    current_value: float
    predicted_value: float
    confidence_interval: Tuple[float, float]
    trend_analysis: Dict[str, Any]
    recommendations: List[str]

@dataclass
class ScalingRecommendation:
    component: str
    current_capacity: int
    recommended_capacity: int
    reason: str
    urgency: str  # "low", "medium", "high", "critical"
    cost_impact: str
    implementation_complexity: str

class CapacityPlanner:
    """Advanced capacity planning and resource forecasting"""
    
    def __init__(self):
        self.metrics_history: Dict[str, List[Tuple[datetime, float]]] = {}
        self.forecasting_models: Dict[str, Any] = {}
        self.capacity_thresholds = self._initialize_thresholds()
        self.cost_models = self._initialize_cost_models()
        
    def _initialize_thresholds(self) -> Dict[ResourceType, Dict[str, float]]:
        """Initialize capacity thresholds for different resources"""
        return {
            ResourceType.CPU: {
                "warning": 70.0,
                "critical": 85.0,
                "maximum": 95.0
            },
            ResourceType.MEMORY: {
                "warning": 75.0,
                "critical": 90.0,
                "maximum": 95.0
            },
            ResourceType.STORAGE: {
                "warning": 80.0,
                "critical": 90.0,
                "maximum": 95.0
            },
            ResourceType.WORKERS: {
                "warning": 80.0,
                "critical": 90.0,
                "maximum": 100.0
            },
            ResourceType.QUEUES: {
                "warning": 100.0,  # 100 tasks in queue
                "critical": 500.0,
                "maximum": 1000.0
            }
        }
    
    def _initialize_cost_models(self) -> Dict[str, Dict[str, float]]:
        """Initialize cost models for different resources"""
        return {
            "aws": {
                "cpu_core_hour": 0.0464,  # t3.medium pricing
                "memory_gb_hour": 0.0058,
                "storage_gb_month": 0.10,
                "network_gb": 0.09
            },
            "worker_scaling": {
                "container_hour": 0.02,
                "lb_hour": 0.025,
                "monitoring_hour": 0.005
            },
            "api_costs": {
                "openai_1k_tokens": 0.002,
                "gemini_1k_tokens": 0.001,
                "whisper_minute": 0.006
            }
        }
    
    async def collect_capacity_metrics(self):
        """Collect current capacity metrics"""
        try:
            timestamp = datetime.utcnow()
            
            # Get system metrics
            system_metrics = metrics_collector.get_current_metrics()
            
            # Collect various capacity metrics
            await self._collect_cpu_metrics(timestamp, system_metrics)
            await self._collect_memory_metrics(timestamp, system_metrics)
            await self._collect_queue_metrics(timestamp, system_metrics)
            await self._collect_worker_metrics(timestamp, system_metrics)
            await self._collect_business_metrics(timestamp)
            
            # Clean old metrics (keep last 30 days)
            await self._cleanup_old_metrics()
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to collect capacity metrics", e)
    
    async def _collect_cpu_metrics(self, timestamp: datetime, system_metrics: Dict[str, Any]):
        """Collect CPU usage metrics"""
        cpu_usage = system_metrics.get('system', {}).get('cpu_usage', 0.0)
        self._store_metric('cpu_usage', timestamp, cpu_usage)
    
    async def _collect_memory_metrics(self, timestamp: datetime, system_metrics: Dict[str, Any]):
        """Collect memory usage metrics"""
        memory_usage = system_metrics.get('system', {}).get('memory_usage', 0.0)
        self._store_metric('memory_usage', timestamp, memory_usage)
    
    async def _collect_queue_metrics(self, timestamp: datetime, system_metrics: Dict[str, Any]):
        """Collect queue length metrics"""
        total_queued = system_metrics.get('system', {}).get('total_queued_tasks', 0)
        self._store_metric('total_queued_tasks', timestamp, total_queued)
        
        # Individual queue metrics
        queues = system_metrics.get('queues', {})
        for queue_name, queue_data in queues.items():
            metric_name = f'queue_{queue_name}_length'
            self._store_metric(metric_name, timestamp, queue_data.get('length', 0))
    
    async def _collect_worker_metrics(self, timestamp: datetime, system_metrics: Dict[str, Any]):
        """Collect worker metrics"""
        total_workers = system_metrics.get('system', {}).get('total_workers', 0)
        active_tasks = system_metrics.get('system', {}).get('total_active_tasks', 0)
        
        self._store_metric('total_workers', timestamp, total_workers)
        self._store_metric('total_active_tasks', timestamp, active_tasks)
        
        # Worker utilization
        utilization = (active_tasks / max(total_workers, 1)) * 100
        self._store_metric('worker_utilization', timestamp, utilization)
    
    async def _collect_business_metrics(self, timestamp: datetime):
        """Collect business-related capacity metrics"""
        # Daily interviews
        daily_interviews = business_metrics.current_metrics.get('daily_interviews', 0)
        self._store_metric('daily_interviews', timestamp, daily_interviews)
        
        # Processing time
        processing_time = business_metrics.current_metrics.get('interview_processing_time', 0)
        self._store_metric('processing_time', timestamp, processing_time)
        
        # Cost per interview
        cost_per_interview = business_metrics.current_metrics.get('cost_per_interview', 0)
        self._store_metric('cost_per_interview', timestamp, cost_per_interview)
    
    def _store_metric(self, metric_name: str, timestamp: datetime, value: float):
        """Store metric value with timestamp"""
        if metric_name not in self.metrics_history:
            self.metrics_history[metric_name] = []
        
        self.metrics_history[metric_name].append((timestamp, value))
        
        # Keep only last 1000 data points per metric
        if len(self.metrics_history[metric_name]) > 1000:
            self.metrics_history[metric_name] = self.metrics_history[metric_name][-1000:]
    
    async def _cleanup_old_metrics(self):
        """Clean up metrics older than 30 days"""
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        for metric_name in self.metrics_history:
            self.metrics_history[metric_name] = [
                (timestamp, value) for timestamp, value in self.metrics_history[metric_name]
                if timestamp > cutoff_date
            ]
    
    async def analyze_capacity_trends(self) -> Dict[str, ResourceMetric]:
        """Analyze capacity trends for all resources"""
        resource_analysis = {}
        
        # Analyze different resource types
        resource_metrics = {
            'cpu_usage': ResourceType.CPU,
            'memory_usage': ResourceType.MEMORY,
            'total_queued_tasks': ResourceType.QUEUES,
            'worker_utilization': ResourceType.WORKERS
        }
        
        for metric_name, resource_type in resource_metrics.items():
            if metric_name in self.metrics_history:
                analysis = await self._analyze_single_metric(metric_name, resource_type)
                resource_analysis[metric_name] = analysis
        
        return resource_analysis
    
    async def _analyze_single_metric(self, metric_name: str, resource_type: ResourceType) -> ResourceMetric:
        """Analyze a single metric for capacity planning"""
        
        data = self.metrics_history[metric_name]
        if len(data) < 10:  # Need at least 10 data points
            return ResourceMetric(
                resource_type=resource_type,
                current_usage=data[-1][1] if data else 0,
                current_capacity=100.0,  # Default capacity
                utilization_percent=0.0,
                trend=TrendDirection.STABLE,
                growth_rate_per_day=0.0,
                projected_exhaustion_days=None,
                recommended_action="Insufficient data for analysis"
            )
        
        # Extract values and timestamps
        timestamps = [d[0] for d in data]
        values = [d[1] for d in data]
        
        current_usage = values[-1]
        
        # Calculate trend
        trend, growth_rate = self._calculate_trend(timestamps, values)
        
        # Determine capacity based on resource type
        if resource_type == ResourceType.QUEUES:
            current_capacity = 1000.0  # Max queue length
        else:
            current_capacity = 100.0  # Percentage-based
        
        utilization = (current_usage / current_capacity) * 100
        
        # Project exhaustion
        projected_exhaustion = self._project_exhaustion(
            current_usage, current_capacity, growth_rate
        )
        
        # Generate recommendations
        recommended_action = self._generate_recommendation(
            resource_type, utilization, trend, projected_exhaustion
        )
        
        return ResourceMetric(
            resource_type=resource_type,
            current_usage=current_usage,
            current_capacity=current_capacity,
            utilization_percent=utilization,
            trend=trend,
            growth_rate_per_day=growth_rate,
            projected_exhaustion_days=projected_exhaustion,
            recommended_action=recommended_action
        )
    
    def _calculate_trend(self, timestamps: List[datetime], values: List[float]) -> Tuple[TrendDirection, float]:
        """Calculate trend direction and growth rate"""
        
        if len(values) < 5:
            return TrendDirection.STABLE, 0.0
        
        # Convert timestamps to days since first measurement
        start_time = timestamps[0]
        days = [(ts - start_time).total_seconds() / 86400 for ts in timestamps]
        
        # Calculate linear regression
        try:
            X = np.array(days).reshape(-1, 1)
            y = np.array(values)
            
            model = LinearRegression()
            model.fit(X, y)
            
            slope = model.coef_[0]
            r_squared = model.score(X, y)
            
            # Determine trend based on slope and R-squared
            if r_squared < 0.3:  # Low correlation, likely volatile
                return TrendDirection.VOLATILE, slope
            elif abs(slope) < 0.1:  # Very small slope
                return TrendDirection.STABLE, slope
            elif slope > 0:
                return TrendDirection.INCREASING, slope
            else:
                return TrendDirection.DECREASING, slope
                
        except Exception:
            return TrendDirection.STABLE, 0.0
    
    def _project_exhaustion(self, current_usage: float, capacity: float, 
                          growth_rate: float) -> Optional[int]:
        """Project when resource will be exhausted"""
        
        if growth_rate <= 0:
            return None  # Not growing or decreasing
        
        remaining_capacity = capacity - current_usage
        if remaining_capacity <= 0:
            return 0  # Already exhausted
        
        days_to_exhaustion = remaining_capacity / growth_rate
        
        # Cap at reasonable maximum
        if days_to_exhaustion > 365:
            return None
        
        return int(days_to_exhaustion)
    
    def _generate_recommendation(self, resource_type: ResourceType, 
                               utilization: float, trend: TrendDirection,
                               projected_exhaustion: Optional[int]) -> str:
        """Generate capacity recommendation"""
        
        thresholds = self.capacity_thresholds[resource_type]
        
        if utilization >= thresholds["critical"]:
            return f"CRITICAL: {resource_type.value} utilization at {utilization:.1f}%. Immediate scaling required."
        elif utilization >= thresholds["warning"]:
            if projected_exhaustion and projected_exhaustion < 7:
                return f"WARNING: {resource_type.value} will be exhausted in {projected_exhaustion} days. Plan scaling."
            else:
                return f"WARNING: {resource_type.value} utilization at {utilization:.1f}%. Monitor closely."
        elif trend == TrendDirection.INCREASING and projected_exhaustion and projected_exhaustion < 30:
            return f"INFO: {resource_type.value} growing. Will need scaling in {projected_exhaustion} days."
        else:
            return f"OK: {resource_type.value} utilization healthy at {utilization:.1f}%."
    
    async def generate_scaling_recommendations(self) -> List[ScalingRecommendation]:
        """Generate specific scaling recommendations"""
        
        recommendations = []
        
        # Analyze current metrics
        capacity_analysis = await self.analyze_capacity_trends()
        
        # Worker scaling recommendations
        if 'worker_utilization' in capacity_analysis:
            worker_metric = capacity_analysis['worker_utilization']
            if worker_metric.utilization_percent > 80:
                recommendations.append(ScalingRecommendation(
                    component="Celery Workers",
                    current_capacity=int(worker_metric.current_usage / worker_metric.utilization_percent * 100),
                    recommended_capacity=int(worker_metric.current_usage / 70 * 100),  # Target 70% utilization
                    reason=f"Worker utilization at {worker_metric.utilization_percent:.1f}%",
                    urgency="high" if worker_metric.utilization_percent > 90 else "medium",
                    cost_impact="Medium",
                    implementation_complexity="Low"
                ))
        
        # Queue scaling recommendations
        if 'total_queued_tasks' in capacity_analysis:
            queue_metric = capacity_analysis['total_queued_tasks']
            if queue_metric.current_usage > 100:
                recommendations.append(ScalingRecommendation(
                    component="Queue Processing",
                    current_capacity=int(queue_metric.current_capacity),
                    recommended_capacity=int(queue_metric.current_capacity * 1.5),
                    reason=f"Queue length at {queue_metric.current_usage} tasks",
                    urgency="high" if queue_metric.current_usage > 500 else "medium",
                    cost_impact="Medium",
                    implementation_complexity="Low"
                ))
        
        # Infrastructure scaling recommendations
        if 'cpu_usage' in capacity_analysis:
            cpu_metric = capacity_analysis['cpu_usage']
            if cpu_metric.utilization_percent > 80:
                recommendations.append(ScalingRecommendation(
                    component="CPU Resources",
                    current_capacity=100,
                    recommended_capacity=150,
                    reason=f"CPU utilization at {cpu_metric.utilization_percent:.1f}%",
                    urgency="high" if cpu_metric.utilization_percent > 90 else "medium",
                    cost_impact="High",
                    implementation_complexity="Medium"
                ))
        
        if 'memory_usage' in capacity_analysis:
            memory_metric = capacity_analysis['memory_usage']
            if memory_metric.utilization_percent > 80:
                recommendations.append(ScalingRecommendation(
                    component="Memory Resources",
                    current_capacity=100,
                    recommended_capacity=150,
                    reason=f"Memory utilization at {memory_metric.utilization_percent:.1f}%",
                    urgency="high" if memory_metric.utilization_percent > 90 else "medium",
                    cost_impact="High",
                    implementation_complexity="Medium"
                ))
        
        return recommendations
    
    async def forecast_capacity_needs(self, horizon_days: int = 30) -> Dict[str, CapacityForecast]:
        """Forecast capacity needs for specified horizon"""
        
        forecasts = {}
        
        key_metrics = ['cpu_usage', 'memory_usage', 'total_queued_tasks', 'daily_interviews']
        
        for metric_name in key_metrics:
            if metric_name in self.metrics_history and len(self.metrics_history[metric_name]) >= 10:
                forecast = await self._forecast_single_metric(metric_name, horizon_days)
                forecasts[metric_name] = forecast
        
        return forecasts
    
    async def _forecast_single_metric(self, metric_name: str, horizon_days: int) -> CapacityForecast:
        """Forecast a single metric"""
        
        data = self.metrics_history[metric_name]
        
        # Extract data
        timestamps = [d[0] for d in data]
        values = [d[1] for d in data]
        
        current_value = values[-1]
        
        # Prepare data for forecasting
        start_time = timestamps[0]
        days = [(ts - start_time).total_seconds() / 86400 for ts in timestamps]
        
        try:
            # Use polynomial regression for better forecasting
            X = np.array(days).reshape(-1, 1)
            y = np.array(values)
            
            # Try different polynomial degrees
            best_score = -float('inf')
            best_model = None
            best_poly = None
            
            for degree in [1, 2, 3]:
                poly = PolynomialFeatures(degree=degree)
                X_poly = poly.fit_transform(X)
                
                model = LinearRegression()
                model.fit(X_poly, y)
                
                score = model.score(X_poly, y)
                if score > best_score:
                    best_score = score
                    best_model = model
                    best_poly = poly
            
            # Forecast
            future_day = days[-1] + horizon_days
            future_X = best_poly.transform([[future_day]])
            predicted_value = best_model.predict(future_X)[0]
            
            # Calculate confidence interval (simplified)
            residuals = y - best_model.predict(best_poly.transform(X))
            std_error = np.std(residuals)
            confidence_interval = (
                predicted_value - 1.96 * std_error,
                predicted_value + 1.96 * std_error
            )
            
            # Generate recommendations
            recommendations = self._generate_forecast_recommendations(
                metric_name, current_value, predicted_value, horizon_days
            )
            
            # Trend analysis
            trend_analysis = {
                "model_score": best_score,
                "polynomial_degree": best_poly.degree if hasattr(best_poly, 'degree') else 1,
                "growth_rate": (predicted_value - current_value) / horizon_days,
                "volatility": np.std(values[-10:]) if len(values) >= 10 else 0
            }
            
            return CapacityForecast(
                resource_type=self._get_resource_type_for_metric(metric_name),
                forecast_horizon_days=horizon_days,
                current_value=current_value,
                predicted_value=predicted_value,
                confidence_interval=confidence_interval,
                trend_analysis=trend_analysis,
                recommendations=recommendations
            )
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, f"Forecasting failed for {metric_name}", e)
            
            # Return simple forecast
            return CapacityForecast(
                resource_type=self._get_resource_type_for_metric(metric_name),
                forecast_horizon_days=horizon_days,
                current_value=current_value,
                predicted_value=current_value,
                confidence_interval=(current_value, current_value),
                trend_analysis={"error": str(e)},
                recommendations=["Insufficient data for reliable forecasting"]
            )
    
    def _get_resource_type_for_metric(self, metric_name: str) -> ResourceType:
        """Map metric name to resource type"""
        mapping = {
            'cpu_usage': ResourceType.CPU,
            'memory_usage': ResourceType.MEMORY,
            'total_queued_tasks': ResourceType.QUEUES,
            'worker_utilization': ResourceType.WORKERS,
            'daily_interviews': ResourceType.NETWORK  # Using network as proxy for throughput
        }
        return mapping.get(metric_name, ResourceType.CPU)
    
    def _generate_forecast_recommendations(self, metric_name: str, current_value: float,
                                         predicted_value: float, horizon_days: int) -> List[str]:
        """Generate recommendations based on forecast"""
        
        recommendations = []
        growth_rate = (predicted_value - current_value) / horizon_days
        
        if growth_rate > 0:
            growth_percent = (predicted_value / current_value - 1) * 100
            
            if growth_percent > 50:
                recommendations.append(f"High growth expected ({growth_percent:.1f}% in {horizon_days} days). Plan significant scaling.")
            elif growth_percent > 20:
                recommendations.append(f"Moderate growth expected ({growth_percent:.1f}% in {horizon_days} days). Plan gradual scaling.")
            elif growth_percent > 5:
                recommendations.append(f"Steady growth expected ({growth_percent:.1f}% in {horizon_days} days). Monitor closely.")
        
        # Specific recommendations by metric type
        if metric_name == 'daily_interviews' and predicted_value > current_value * 1.5:
            recommendations.append("Business growth expected. Consider scaling entire infrastructure.")
        
        if metric_name in ['cpu_usage', 'memory_usage'] and predicted_value > 80:
            recommendations.append("Resource exhaustion predicted. Plan infrastructure upgrade.")
        
        if metric_name == 'total_queued_tasks' and predicted_value > 500:
            recommendations.append("Queue congestion predicted. Plan worker scaling.")
        
        return recommendations or ["Continue monitoring current trends."]
    
    async def calculate_cost_projections(self, scaling_recommendations: List[ScalingRecommendation]) -> Dict[str, Any]:
        """Calculate cost projections for scaling recommendations"""
        
        cost_analysis = {
            "monthly_cost_increase": 0.0,
            "annual_cost_increase": 0.0,
            "cost_per_component": {},
            "roi_analysis": {}
        }
        
        aws_costs = self.cost_models["aws"]
        worker_costs = self.cost_models["worker_scaling"]
        
        for recommendation in scaling_recommendations:
            component_cost = 0.0
            
            if "Worker" in recommendation.component:
                # Calculate worker scaling costs
                additional_workers = recommendation.recommended_capacity - recommendation.current_capacity
                monthly_hours = 24 * 30  # Assuming 24/7 operation
                
                component_cost = (
                    additional_workers * worker_costs["container_hour"] * monthly_hours +
                    worker_costs["monitoring_hour"] * monthly_hours  # Additional monitoring
                )
            
            elif "CPU" in recommendation.component:
                # Calculate CPU scaling costs
                additional_cores = (recommendation.recommended_capacity - recommendation.current_capacity) / 100 * 4  # Assume 4 cores baseline
                monthly_hours = 24 * 30
                
                component_cost = additional_cores * aws_costs["cpu_core_hour"] * monthly_hours
            
            elif "Memory" in recommendation.component:
                # Calculate memory scaling costs
                additional_gb = (recommendation.recommended_capacity - recommendation.current_capacity) / 100 * 16  # Assume 16GB baseline
                monthly_hours = 24 * 30
                
                component_cost = additional_gb * aws_costs["memory_gb_hour"] * monthly_hours
            
            cost_analysis["cost_per_component"][recommendation.component] = component_cost
            cost_analysis["monthly_cost_increase"] += component_cost
        
        cost_analysis["annual_cost_increase"] = cost_analysis["monthly_cost_increase"] * 12
        
        # Simple ROI analysis
        current_daily_interviews = business_metrics.current_metrics.get('daily_interviews', 50)
        current_monthly_revenue = current_daily_interviews * 30 * 10  # Assume $10 value per interview
        
        cost_analysis["roi_analysis"] = {
            "monthly_cost_increase": cost_analysis["monthly_cost_increase"],
            "estimated_monthly_revenue": current_monthly_revenue,
            "cost_percentage_of_revenue": (cost_analysis["monthly_cost_increase"] / max(current_monthly_revenue, 1)) * 100,
            "break_even_additional_interviews": cost_analysis["monthly_cost_increase"] / 10  # Daily interviews needed to break even
        }
        
        return cost_analysis
    
    async def generate_capacity_report(self) -> Dict[str, Any]:
        """Generate comprehensive capacity planning report"""
        
        # Collect all analyses
        capacity_trends = await self.analyze_capacity_trends()
        scaling_recommendations = await self.generate_scaling_recommendations()
        forecasts = await self.forecast_capacity_needs(30)
        cost_projections = await self.calculate_cost_projections(scaling_recommendations)
        
        # Overall health assessment
        critical_issues = [
            metric for metric, analysis in capacity_trends.items()
            if analysis.utilization_percent > 90
        ]
        
        warning_issues = [
            metric for metric, analysis in capacity_trends.items()
            if 70 <= analysis.utilization_percent <= 90
        ]
        
        overall_health = "healthy"
        if critical_issues:
            overall_health = "critical"
        elif warning_issues:
            overall_health = "warning"
        
        return {
            "report_generated_at": datetime.utcnow().isoformat(),
            "overall_health": overall_health,
            "summary": {
                "critical_issues": len(critical_issues),
                "warning_issues": len(warning_issues),
                "scaling_recommendations": len(scaling_recommendations),
                "monthly_cost_impact": cost_projections["monthly_cost_increase"]
            },
            "capacity_trends": {
                name: {
                    "resource_type": analysis.resource_type.value,
                    "utilization_percent": analysis.utilization_percent,
                    "trend": analysis.trend.value,
                    "growth_rate_per_day": analysis.growth_rate_per_day,
                    "projected_exhaustion_days": analysis.projected_exhaustion_days,
                    "recommendation": analysis.recommended_action
                }
                for name, analysis in capacity_trends.items()
            },
            "scaling_recommendations": [
                {
                    "component": rec.component,
                    "current_capacity": rec.current_capacity,
                    "recommended_capacity": rec.recommended_capacity,
                    "reason": rec.reason,
                    "urgency": rec.urgency,
                    "cost_impact": rec.cost_impact,
                    "implementation_complexity": rec.implementation_complexity
                }
                for rec in scaling_recommendations
            ],
            "forecasts": {
                name: {
                    "current_value": forecast.current_value,
                    "predicted_value": forecast.predicted_value,
                    "confidence_interval": forecast.confidence_interval,
                    "recommendations": forecast.recommendations
                }
                for name, forecast in forecasts.items()
            },
            "cost_analysis": cost_projections,
            "next_review_date": (datetime.utcnow() + timedelta(days=7)).isoformat()
        }

# Global capacity planner
capacity_planner = CapacityPlanner()