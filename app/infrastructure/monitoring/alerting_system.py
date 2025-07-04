import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.infrastructure.monitoring.business_metrics import business_metrics, SLAStatus
from app.infrastructure.websocket_manager import websocket_manager
from app.utils.secure_logging import SecureLogger
from app.core.config import settings

logger = logging.getLogger(__name__)

class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class AlertChannel(Enum):
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    WEBSOCKET = "websocket"
    SMS = "sms"

@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    metric_name: str
    condition: str  # ">" | "<" | "==" | "!="
    threshold: float
    severity: AlertSeverity
    channels: List[AlertChannel]
    cooldown_minutes: int = 30
    description: str = ""
    enabled: bool = True

@dataclass
class Alert:
    """Alert instance"""
    rule_name: str
    metric_name: str
    current_value: float
    threshold: float
    severity: AlertSeverity
    message: str
    timestamp: datetime
    metadata: Dict[str, Any]
    channels_sent: List[AlertChannel] = None

    def __post_init__(self):
        if self.channels_sent is None:
            self.channels_sent = []

class AlertingSystem:
    """Intelligent alerting system for business metrics"""
    
    def __init__(self):
        self.alert_rules = self._initialize_alert_rules()
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.last_alert_time: Dict[str, datetime] = {}
        self.notification_handlers = self._initialize_handlers()
        self.running = False
        
    def _initialize_alert_rules(self) -> Dict[str, AlertRule]:
        """Initialize default alert rules"""
        return {
            # Critical business metrics
            "interview_success_rate_critical": AlertRule(
                name="Interview Success Rate Critical",
                metric_name="interview_success_rate",
                condition="<",
                threshold=90.0,
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.EMAIL, AlertChannel.WEBSOCKET, AlertChannel.SLACK],
                cooldown_minutes=15,
                description="Interview success rate below 90%"
            ),
            
            "interview_processing_time_critical": AlertRule(
                name="Interview Processing Time Critical",
                metric_name="interview_processing_time",
                condition=">",
                threshold=30.0,
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.EMAIL, AlertChannel.WEBSOCKET],
                cooldown_minutes=30,
                description="Interview processing time exceeds 30 minutes"
            ),
            
            "api_availability_critical": AlertRule(
                name="API Availability Critical",
                metric_name="api_availability",
                condition="<",
                threshold=95.0,
                severity=AlertSeverity.EMERGENCY,
                channels=[AlertChannel.EMAIL, AlertChannel.WEBSOCKET, AlertChannel.SLACK],
                cooldown_minutes=5,
                description="API availability below 95%"
            ),
            
            "error_rate_warning": AlertRule(
                name="Error Rate Warning",
                metric_name="error_rate",
                condition=">",
                threshold=5.0,
                severity=AlertSeverity.WARNING,
                channels=[AlertChannel.WEBSOCKET, AlertChannel.SLACK],
                cooldown_minutes=60,
                description="Error rate above 5%"
            ),
            
            "error_rate_critical": AlertRule(
                name="Error Rate Critical",
                metric_name="error_rate",
                condition=">",
                threshold=15.0,
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.EMAIL, AlertChannel.WEBSOCKET, AlertChannel.SLACK],
                cooldown_minutes=30,
                description="Error rate above 15%"
            ),
            
            "daily_interviews_low": AlertRule(
                name="Daily Interviews Low",
                metric_name="daily_interviews",
                condition="<",
                threshold=20,
                severity=AlertSeverity.WARNING,
                channels=[AlertChannel.WEBSOCKET, AlertChannel.EMAIL],
                cooldown_minutes=120,
                description="Daily interview volume below threshold"
            ),
            
            "cost_per_interview_high": AlertRule(
                name="Cost Per Interview High",
                metric_name="cost_per_interview",
                condition=">",
                threshold=5.0,
                severity=AlertSeverity.WARNING,
                channels=[AlertChannel.EMAIL, AlertChannel.WEBSOCKET],
                cooldown_minutes=60,
                description="Cost per interview exceeds $5"
            ),
            
            "user_satisfaction_low": AlertRule(
                name="User Satisfaction Low",
                metric_name="user_satisfaction",
                condition="<",
                threshold=3.5,
                severity=AlertSeverity.WARNING,
                channels=[AlertChannel.EMAIL, AlertChannel.WEBSOCKET],
                cooldown_minutes=180,
                description="User satisfaction rating below 3.5"
            )
        }
    
    def _initialize_handlers(self) -> Dict[AlertChannel, Callable]:
        """Initialize notification handlers"""
        return {
            AlertChannel.EMAIL: self._send_email_alert,
            AlertChannel.SLACK: self._send_slack_alert,
            AlertChannel.WEBSOCKET: self._send_websocket_alert,
            AlertChannel.WEBHOOK: self._send_webhook_alert,
            AlertChannel.SMS: self._send_sms_alert
        }
    
    async def start_monitoring(self):
        """Start alert monitoring"""
        self.running = True
        
        SecureLogger.safe_log_info(logger, "Alerting system started", {
            "alert_rules_count": len(self.alert_rules),
            "enabled_rules": len([r for r in self.alert_rules.values() if r.enabled])
        })
        
        while self.running:
            try:
                await self._check_all_metrics()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                SecureLogger.safe_log_error(logger, "Alert monitoring error", e)
                await asyncio.sleep(30)
    
    def stop_monitoring(self):
        """Stop alert monitoring"""
        self.running = False
        SecureLogger.safe_log_info(logger, "Alerting system stopped")
    
    async def _check_all_metrics(self):
        """Check all metrics against alert rules"""
        current_metrics = business_metrics.current_metrics
        
        for rule_name, rule in self.alert_rules.items():
            if not rule.enabled:
                continue
                
            metric_value = current_metrics.get(rule.metric_name)
            if metric_value is None:
                continue
            
            # Check if alert condition is met
            if self._evaluate_condition(metric_value, rule.condition, rule.threshold):
                await self._trigger_alert(rule, metric_value)
            else:
                # Check if we should resolve an existing alert
                await self._resolve_alert(rule_name)
    
    def _evaluate_condition(self, value: float, condition: str, threshold: float) -> bool:
        """Evaluate alert condition"""
        if condition == ">":
            return value > threshold
        elif condition == "<":
            return value < threshold
        elif condition == "==":
            return value == threshold
        elif condition == "!=":
            return value != threshold
        return False
    
    async def _trigger_alert(self, rule: AlertRule, current_value: float):
        """Trigger an alert"""
        
        # Check cooldown period
        last_alert = self.last_alert_time.get(rule.name)
        if last_alert:
            cooldown_period = timedelta(minutes=rule.cooldown_minutes)
            if datetime.utcnow() - last_alert < cooldown_period:
                return  # Still in cooldown
        
        # Create alert
        alert = Alert(
            rule_name=rule.name,
            metric_name=rule.metric_name,
            current_value=current_value,
            threshold=rule.threshold,
            severity=rule.severity,
            message=self._format_alert_message(rule, current_value),
            timestamp=datetime.utcnow(),
            metadata={
                "condition": rule.condition,
                "description": rule.description
            }
        )
        
        # Store alert
        self.active_alerts[rule.name] = alert
        self.alert_history.append(alert)
        self.last_alert_time[rule.name] = alert.timestamp
        
        # Keep only last 1000 alerts in history
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]
        
        # Send notifications
        await self._send_alert_notifications(alert, rule.channels)
        
        SecureLogger.safe_log_warning(logger, f"Alert triggered: {rule.name}", {
            "metric_name": rule.metric_name,
            "current_value": current_value,
            "threshold": rule.threshold,
            "severity": rule.severity.value
        })
    
    async def _resolve_alert(self, rule_name: str):
        """Resolve an active alert"""
        if rule_name in self.active_alerts:
            alert = self.active_alerts.pop(rule_name)
            
            # Send resolution notification
            resolution_message = f"🟢 RESOLVED: {alert.rule_name} - {alert.metric_name} is now within acceptable range"
            
            await self._send_resolution_notifications(alert, resolution_message)
            
            SecureLogger.safe_log_info(logger, f"Alert resolved: {rule_name}", {
                "metric_name": alert.metric_name
            })
    
    def _format_alert_message(self, rule: AlertRule, current_value: float) -> str:
        """Format alert message"""
        severity_emoji = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️", 
            AlertSeverity.CRITICAL: "🚨",
            AlertSeverity.EMERGENCY: "🆘"
        }
        
        emoji = severity_emoji.get(rule.severity, "⚠️")
        
        return (
            f"{emoji} {rule.severity.value.upper()}: {rule.name}\n\n"
            f"Metric: {rule.metric_name}\n"
            f"Current Value: {current_value:.2f}\n"
            f"Threshold: {rule.condition} {rule.threshold}\n"
            f"Description: {rule.description}\n"
            f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
    
    async def _send_alert_notifications(self, alert: Alert, channels: List[AlertChannel]):
        """Send alert notifications to all channels"""
        
        for channel in channels:
            try:
                handler = self.notification_handlers.get(channel)
                if handler:
                    success = await handler(alert)
                    if success:
                        alert.channels_sent.append(channel)
            except Exception as e:
                SecureLogger.safe_log_error(logger, f"Failed to send alert via {channel.value}", e)
    
    async def _send_resolution_notifications(self, alert: Alert, message: str):
        """Send alert resolution notifications"""
        
        for channel in alert.channels_sent:
            try:
                handler = self.notification_handlers.get(channel)
                if handler:
                    # Create a temporary alert for resolution
                    resolution_alert = Alert(
                        rule_name=alert.rule_name,
                        metric_name=alert.metric_name,
                        current_value=0,  # Not relevant for resolution
                        threshold=alert.threshold,
                        severity=AlertSeverity.INFO,
                        message=message,
                        timestamp=datetime.utcnow(),
                        metadata={"type": "resolution", "original_alert": alert.rule_name}
                    )
                    await handler(resolution_alert)
            except Exception as e:
                SecureLogger.safe_log_error(logger, f"Failed to send resolution via {channel.value}", e)
    
    async def _send_email_alert(self, alert: Alert) -> bool:
        """Send email alert"""
        try:
            # Email configuration (should be in settings)
            smtp_server = getattr(settings, 'SMTP_SERVER', 'localhost')
            smtp_port = getattr(settings, 'SMTP_PORT', 587)
            smtp_username = getattr(settings, 'SMTP_USERNAME', '')
            smtp_password = getattr(settings, 'SMTP_PASSWORD', '')
            alert_email = getattr(settings, 'ALERT_EMAIL', 'admin@whatsapp-bot.com')
            
            if not all([smtp_server, alert_email]):
                return False
            
            msg = MIMEMultipart()
            msg['From'] = smtp_username or alert_email
            msg['To'] = alert_email
            msg['Subject'] = f"[WhatsApp Bot] {alert.severity.value.upper()}: {alert.rule_name}"
            
            body = alert.message
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            if smtp_username and smtp_password:
                server.starttls()
                server.login(smtp_username, smtp_password)
            
            server.send_message(msg)
            server.quit()
            
            return True
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to send email alert", e)
            return False
    
    async def _send_slack_alert(self, alert: Alert) -> bool:
        """Send Slack alert"""
        try:
            slack_webhook = getattr(settings, 'SLACK_WEBHOOK_URL', None)
            if not slack_webhook:
                return False
            
            import aiohttp
            
            color_map = {
                AlertSeverity.INFO: "#36a64f",
                AlertSeverity.WARNING: "#ff9500", 
                AlertSeverity.CRITICAL: "#ff0000",
                AlertSeverity.EMERGENCY: "#8b0000"
            }
            
            payload = {
                "attachments": [{
                    "color": color_map.get(alert.severity, "#ff9500"),
                    "title": f"{alert.severity.value.upper()}: {alert.rule_name}",
                    "text": alert.message,
                    "footer": "WhatsApp Interview Bot",
                    "ts": int(alert.timestamp.timestamp())
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(slack_webhook, json=payload) as response:
                    return response.status == 200
                    
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to send Slack alert", e)
            return False
    
    async def _send_websocket_alert(self, alert: Alert) -> bool:
        """Send WebSocket alert"""
        try:
            alert_message = {
                "type": "business_alert",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "rule_name": alert.rule_name,
                    "metric_name": alert.metric_name,
                    "current_value": alert.current_value,
                    "threshold": alert.threshold,
                    "severity": alert.severity.value,
                    "message": alert.message,
                    "metadata": alert.metadata
                }
            }
            
            await websocket_manager.broadcast_to_dashboard(alert_message)
            return True
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to send WebSocket alert", e)
            return False
    
    async def _send_webhook_alert(self, alert: Alert) -> bool:
        """Send webhook alert"""
        try:
            webhook_url = getattr(settings, 'ALERT_WEBHOOK_URL', None)
            if not webhook_url:
                return False
            
            import aiohttp
            
            payload = {
                "alert": {
                    "rule_name": alert.rule_name,
                    "metric_name": alert.metric_name,
                    "current_value": alert.current_value,
                    "threshold": alert.threshold,
                    "severity": alert.severity.value,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                    "metadata": alert.metadata
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    return response.status == 200
                    
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to send webhook alert", e)
            return False
    
    async def _send_sms_alert(self, alert: Alert) -> bool:
        """Send SMS alert (placeholder)"""
        # SMS integration would require a service like Twilio
        SecureLogger.safe_log_info(logger, "SMS alert not implemented", {
            "alert": alert.rule_name
        })
        return False
    
    def get_alert_status(self) -> Dict[str, Any]:
        """Get current alerting system status"""
        return {
            "running": self.running,
            "active_alerts": len(self.active_alerts),
            "total_rules": len(self.alert_rules),
            "enabled_rules": len([r for r in self.alert_rules.values() if r.enabled]),
            "alert_history_count": len(self.alert_history),
            "active_alert_details": [
                {
                    "rule_name": alert.rule_name,
                    "metric_name": alert.metric_name,
                    "severity": alert.severity.value,
                    "current_value": alert.current_value,
                    "threshold": alert.threshold,
                    "triggered_at": alert.timestamp.isoformat()
                }
                for alert in self.active_alerts.values()
            ]
        }
    
    async def add_custom_rule(self, rule: AlertRule) -> bool:
        """Add custom alert rule"""
        try:
            self.alert_rules[rule.name] = rule
            SecureLogger.safe_log_info(logger, "Custom alert rule added", {
                "rule_name": rule.name,
                "metric_name": rule.metric_name
            })
            return True
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to add custom alert rule", e)
            return False
    
    async def test_alert(self, rule_name: str) -> bool:
        """Test alert by forcing trigger"""
        rule = self.alert_rules.get(rule_name)
        if not rule:
            return False
        
        test_alert = Alert(
            rule_name=rule.name,
            metric_name=rule.metric_name,
            current_value=rule.threshold + 1 if rule.condition == ">" else rule.threshold - 1,
            threshold=rule.threshold,
            severity=rule.severity,
            message=f"🧪 TEST ALERT: {rule.name} - This is a test alert",
            timestamp=datetime.utcnow(),
            metadata={"type": "test", "original_rule": rule.name}
        )
        
        await self._send_alert_notifications(test_alert, rule.channels)
        
        SecureLogger.safe_log_info(logger, "Test alert sent", {
            "rule_name": rule_name
        })
        
        return True

# Global alerting system
alerting_system = AlertingSystem()