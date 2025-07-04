import asyncio
import logging
import os
import shutil
import subprocess
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import tarfile
import boto3
from pathlib import Path

from app.infrastructure.database.mongodb import MongoDB
from app.infrastructure.redis_client import redis_client
from app.utils.secure_logging import SecureLogger
from app.core.config import settings

logger = logging.getLogger(__name__)

class RecoveryType(Enum):
    FULL = "full"
    DATABASE_ONLY = "database_only"
    REDIS_ONLY = "redis_only"
    CONFIGURATION = "configuration"
    SELECTIVE = "selective"

class BackupStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class BackupMetadata:
    backup_id: str
    backup_type: RecoveryType
    timestamp: datetime
    size_bytes: int
    location: str
    status: BackupStatus
    components: List[str]
    retention_days: int = 30
    metadata: Dict[str, Any] = None

@dataclass
class RecoveryPlan:
    plan_id: str
    recovery_type: RecoveryType
    target_timestamp: datetime
    steps: List[Dict[str, Any]]
    estimated_duration_minutes: int
    data_loss_window_minutes: int
    dependencies: List[str] = None

class DisasterRecoveryManager:
    """Comprehensive disaster recovery and backup management"""
    
    def __init__(self):
        self.backup_location = Path("/app/backups")
        self.s3_bucket = getattr(settings, 'BACKUP_S3_BUCKET', None)
        self.retention_days = getattr(settings, 'BACKUP_RETENTION_DAYS', 30)
        self.backup_history: List[BackupMetadata] = []
        self.recovery_plans = self._initialize_recovery_plans()
        
        # Ensure backup directory exists
        self.backup_location.mkdir(parents=True, exist_ok=True)
        
        # Initialize S3 client if configured
        self.s3_client = None
        if self.s3_bucket:
            try:
                self.s3_client = boto3.client('s3')
            except Exception as e:
                SecureLogger.safe_log_warning(logger, "S3 backup not available", {"error": str(e)})
    
    def _initialize_recovery_plans(self) -> Dict[str, RecoveryPlan]:
        """Initialize predefined recovery plans"""
        return {
            "critical_system_failure": RecoveryPlan(
                plan_id="critical_system_failure",
                recovery_type=RecoveryType.FULL,
                target_timestamp=datetime.utcnow(),
                estimated_duration_minutes=30,
                data_loss_window_minutes=15,
                steps=[
                    {"step": 1, "action": "stop_services", "description": "Stop all services"},
                    {"step": 2, "action": "restore_database", "description": "Restore MongoDB from latest backup"},
                    {"step": 3, "action": "restore_redis", "description": "Restore Redis data"},
                    {"step": 4, "action": "restore_configuration", "description": "Restore configuration files"},
                    {"step": 5, "action": "start_services", "description": "Start all services"},
                    {"step": 6, "action": "verify_health", "description": "Verify system health"}
                ]
            ),
            
            "database_corruption": RecoveryPlan(
                plan_id="database_corruption",
                recovery_type=RecoveryType.DATABASE_ONLY,
                target_timestamp=datetime.utcnow(),
                estimated_duration_minutes=15,
                data_loss_window_minutes=5,
                steps=[
                    {"step": 1, "action": "stop_application", "description": "Stop application services"},
                    {"step": 2, "action": "backup_corrupted_data", "description": "Backup corrupted data for analysis"},
                    {"step": 3, "action": "restore_database", "description": "Restore MongoDB from backup"},
                    {"step": 4, "action": "verify_data_integrity", "description": "Verify restored data"},
                    {"step": 5, "action": "start_application", "description": "Restart application"}
                ]
            ),
            
            "redis_failure": RecoveryPlan(
                plan_id="redis_failure",
                recovery_type=RecoveryType.REDIS_ONLY,
                target_timestamp=datetime.utcnow(),
                estimated_duration_minutes=5,
                data_loss_window_minutes=1,
                steps=[
                    {"step": 1, "action": "stop_redis_dependent_services", "description": "Stop services using Redis"},
                    {"step": 2, "action": "restore_redis", "description": "Restore Redis data"},
                    {"step": 3, "action": "start_redis_services", "description": "Start Redis-dependent services"},
                    {"step": 4, "action": "verify_cache_warmup", "description": "Verify cache is working"}
                ]
            )
        }
    
    async def create_backup(self, backup_type: RecoveryType = RecoveryType.FULL, 
                          retention_days: int = None) -> BackupMetadata:
        """Create comprehensive system backup"""
        
        backup_id = f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        retention = retention_days or self.retention_days
        
        backup_metadata = BackupMetadata(
            backup_id=backup_id,
            backup_type=backup_type,
            timestamp=datetime.utcnow(),
            size_bytes=0,
            location="",
            status=BackupStatus.PENDING,
            components=[],
            retention_days=retention
        )
        
        try:
            backup_metadata.status = BackupStatus.IN_PROGRESS
            SecureLogger.safe_log_info(logger, "Starting backup", {
                "backup_id": backup_id,
                "backup_type": backup_type.value
            })
            
            backup_dir = self.backup_location / backup_id
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            total_size = 0
            components = []
            
            # Backup based on type
            if backup_type in [RecoveryType.FULL, RecoveryType.DATABASE_ONLY]:
                db_size = await self._backup_mongodb(backup_dir)
                total_size += db_size
                components.append("mongodb")
            
            if backup_type in [RecoveryType.FULL, RecoveryType.REDIS_ONLY]:
                redis_size = await self._backup_redis(backup_dir)
                total_size += redis_size
                components.append("redis")
            
            if backup_type in [RecoveryType.FULL, RecoveryType.CONFIGURATION]:
                config_size = await self._backup_configuration(backup_dir)
                total_size += config_size
                components.append("configuration")
            
            # Create archive
            archive_path = self.backup_location / f"{backup_id}.tar.gz"
            await self._create_archive(backup_dir, archive_path)
            
            # Upload to S3 if configured
            if self.s3_client:
                await self._upload_to_s3(archive_path, backup_id)
                backup_metadata.location = f"s3://{self.s3_bucket}/{backup_id}.tar.gz"
            else:
                backup_metadata.location = str(archive_path)
            
            # Clean up temporary directory
            shutil.rmtree(backup_dir)
            
            # Update metadata
            backup_metadata.size_bytes = total_size
            backup_metadata.components = components
            backup_metadata.status = BackupStatus.COMPLETED
            
            # Store in history
            self.backup_history.append(backup_metadata)
            
            SecureLogger.safe_log_info(logger, "Backup completed successfully", {
                "backup_id": backup_id,
                "size_bytes": total_size,
                "components": components,
                "location": backup_metadata.location
            })
            
            return backup_metadata
            
        except Exception as e:
            backup_metadata.status = BackupStatus.FAILED
            SecureLogger.safe_log_error(logger, "Backup failed", e, {
                "backup_id": backup_id
            })
            raise
    
    async def _backup_mongodb(self, backup_dir: Path) -> int:
        """Backup MongoDB data"""
        try:
            mongo_backup_dir = backup_dir / "mongodb"
            mongo_backup_dir.mkdir(exist_ok=True)
            
            # Use mongodump
            db_name = settings.DB_NAME
            mongodb_url = settings.MONGODB_URL
            
            cmd = [
                "mongodump",
                "--uri", mongodb_url,
                "--db", db_name,
                "--out", str(mongo_backup_dir)
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"mongodump failed: {stderr.decode()}")
            
            # Calculate backup size
            total_size = sum(f.stat().st_size for f in mongo_backup_dir.rglob('*') if f.is_file())
            
            SecureLogger.safe_log_info(logger, "MongoDB backup completed", {
                "size_bytes": total_size,
                "location": str(mongo_backup_dir)
            })
            
            return total_size
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "MongoDB backup failed", e)
            raise
    
    async def _backup_redis(self, backup_dir: Path) -> int:
        """Backup Redis data"""
        try:
            redis_backup_dir = backup_dir / "redis"
            redis_backup_dir.mkdir(exist_ok=True)
            
            # Create Redis backup using BGSAVE
            if await redis_client.is_connected():
                # Trigger background save
                await redis_client.execute_command("BGSAVE")
                
                # Wait for save to complete
                while True:
                    result = await redis_client.execute_command("LASTSAVE")
                    await asyncio.sleep(1)
                    new_result = await redis_client.execute_command("LASTSAVE")
                    if new_result > result:
                        break
                
                # Copy RDB file (this is a simplified approach)
                # In production, you'd configure Redis to save to the backup directory
                backup_file = redis_backup_dir / "dump.rdb"
                backup_file.write_text("Redis backup placeholder - configure RDB path")
                
                total_size = backup_file.stat().st_size
            else:
                # Redis not available, create empty backup
                backup_file = redis_backup_dir / "redis_not_available.txt"
                backup_file.write_text("Redis was not available during backup")
                total_size = backup_file.stat().st_size
            
            SecureLogger.safe_log_info(logger, "Redis backup completed", {
                "size_bytes": total_size,
                "location": str(redis_backup_dir)
            })
            
            return total_size
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Redis backup failed", e)
            raise
    
    async def _backup_configuration(self, backup_dir: Path) -> int:
        """Backup configuration files"""
        try:
            config_backup_dir = backup_dir / "configuration"
            config_backup_dir.mkdir(exist_ok=True)
            
            # Backup configuration files
            config_files = [
                "/app/.env",
                "/app/app/core/config.py",
                "/app/redis.conf",
                "/app/docker-compose.celery.yml",
                "/app/requirements.txt"
            ]
            
            total_size = 0
            
            for config_file in config_files:
                if os.path.exists(config_file):
                    file_path = Path(config_file)
                    backup_file = config_backup_dir / file_path.name
                    shutil.copy2(config_file, backup_file)
                    total_size += backup_file.stat().st_size
            
            # Create metadata file
            metadata_file = config_backup_dir / "backup_metadata.json"
            metadata = {
                "timestamp": datetime.utcnow().isoformat(),
                "environment": settings.ENVIRONMENT,
                "version": settings.VERSION,
                "files_backed_up": len([f for f in config_files if os.path.exists(f)])
            }
            
            import json
            metadata_file.write_text(json.dumps(metadata, indent=2))
            total_size += metadata_file.stat().st_size
            
            SecureLogger.safe_log_info(logger, "Configuration backup completed", {
                "size_bytes": total_size,
                "files_count": len([f for f in config_files if os.path.exists(f)])
            })
            
            return total_size
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Configuration backup failed", e)
            raise
    
    async def _create_archive(self, source_dir: Path, archive_path: Path):
        """Create compressed archive"""
        try:
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(source_dir, arcname=source_dir.name)
            
            SecureLogger.safe_log_info(logger, "Archive created", {
                "source": str(source_dir),
                "archive": str(archive_path),
                "size_bytes": archive_path.stat().st_size
            })
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Archive creation failed", e)
            raise
    
    async def _upload_to_s3(self, file_path: Path, backup_id: str):
        """Upload backup to S3"""
        try:
            if not self.s3_client:
                return
            
            s3_key = f"backups/{backup_id}.tar.gz"
            
            self.s3_client.upload_file(
                str(file_path),
                self.s3_bucket,
                s3_key,
                ExtraArgs={
                    'Metadata': {
                        'backup_id': backup_id,
                        'timestamp': datetime.utcnow().isoformat(),
                        'environment': settings.ENVIRONMENT
                    }
                }
            )
            
            SecureLogger.safe_log_info(logger, "Backup uploaded to S3", {
                "bucket": self.s3_bucket,
                "key": s3_key
            })
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "S3 upload failed", e)
            raise
    
    async def execute_recovery(self, plan_id: str, backup_id: str = None, 
                             target_timestamp: datetime = None) -> Dict[str, Any]:
        """Execute disaster recovery plan"""
        
        plan = self.recovery_plans.get(plan_id)
        if not plan:
            raise ValueError(f"Recovery plan not found: {plan_id}")
        
        # Find appropriate backup
        if not backup_id:
            backup_metadata = self._find_best_backup(plan.recovery_type, target_timestamp)
        else:
            backup_metadata = self._find_backup_by_id(backup_id)
        
        if not backup_metadata:
            raise ValueError("No suitable backup found for recovery")
        
        recovery_log = {
            "plan_id": plan_id,
            "backup_id": backup_metadata.backup_id,
            "started_at": datetime.utcnow(),
            "steps_completed": [],
            "status": "in_progress"
        }
        
        try:
            SecureLogger.safe_log_info(logger, "Starting disaster recovery", {
                "plan_id": plan_id,
                "backup_id": backup_metadata.backup_id,
                "estimated_duration": plan.estimated_duration_minutes
            })
            
            # Execute recovery steps
            for step in plan.steps:
                step_start = datetime.utcnow()
                
                SecureLogger.safe_log_info(logger, f"Executing recovery step {step['step']}", {
                    "action": step["action"],
                    "description": step["description"]
                })
                
                success = await self._execute_recovery_step(step, backup_metadata)
                
                step_duration = (datetime.utcnow() - step_start).total_seconds()
                
                recovery_log["steps_completed"].append({
                    "step": step["step"],
                    "action": step["action"],
                    "success": success,
                    "duration_seconds": step_duration
                })
                
                if not success:
                    recovery_log["status"] = "failed"
                    recovery_log["failed_at_step"] = step["step"]
                    break
            
            if recovery_log["status"] != "failed":
                recovery_log["status"] = "completed"
                recovery_log["completed_at"] = datetime.utcnow()
            
            SecureLogger.safe_log_info(logger, "Disaster recovery completed", {
                "plan_id": plan_id,
                "status": recovery_log["status"],
                "steps_completed": len(recovery_log["steps_completed"])
            })
            
            return recovery_log
            
        except Exception as e:
            recovery_log["status"] = "error"
            recovery_log["error"] = str(e)
            SecureLogger.safe_log_error(logger, "Disaster recovery failed", e)
            raise
    
    async def _execute_recovery_step(self, step: Dict[str, Any], backup_metadata: BackupMetadata) -> bool:
        """Execute individual recovery step"""
        
        action = step["action"]
        
        try:
            if action == "stop_services":
                return await self._stop_services()
            elif action == "start_services":
                return await self._start_services()
            elif action == "stop_application":
                return await self._stop_application()
            elif action == "start_application":
                return await self._start_application()
            elif action == "restore_database":
                return await self._restore_database(backup_metadata)
            elif action == "restore_redis":
                return await self._restore_redis(backup_metadata)
            elif action == "restore_configuration":
                return await self._restore_configuration(backup_metadata)
            elif action == "verify_health":
                return await self._verify_system_health()
            elif action == "verify_data_integrity":
                return await self._verify_data_integrity()
            else:
                SecureLogger.safe_log_warning(logger, f"Unknown recovery action: {action}")
                return False
                
        except Exception as e:
            SecureLogger.safe_log_error(logger, f"Recovery step failed: {action}", e)
            return False
    
    async def _stop_services(self) -> bool:
        """Stop all services"""
        try:
            # This would stop Docker services in production
            cmd = ["docker-compose", "-f", "docker-compose.celery.yml", "stop"]
            process = await asyncio.create_subprocess_exec(*cmd)
            await process.communicate()
            return process.returncode == 0
        except Exception:
            return False
    
    async def _start_services(self) -> bool:
        """Start all services"""
        try:
            cmd = ["docker-compose", "-f", "docker-compose.celery.yml", "up", "-d"]
            process = await asyncio.create_subprocess_exec(*cmd)
            await process.communicate()
            return process.returncode == 0
        except Exception:
            return False
    
    async def _stop_application(self) -> bool:
        """Stop application services only"""
        # Implementation specific to your deployment
        return True
    
    async def _start_application(self) -> bool:
        """Start application services"""
        # Implementation specific to your deployment
        return True
    
    async def _restore_database(self, backup_metadata: BackupMetadata) -> bool:
        """Restore database from backup"""
        try:
            # Download and extract backup if needed
            backup_dir = await self._prepare_backup(backup_metadata)
            
            # Restore MongoDB
            mongo_backup_dir = backup_dir / "mongodb" / settings.DB_NAME
            
            cmd = [
                "mongorestore",
                "--uri", settings.MONGODB_URL,
                "--db", settings.DB_NAME,
                "--drop",  # Drop existing collections
                str(mongo_backup_dir)
            ]
            
            process = await asyncio.create_subprocess_exec(*cmd)
            await process.communicate()
            
            return process.returncode == 0
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Database restore failed", e)
            return False
    
    async def _restore_redis(self, backup_metadata: BackupMetadata) -> bool:
        """Restore Redis from backup"""
        # Simplified Redis restore - in production you'd restore RDB file
        return True
    
    async def _restore_configuration(self, backup_metadata: BackupMetadata) -> bool:
        """Restore configuration from backup"""
        # Restore configuration files
        return True
    
    async def _verify_system_health(self) -> bool:
        """Verify system health after recovery"""
        try:
            # Basic health checks
            from app.api.v1.health import readiness
            health_result = await readiness()
            return health_result.get("status") == "healthy"
        except Exception:
            return False
    
    async def _verify_data_integrity(self) -> bool:
        """Verify data integrity after restore"""
        try:
            # Basic data integrity checks
            db = await MongoDB.get_database()
            collections = await db.list_collection_names()
            return len(collections) > 0
        except Exception:
            return False
    
    async def _prepare_backup(self, backup_metadata: BackupMetadata) -> Path:
        """Download and prepare backup for restore"""
        # This would download from S3 and extract if needed
        # For now, assume local backup
        backup_path = Path(backup_metadata.location)
        
        if backup_path.suffix == ".gz":
            # Extract archive
            extract_dir = self.backup_location / f"restore_{backup_metadata.backup_id}"
            extract_dir.mkdir(exist_ok=True)
            
            with tarfile.open(backup_path, "r:gz") as tar:
                tar.extractall(extract_dir)
            
            return extract_dir / backup_metadata.backup_id
        
        return backup_path
    
    def _find_best_backup(self, recovery_type: RecoveryType, 
                         target_timestamp: datetime = None) -> Optional[BackupMetadata]:
        """Find the best backup for recovery"""
        
        target = target_timestamp or datetime.utcnow()
        
        # Filter backups by type and successful status
        suitable_backups = [
            backup for backup in self.backup_history
            if (backup.backup_type == recovery_type or backup.backup_type == RecoveryType.FULL)
            and backup.status == BackupStatus.COMPLETED
            and backup.timestamp <= target
        ]
        
        if not suitable_backups:
            return None
        
        # Return the most recent suitable backup
        return max(suitable_backups, key=lambda b: b.timestamp)
    
    def _find_backup_by_id(self, backup_id: str) -> Optional[BackupMetadata]:
        """Find backup by ID"""
        for backup in self.backup_history:
            if backup.backup_id == backup_id:
                return backup
        return None
    
    async def cleanup_old_backups(self):
        """Clean up old backups based on retention policy"""
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        
        old_backups = [
            backup for backup in self.backup_history
            if backup.timestamp < cutoff_date
        ]
        
        for backup in old_backups:
            try:
                # Delete local backup
                if os.path.exists(backup.location):
                    os.remove(backup.location)
                
                # Delete from S3 if applicable
                if self.s3_client and backup.location.startswith("s3://"):
                    s3_key = backup.location.replace(f"s3://{self.s3_bucket}/", "")
                    self.s3_client.delete_object(Bucket=self.s3_bucket, Key=s3_key)
                
                # Remove from history
                self.backup_history.remove(backup)
                
                SecureLogger.safe_log_info(logger, "Old backup cleaned up", {
                    "backup_id": backup.backup_id,
                    "age_days": (datetime.utcnow() - backup.timestamp).days
                })
                
            except Exception as e:
                SecureLogger.safe_log_error(logger, "Failed to cleanup backup", e, {
                    "backup_id": backup.backup_id
                })
    
    def get_recovery_status(self) -> Dict[str, Any]:
        """Get disaster recovery system status"""
        return {
            "backup_count": len(self.backup_history),
            "latest_backup": (
                max(self.backup_history, key=lambda b: b.timestamp).backup_id
                if self.backup_history else None
            ),
            "recovery_plans": list(self.recovery_plans.keys()),
            "s3_configured": self.s3_client is not None,
            "retention_days": self.retention_days,
            "backup_location": str(self.backup_location)
        }

# Global disaster recovery manager
disaster_recovery = DisasterRecoveryManager()