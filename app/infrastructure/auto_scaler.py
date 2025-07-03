import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import subprocess
import json
from app.infrastructure.metrics_collector import metrics_collector, QueueMetrics
from app.utils.secure_logging import SecureLogger
from app.core.config import settings
from app.infrastructure.prometheus_metrics import prometheus_metrics

logger = logging.getLogger(__name__)

class ScalingAction(Enum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NO_ACTION = "no_action"

@dataclass
class ScalingRule:
    """Rule for auto-scaling decisions"""
    queue_name: str
    min_workers: int = 1
    max_workers: int = 10
    scale_up_threshold: float = 5.0  # Queue length threshold to scale up
    scale_down_threshold: float = 0.5  # Queue length threshold to scale down
    cpu_threshold: float = 80.0  # CPU percentage threshold
    memory_threshold: float = 85.0  # Memory percentage threshold
    cooldown_minutes: int = 5  # Minimum time between scaling actions
    
@dataclass
class ScalingDecision:
    """Auto-scaling decision result"""
    queue_name: str
    current_workers: int
    target_workers: int
    action: ScalingAction
    reason: str
    confidence: float = 0.0  # 0-1, how confident we are in this decision
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

class AutoScaler:
    """Intelligent auto-scaling for Celery workers"""
    
    def __init__(self):
        self.scaling_rules = self._initialize_scaling_rules()
        self.scaling_history: List[ScalingDecision] = []
        self.last_scaling_action: Dict[str, datetime] = {}
        self.enabled = True
        self.running = False
        self.check_interval = 60  # seconds
    
    def _initialize_scaling_rules(self) -> Dict[str, ScalingRule]:
        """Initialize scaling rules for different queues"""
        return {
            'audio_processing': ScalingRule(
                queue_name='audio_processing',
                min_workers=2,
                max_workers=8,
                scale_up_threshold=3.0,  # Scale up if >3 tasks queued
                scale_down_threshold=0.5,  # Scale down if <0.5 avg tasks
                cpu_threshold=75.0,
                memory_threshold=80.0,
                cooldown_minutes=3
            ),
            'document_generation': ScalingRule(
                queue_name='document_generation',
                min_workers=1,
                max_workers=5,
                scale_up_threshold=5.0,  # Documents can wait a bit longer
                scale_down_threshold=1.0,
                cpu_threshold=70.0,
                memory_threshold=75.0,
                cooldown_minutes=5
            ),
            'maintenance': ScalingRule(
                queue_name='maintenance',
                min_workers=1,
                max_workers=2,
                scale_up_threshold=10.0,  # Maintenance is not urgent
                scale_down_threshold=2.0,
                cpu_threshold=60.0,
                memory_threshold=70.0,
                cooldown_minutes=10
            ),
            'high_priority': ScalingRule(
                queue_name='high_priority',
                min_workers=1,
                max_workers=5,
                scale_up_threshold=1.0,  # Scale immediately for high priority
                scale_down_threshold=0.1,
                cpu_threshold=85.0,
                memory_threshold=90.0,
                cooldown_minutes=2
            )
        }
    
    async def start_auto_scaling(self):
        """Start auto-scaling service"""
        self.running = True
        
        SecureLogger.safe_log_info(logger, "Auto-scaler started", {
            'enabled': self.enabled,
            'check_interval': self.check_interval,
            'rules_count': len(self.scaling_rules)
        })
        
        while self.running:
            try:
                if self.enabled:
                    await self.evaluate_scaling_decisions()
                
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                SecureLogger.safe_log_error(logger, "Auto-scaling evaluation error", e)
                await asyncio.sleep(30)  # Wait before retrying
    
    def stop_auto_scaling(self):
        """Stop auto-scaling service"""
        self.running = False
        SecureLogger.safe_log_info(logger, "Auto-scaler stopped")
    
    async def evaluate_scaling_decisions(self):
        """Evaluate if scaling actions are needed"""
        try:
            current_metrics = metrics_collector.get_current_metrics()
            
            for queue_name, rule in self.scaling_rules.items():
                decision = await self.make_scaling_decision(queue_name, rule, current_metrics)
                
                if decision.action != ScalingAction.NO_ACTION:
                    await self.execute_scaling_decision(decision)
                    self.scaling_history.append(decision)
                    
                    # Keep only last 100 scaling decisions
                    if len(self.scaling_history) > 100:
                        self.scaling_history = self.scaling_history[-100:]
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to evaluate scaling decisions", e)
    
    async def make_scaling_decision(self, queue_name: str, rule: ScalingRule, 
                                  current_metrics: Dict) -> ScalingDecision:
        """Make scaling decision for a specific queue"""
        try:
            # Get current queue metrics
            queue_metrics = current_metrics.get('queues', {}).get(queue_name, {})
            queue_length = queue_metrics.get('length', 0)
            current_workers = queue_metrics.get('workers_active', rule.min_workers)
            avg_processing_time = queue_metrics.get('avg_processing_time', 0)
            
            # Get system metrics
            system_metrics = current_metrics.get('system', {})
            cpu_usage = system_metrics.get('cpu_usage', 0)
            memory_usage = system_metrics.get('memory_usage', 0)
            
            # Check cooldown period
            if not self._is_cooldown_expired(queue_name, rule):
                return ScalingDecision(
                    queue_name=queue_name,
                    current_workers=current_workers,
                    target_workers=current_workers,
                    action=ScalingAction.NO_ACTION,
                    reason="Cooldown period active",
                    confidence=1.0
                )
            
            # Calculate scaling factors
            queue_pressure = queue_length / max(current_workers, 1)
            resource_pressure = max(cpu_usage, memory_usage) / 100
            
            # Determine scaling action
            action = ScalingAction.NO_ACTION
            target_workers = current_workers
            reason = "No scaling needed"
            confidence = 0.5
            
            # Scale up conditions
            if (queue_length > rule.scale_up_threshold and 
                current_workers < rule.max_workers and
                (cpu_usage < rule.cpu_threshold or memory_usage < rule.memory_threshold)):
                
                # Calculate target workers based on queue pressure
                if queue_pressure > 3:
                    target_workers = min(current_workers + 2, rule.max_workers)
                    confidence = 0.9
                elif queue_pressure > 1.5:
                    target_workers = min(current_workers + 1, rule.max_workers)
                    confidence = 0.8
                else:
                    target_workers = min(current_workers + 1, rule.max_workers)
                    confidence = 0.6
                
                action = ScalingAction.SCALE_UP
                reason = f"Queue length {queue_length} > threshold {rule.scale_up_threshold}"
            
            # Scale down conditions
            elif (queue_length < rule.scale_down_threshold and 
                  current_workers > rule.min_workers and
                  avg_processing_time < 300):  # Don't scale down if tasks are taking too long
                
                # Be more conservative with scaling down
                if queue_pressure < 0.1 and cpu_usage < 30:
                    target_workers = max(current_workers - 1, rule.min_workers)
                    confidence = 0.7
                    action = ScalingAction.SCALE_DOWN
                    reason = f"Queue length {queue_length} < threshold {rule.scale_down_threshold} and low CPU"
            
            # Resource-based scaling
            elif cpu_usage > rule.cpu_threshold or memory_usage > rule.memory_threshold:
                if current_workers < rule.max_workers:
                    target_workers = min(current_workers + 1, rule.max_workers)
                    action = ScalingAction.SCALE_UP
                    reason = f"High resource usage: CPU {cpu_usage}%, Memory {memory_usage}%"
                    confidence = 0.8
            
            return ScalingDecision(
                queue_name=queue_name,
                current_workers=current_workers,
                target_workers=target_workers,
                action=action,
                reason=reason,
                confidence=confidence
            )
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to make scaling decision", e, {
                'queue_name': queue_name
            })
            
            return ScalingDecision(
                queue_name=queue_name,
                current_workers=0,
                target_workers=0,
                action=ScalingAction.NO_ACTION,
                reason=f"Decision error: {str(e)}",
                confidence=0.0
            )
    
    def _is_cooldown_expired(self, queue_name: str, rule: ScalingRule) -> bool:
        """Check if cooldown period has expired for a queue"""
        last_action = self.last_scaling_action.get(queue_name)
        if not last_action:
            return True
        
        cooldown_period = timedelta(minutes=rule.cooldown_minutes)
        return datetime.utcnow() - last_action > cooldown_period
    
    async def execute_scaling_decision(self, decision: ScalingDecision):
        """Execute the scaling decision"""
        try:
            if decision.confidence < 0.5:
                SecureLogger.safe_log_warning(logger, "Skipping low-confidence scaling decision", {
                    'queue_name': decision.queue_name,
                    'confidence': decision.confidence,
                    'reason': decision.reason
                })
                return
            
            SecureLogger.safe_log_info(logger, "Executing scaling decision", {
                'queue_name': decision.queue_name,
                'action': decision.action.value,
                'current_workers': decision.current_workers,
                'target_workers': decision.target_workers,
                'reason': decision.reason,
                'confidence': decision.confidence
            })
            
            # Execute scaling based on deployment environment
            success = await self._execute_scaling_action(decision)
            
            if success:
                self.last_scaling_action[decision.queue_name] = decision.timestamp
                
                # Record scaling decision in Prometheus
                prometheus_metrics.record_scaling_decision(
                    decision.queue_name, 
                    decision.action.value, 
                    decision.reason[:50],  # Truncate reason for labels
                    decision.target_workers
                )
                
                SecureLogger.safe_log_info(logger, "Scaling action completed successfully", {
                    'queue_name': decision.queue_name,
                    'action': decision.action.value,
                    'target_workers': decision.target_workers
                })
            else:
                SecureLogger.safe_log_error(logger, "Scaling action failed", None, {
                    'queue_name': decision.queue_name,
                    'action': decision.action.value
                })
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to execute scaling decision", e, {
                'queue_name': decision.queue_name,
                'action': decision.action.value
            })
    
    async def _execute_scaling_action(self, decision: ScalingDecision) -> bool:
        """Execute the actual scaling action based on environment"""
        try:
            # Docker Compose scaling
            if await self._is_docker_compose_environment():
                return await self._scale_docker_compose(decision)
            
            # Kubernetes scaling
            elif await self._is_kubernetes_environment():
                return await self._scale_kubernetes(decision)
            
            # Fly.io scaling
            elif await self._is_fly_environment():
                return await self._scale_fly_io(decision)
            
            else:
                SecureLogger.safe_log_warning(logger, "Unknown deployment environment, simulating scaling", {
                    'decision': decision.queue_name
                })
                return True  # Simulate success for development
                
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Scaling execution failed", e)
            return False
    
    async def _scale_docker_compose(self, decision: ScalingDecision) -> bool:
        """Scale using Docker Compose"""
        try:
            # Map queue names to Docker Compose services
            service_mapping = {
                'audio_processing': 'celery-worker-audio',
                'document_generation': 'celery-worker-docs',
                'maintenance': 'celery-worker-general',
                'high_priority': 'celery-worker-general'
            }
            
            service_name = service_mapping.get(decision.queue_name)
            if not service_name:
                return False
            
            # Execute docker-compose scale command
            cmd = [
                'docker-compose', '-f', 'docker-compose.celery.yml',
                'up', '-d', '--scale', f'{service_name}={decision.target_workers}'
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                SecureLogger.safe_log_info(logger, "Docker Compose scaling successful", {
                    'service': service_name,
                    'target_workers': decision.target_workers
                })
                return True
            else:
                SecureLogger.safe_log_error(logger, "Docker Compose scaling failed", None, {
                    'service': service_name,
                    'stderr': stderr.decode() if stderr else 'No error output'
                })
                return False
                
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Docker Compose scaling exception", e)
            return False
    
    async def _scale_kubernetes(self, decision: ScalingDecision) -> bool:
        """Scale using Kubernetes"""
        try:
            # Map queue names to Kubernetes deployments
            deployment_mapping = {
                'audio_processing': 'celery-worker-audio',
                'document_generation': 'celery-worker-docs',
                'maintenance': 'celery-worker-general',
                'high_priority': 'celery-worker-general'
            }
            
            deployment_name = deployment_mapping.get(decision.queue_name)
            if not deployment_name:
                return False
            
            # Execute kubectl scale command
            cmd = [
                'kubectl', 'scale', 'deployment', deployment_name,
                f'--replicas={decision.target_workers}'
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                SecureLogger.safe_log_info(logger, "Kubernetes scaling successful", {
                    'deployment': deployment_name,
                    'target_replicas': decision.target_workers
                })
                return True
            else:
                SecureLogger.safe_log_error(logger, "Kubernetes scaling failed", None, {
                    'deployment': deployment_name,
                    'stderr': stderr.decode() if stderr else 'No error output'
                })
                return False
                
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Kubernetes scaling exception", e)
            return False
    
    async def _scale_fly_io(self, decision: ScalingDecision) -> bool:
        """Scale using Fly.io"""
        try:
            # Fly.io scaling would require fly CLI
            cmd = [
                'fly', 'scale', 'count', str(decision.target_workers),
                '--app', 'whatsapp-interview-bot'  # Your app name
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                SecureLogger.safe_log_info(logger, "Fly.io scaling successful", {
                    'target_instances': decision.target_workers
                })
                return True
            else:
                SecureLogger.safe_log_error(logger, "Fly.io scaling failed", None, {
                    'stderr': stderr.decode() if stderr else 'No error output'
                })
                return False
                
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Fly.io scaling exception", e)
            return False
    
    async def _is_docker_compose_environment(self) -> bool:
        """Check if running in Docker Compose environment"""
        try:
            process = await asyncio.create_subprocess_exec(
                'docker-compose', '--version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            return process.returncode == 0
        except:
            return False
    
    async def _is_kubernetes_environment(self) -> bool:
        """Check if running in Kubernetes environment"""
        try:
            process = await asyncio.create_subprocess_exec(
                'kubectl', 'version', '--client',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            return process.returncode == 0
        except:
            return False
    
    async def _is_fly_environment(self) -> bool:
        """Check if running in Fly.io environment"""
        try:
            process = await asyncio.create_subprocess_exec(
                'fly', 'version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            return process.returncode == 0
        except:
            return False
    
    def get_scaling_status(self) -> Dict[str, any]:
        """Get current auto-scaling status"""
        return {
            'enabled': self.enabled,
            'running': self.running,
            'check_interval': self.check_interval,
            'rules': {name: {
                'min_workers': rule.min_workers,
                'max_workers': rule.max_workers,
                'scale_up_threshold': rule.scale_up_threshold,
                'scale_down_threshold': rule.scale_down_threshold,
                'cooldown_minutes': rule.cooldown_minutes
            } for name, rule in self.scaling_rules.items()},
            'recent_decisions': [
                {
                    'queue_name': d.queue_name,
                    'action': d.action.value,
                    'target_workers': d.target_workers,
                    'reason': d.reason,
                    'confidence': d.confidence,
                    'timestamp': d.timestamp.isoformat()
                }
                for d in self.scaling_history[-10:]  # Last 10 decisions
            ],
            'last_scaling_actions': {
                queue: timestamp.isoformat()
                for queue, timestamp in self.last_scaling_action.items()
            }
        }
    
    def enable_auto_scaling(self):
        """Enable auto-scaling"""
        self.enabled = True
        SecureLogger.safe_log_info(logger, "Auto-scaling enabled")
    
    def disable_auto_scaling(self):
        """Disable auto-scaling"""
        self.enabled = False
        SecureLogger.safe_log_info(logger, "Auto-scaling disabled")

# Global auto-scaler instance
auto_scaler = AutoScaler()