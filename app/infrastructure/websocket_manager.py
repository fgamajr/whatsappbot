import asyncio
import json
import logging
from typing import Dict, List, Set, Any, Optional
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from app.utils.secure_logging import SecureLogger
from app.infrastructure.redis_client import redis_client
from app.infrastructure.prometheus_metrics import prometheus_metrics

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        # Active connections grouped by type
        self.active_connections: Dict[str, List[WebSocket]] = {
            'dashboard': [],      # Admin dashboard connections
            'pipeline': [],       # Pipeline monitoring connections  
            'interviews': {},     # Interview-specific connections {interview_id: [websockets]}
            'metrics': []         # System metrics connections
        }
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        
    async def connect_dashboard(self, websocket: WebSocket, user_id: str = None):
        """Connect to dashboard updates"""
        await websocket.accept()
        self.active_connections['dashboard'].append(websocket)
        self.connection_metadata[websocket] = {
            'type': 'dashboard',
            'user_id': user_id,
            'connected_at': datetime.utcnow(),
            'last_ping': datetime.utcnow()
        }
        
        SecureLogger.safe_log_info(logger, "Dashboard WebSocket connected", {
            'user_id': user_id,
            'total_dashboard_connections': len(self.active_connections['dashboard'])
        })
        
        # Update Prometheus metrics
        prometheus_metrics.update_websocket_metrics('dashboard', len(self.active_connections['dashboard']))
        
        # Send initial dashboard data
        await self.send_dashboard_initial_data(websocket)
    
    async def connect_pipeline_monitor(self, websocket: WebSocket, pipeline_id: str = None):
        """Connect to pipeline monitoring updates"""
        await websocket.accept()
        self.active_connections['pipeline'].append(websocket)
        self.connection_metadata[websocket] = {
            'type': 'pipeline',
            'pipeline_id': pipeline_id,
            'connected_at': datetime.utcnow(),
            'last_ping': datetime.utcnow()
        }
        
        SecureLogger.safe_log_info(logger, "Pipeline WebSocket connected", {
            'pipeline_id': pipeline_id,
            'total_pipeline_connections': len(self.active_connections['pipeline'])
        })
    
    async def connect_interview_updates(self, websocket: WebSocket, interview_id: str, user_phone: str = None):
        """Connect to specific interview updates"""
        await websocket.accept()
        
        if interview_id not in self.active_connections['interviews']:
            self.active_connections['interviews'][interview_id] = []
        
        self.active_connections['interviews'][interview_id].append(websocket)
        self.connection_metadata[websocket] = {
            'type': 'interview',
            'interview_id': interview_id,
            'user_phone': SecureLogger.mask_phone_number(user_phone) if user_phone else None,
            'connected_at': datetime.utcnow(),
            'last_ping': datetime.utcnow()
        }
        
        SecureLogger.safe_log_info(logger, "Interview WebSocket connected", {
            'interview_id': interview_id,
            'user_phone': SecureLogger.mask_phone_number(user_phone) if user_phone else None,
            'connections_for_interview': len(self.active_connections['interviews'][interview_id])
        })
        
        # Send current interview status
        await self.send_interview_initial_status(websocket, interview_id)
    
    async def connect_metrics_stream(self, websocket: WebSocket, admin_user: str = None):
        """Connect to real-time metrics stream"""
        await websocket.accept()
        self.active_connections['metrics'].append(websocket)
        self.connection_metadata[websocket] = {
            'type': 'metrics',
            'admin_user': admin_user,
            'connected_at': datetime.utcnow(),
            'last_ping': datetime.utcnow()
        }
        
        SecureLogger.safe_log_info(logger, "Metrics WebSocket connected", {
            'admin_user': admin_user,
            'total_metrics_connections': len(self.active_connections['metrics'])
        })
    
    async def disconnect(self, websocket: WebSocket):
        """Disconnect and clean up WebSocket"""
        try:
            metadata = self.connection_metadata.get(websocket, {})
            connection_type = metadata.get('type', 'unknown')
            
            # Remove from appropriate connection list
            if connection_type == 'dashboard':
                self.active_connections['dashboard'].remove(websocket)
            elif connection_type == 'pipeline':
                self.active_connections['pipeline'].remove(websocket)
            elif connection_type == 'interview':
                interview_id = metadata.get('interview_id')
                if interview_id and interview_id in self.active_connections['interviews']:
                    self.active_connections['interviews'][interview_id].remove(websocket)
                    # Clean up empty interview lists
                    if not self.active_connections['interviews'][interview_id]:
                        del self.active_connections['interviews'][interview_id]
            elif connection_type == 'metrics':
                self.active_connections['metrics'].remove(websocket)
            
            # Remove metadata
            if websocket in self.connection_metadata:
                del self.connection_metadata[websocket]
            
            SecureLogger.safe_log_info(logger, "WebSocket disconnected", {
                'connection_type': connection_type,
                'interview_id': metadata.get('interview_id'),
                'user_id': metadata.get('user_id')
            })
            
        except ValueError:
            # Connection was already removed
            pass
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Error during WebSocket disconnect", e)
    
    async def send_dashboard_initial_data(self, websocket: WebSocket):
        """Send initial dashboard data to new connection"""
        try:
            from app.infrastructure.metrics_collector import metrics_collector
            from app.infrastructure.auto_scaler import auto_scaler
            
            initial_data = {
                'type': 'dashboard_init',
                'timestamp': datetime.utcnow().isoformat(),
                'data': {
                    'metrics': metrics_collector.get_current_metrics(),
                    'auto_scaling': auto_scaler.get_scaling_status(),
                    'system_status': 'operational'
                }
            }
            
            await websocket.send_text(json.dumps(initial_data))
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to send dashboard initial data", e)
    
    async def send_interview_initial_status(self, websocket: WebSocket, interview_id: str):
        """Send current interview status to new connection"""
        try:
            # Get interview status from database
            from app.infrastructure.database.repositories.interview import InterviewRepository
            
            repo = InterviewRepository()
            interview = await repo.get_by_id(interview_id)
            
            if interview:
                status_data = {
                    'type': 'interview_status',
                    'timestamp': datetime.utcnow().isoformat(),
                    'interview_id': interview_id,
                    'data': {
                        'status': interview.status.value,
                        'progress': {
                            'chunks_total': interview.chunks_total or 0,
                            'chunks_processed': interview.chunks_processed or 0,
                            'percentage': int((interview.chunks_processed or 0) / max(interview.chunks_total or 1, 1) * 100)
                        },
                        'created_at': interview.created_at.isoformat() if interview.created_at else None,
                        'estimated_completion': self.calculate_estimated_completion(interview)
                    }
                }
                
                await websocket.send_text(json.dumps(status_data))
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to send interview initial status", e, {
                'interview_id': interview_id
            })
    
    def calculate_estimated_completion(self, interview) -> Optional[str]:
        """Calculate estimated completion time for interview"""
        try:
            if not interview.chunks_total or interview.chunks_processed >= interview.chunks_total:
                return None
            
            # Simple estimation based on average processing time
            remaining_chunks = interview.chunks_total - interview.chunks_processed
            avg_time_per_chunk = 300  # 5 minutes average
            
            estimated_seconds = remaining_chunks * avg_time_per_chunk
            estimated_completion = datetime.utcnow().timestamp() + estimated_seconds
            
            return datetime.fromtimestamp(estimated_completion).isoformat()
            
        except Exception:
            return None
    
    # ================================
    # BROADCAST METHODS
    # ================================
    
    async def broadcast_to_dashboard(self, message: Dict[str, Any]):
        """Broadcast message to all dashboard connections"""
        await self._broadcast_to_connections(self.active_connections['dashboard'], message)
    
    async def broadcast_to_pipeline_monitors(self, message: Dict[str, Any]):
        """Broadcast message to all pipeline monitoring connections"""
        await self._broadcast_to_connections(self.active_connections['pipeline'], message)
    
    async def broadcast_to_interview(self, interview_id: str, message: Dict[str, Any]):
        """Broadcast message to specific interview connections"""
        if interview_id in self.active_connections['interviews']:
            connections = self.active_connections['interviews'][interview_id]
            await self._broadcast_to_connections(connections, message)
    
    async def broadcast_to_metrics_subscribers(self, message: Dict[str, Any]):
        """Broadcast message to metrics stream connections"""
        await self._broadcast_to_connections(self.active_connections['metrics'], message)
    
    async def _broadcast_to_connections(self, connections: List[WebSocket], message: Dict[str, Any]):
        """Broadcast message to a list of connections"""
        if not connections:
            return
        
        message_str = json.dumps(message)
        disconnected_connections = []
        
        for connection in connections:
            try:
                await connection.send_text(message_str)
                # Update last ping time
                if connection in self.connection_metadata:
                    self.connection_metadata[connection]['last_ping'] = datetime.utcnow()
                
                # Record message sent in Prometheus
                connection_type = self.connection_metadata.get(connection, {}).get('type', 'unknown')
                message_type = message.get('type', 'unknown')
                prometheus_metrics.record_websocket_message(message_type, connection_type)
                    
            except WebSocketDisconnect:
                disconnected_connections.append(connection)
            except Exception as e:
                SecureLogger.safe_log_error(logger, "Failed to send WebSocket message", e)
                disconnected_connections.append(connection)
        
        # Clean up disconnected connections
        for connection in disconnected_connections:
            await self.disconnect(connection)
    
    # ================================
    # INTERVIEW PROGRESS UPDATES
    # ================================
    
    async def update_interview_progress(self, interview_id: str, progress_data: Dict[str, Any]):
        """Send interview progress update"""
        message = {
            'type': 'interview_progress',
            'timestamp': datetime.utcnow().isoformat(),
            'interview_id': interview_id,
            'data': progress_data
        }
        
        await self.broadcast_to_interview(interview_id, message)
        
        SecureLogger.safe_log_info(logger, "Interview progress update sent", {
            'interview_id': interview_id,
            'progress_data': progress_data
        })
    
    async def update_interview_status(self, interview_id: str, new_status: str, additional_data: Dict[str, Any] = None):
        """Send interview status change update"""
        message = {
            'type': 'interview_status_change',
            'timestamp': datetime.utcnow().isoformat(),
            'interview_id': interview_id,
            'data': {
                'new_status': new_status,
                **(additional_data or {})
            }
        }
        
        await self.broadcast_to_interview(interview_id, message)
        
        SecureLogger.safe_log_info(logger, "Interview status update sent", {
            'interview_id': interview_id,
            'new_status': new_status
        })
    
    async def send_interview_error(self, interview_id: str, error_message: str, error_type: str = 'processing_error'):
        """Send interview error notification"""
        message = {
            'type': 'interview_error',
            'timestamp': datetime.utcnow().isoformat(),
            'interview_id': interview_id,
            'data': {
                'error_type': error_type,
                'error_message': error_message,
                'user_friendly_message': self._get_user_friendly_error_message(error_type)
            }
        }
        
        await self.broadcast_to_interview(interview_id, message)
        
        SecureLogger.safe_log_warning(logger, "Interview error notification sent", {
            'interview_id': interview_id,
            'error_type': error_type
        })
    
    def _get_user_friendly_error_message(self, error_type: str) -> str:
        """Convert error types to user-friendly messages"""
        error_messages = {
            'processing_error': 'Houve um erro no processamento do áudio. Tentaremos novamente.',
            'download_error': 'Não foi possível baixar o áudio. Verifique o arquivo enviado.',
            'transcription_error': 'Erro na transcrição do áudio. O arquivo pode estar corrompido.',
            'analysis_error': 'Erro na análise do conteúdo. A transcrição será fornecida.',
            'document_error': 'Erro na geração dos documentos. Tentaremos reenviar.',
            'timeout_error': 'O processamento está demorando mais que o esperado.'
        }
        
        return error_messages.get(error_type, 'Erro inesperado no processamento.')
    
    # ================================
    # SYSTEM METRICS UPDATES
    # ================================
    
    async def broadcast_metrics_update(self, metrics_data: Dict[str, Any]):
        """Broadcast system metrics update"""
        message = {
            'type': 'metrics_update',
            'timestamp': datetime.utcnow().isoformat(),
            'data': metrics_data
        }
        
        await self.broadcast_to_metrics_subscribers(message)
        await self.broadcast_to_dashboard(message)
    
    async def broadcast_scaling_event(self, scaling_data: Dict[str, Any]):
        """Broadcast auto-scaling event"""
        message = {
            'type': 'scaling_event',
            'timestamp': datetime.utcnow().isoformat(),
            'data': scaling_data
        }
        
        await self.broadcast_to_dashboard(message)
        await self.broadcast_to_pipeline_monitors(message)
    
    async def broadcast_pipeline_status(self, pipeline_id: str, status_data: Dict[str, Any]):
        """Broadcast pipeline status update"""
        message = {
            'type': 'pipeline_status',
            'timestamp': datetime.utcnow().isoformat(),
            'pipeline_id': pipeline_id,
            'data': status_data
        }
        
        await self.broadcast_to_pipeline_monitors(message)
        await self.broadcast_to_dashboard(message)
    
    # ================================
    # CONNECTION MANAGEMENT
    # ================================
    
    async def ping_all_connections(self):
        """Send ping to all connections to keep them alive"""
        ping_message = {
            'type': 'ping',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        all_connections = []
        all_connections.extend(self.active_connections['dashboard'])
        all_connections.extend(self.active_connections['pipeline'])
        all_connections.extend(self.active_connections['metrics'])
        
        for interview_connections in self.active_connections['interviews'].values():
            all_connections.extend(interview_connections)
        
        await self._broadcast_to_connections(all_connections, ping_message)
    
    async def cleanup_stale_connections(self):
        """Clean up connections that haven't responded to pings"""
        stale_connections = []
        cutoff_time = datetime.utcnow().timestamp() - 300  # 5 minutes
        
        for connection, metadata in self.connection_metadata.items():
            last_ping = metadata.get('last_ping', datetime.utcnow()).timestamp()
            if last_ping < cutoff_time:
                stale_connections.append(connection)
        
        for connection in stale_connections:
            await self.disconnect(connection)
        
        if stale_connections:
            SecureLogger.safe_log_info(logger, "Cleaned up stale connections", {
                'stale_connections_count': len(stale_connections)
            })
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics"""
        return {
            'dashboard_connections': len(self.active_connections['dashboard']),
            'pipeline_connections': len(self.active_connections['pipeline']),
            'metrics_connections': len(self.active_connections['metrics']),
            'interview_connections': {
                interview_id: len(connections)
                for interview_id, connections in self.active_connections['interviews'].items()
            },
            'total_connections': (
                len(self.active_connections['dashboard']) +
                len(self.active_connections['pipeline']) +
                len(self.active_connections['metrics']) +
                sum(len(conns) for conns in self.active_connections['interviews'].values())
            ),
            'connection_metadata_count': len(self.connection_metadata)
        }

# Global WebSocket manager instance
websocket_manager = WebSocketManager()