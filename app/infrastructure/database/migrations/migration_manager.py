import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from abc import ABC, abstractmethod
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.infrastructure.database.mongodb import MongoDB
from app.utils.secure_logging import SecureLogger

logger = logging.getLogger(__name__)

class Migration(ABC):
    """Base migration class"""
    
    def __init__(self, version: str, description: str):
        self.version = version
        self.description = description
        self.timestamp = datetime.utcnow()
    
    @abstractmethod
    async def up(self, db: AsyncIOMotorDatabase) -> None:
        """Apply migration"""
        pass
    
    @abstractmethod
    async def down(self, db: AsyncIOMotorDatabase) -> None:
        """Rollback migration"""
        pass
    
    async def validate(self, db: AsyncIOMotorDatabase) -> bool:
        """Validate migration was applied correctly"""
        return True

class MigrationManager:
    """Manages database schema migrations"""
    
    MIGRATION_COLLECTION = "_migrations"
    
    def __init__(self):
        self.migrations: List[Migration] = []
    
    def register_migration(self, migration: Migration):
        """Register a migration"""
        self.migrations.append(migration)
        # Sort by version to ensure order
        self.migrations.sort(key=lambda m: m.version)
    
    async def get_applied_migrations(self, db: AsyncIOMotorDatabase) -> List[str]:
        """Get list of applied migration versions"""
        try:
            cursor = db[self.MIGRATION_COLLECTION].find({}, {"version": 1})
            migrations = await cursor.to_list(length=None)
            return [m["version"] for m in migrations]
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to get applied migrations", e)
            return []
    
    async def mark_migration_applied(self, db: AsyncIOMotorDatabase, migration: Migration):
        """Mark migration as applied"""
        migration_doc = {
            "version": migration.version,
            "description": migration.description,
            "applied_at": datetime.utcnow(),
            "checksum": self._calculate_checksum(migration)
        }
        
        await db[self.MIGRATION_COLLECTION].insert_one(migration_doc)
        
        SecureLogger.safe_log_info(logger, "Migration applied", {
            "version": migration.version,
            "description": migration.description
        })
    
    async def mark_migration_reverted(self, db: AsyncIOMotorDatabase, version: str):
        """Mark migration as reverted"""
        await db[self.MIGRATION_COLLECTION].delete_one({"version": version})
        
        SecureLogger.safe_log_info(logger, "Migration reverted", {
            "version": version
        })
    
    async def migrate_up(self, target_version: Optional[str] = None) -> Dict[str, Any]:
        """Apply migrations up to target version"""
        db = await MongoDB.get_database()
        applied_migrations = await self.get_applied_migrations(db)
        
        migrations_to_apply = []
        for migration in self.migrations:
            if migration.version not in applied_migrations:
                migrations_to_apply.append(migration)
                if target_version and migration.version == target_version:
                    break
        
        results = {
            "success": True,
            "applied_migrations": [],
            "errors": []
        }
        
        for migration in migrations_to_apply:
            try:
                SecureLogger.safe_log_info(logger, "Applying migration", {
                    "version": migration.version,
                    "description": migration.description
                })
                
                # Apply migration
                await migration.up(db)
                
                # Validate
                if not await migration.validate(db):
                    raise Exception(f"Migration validation failed: {migration.version}")
                
                # Mark as applied
                await self.mark_migration_applied(db, migration)
                
                results["applied_migrations"].append({
                    "version": migration.version,
                    "description": migration.description,
                    "status": "success"
                })
                
            except Exception as e:
                error_msg = f"Failed to apply migration {migration.version}: {str(e)}"
                SecureLogger.safe_log_error(logger, error_msg, e)
                
                results["success"] = False
                results["errors"].append({
                    "version": migration.version,
                    "error": error_msg
                })
                break  # Stop on first error
        
        return results
    
    async def migrate_down(self, target_version: str) -> Dict[str, Any]:
        """Rollback migrations to target version"""
        db = await MongoDB.get_database()
        applied_migrations = await self.get_applied_migrations(db)
        
        # Find migrations to rollback (in reverse order)
        migrations_to_rollback = []
        for migration in reversed(self.migrations):
            if migration.version in applied_migrations:
                migrations_to_rollback.append(migration)
                if migration.version == target_version:
                    break
        
        results = {
            "success": True,
            "reverted_migrations": [],
            "errors": []
        }
        
        for migration in migrations_to_rollback:
            try:
                SecureLogger.safe_log_info(logger, "Rolling back migration", {
                    "version": migration.version,
                    "description": migration.description
                })
                
                # Rollback migration
                await migration.down(db)
                
                # Mark as reverted
                await self.mark_migration_reverted(db, migration.version)
                
                results["reverted_migrations"].append({
                    "version": migration.version,
                    "description": migration.description,
                    "status": "success"
                })
                
            except Exception as e:
                error_msg = f"Failed to rollback migration {migration.version}: {str(e)}"
                SecureLogger.safe_log_error(logger, error_msg, e)
                
                results["success"] = False
                results["errors"].append({
                    "version": migration.version,
                    "error": error_msg
                })
                break  # Stop on first error
        
        return results
    
    async def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status"""
        db = await MongoDB.get_database()
        applied_migrations = await self.get_applied_migrations(db)
        
        migration_status = []
        for migration in self.migrations:
            status = {
                "version": migration.version,
                "description": migration.description,
                "applied": migration.version in applied_migrations
            }
            
            if migration.version in applied_migrations:
                # Get application details
                migration_doc = await db[self.MIGRATION_COLLECTION].find_one(
                    {"version": migration.version}
                )
                if migration_doc:
                    status["applied_at"] = migration_doc.get("applied_at")
            
            migration_status.append(status)
        
        pending_count = len([m for m in migration_status if not m["applied"]])
        
        return {
            "total_migrations": len(self.migrations),
            "applied_migrations": len(applied_migrations),
            "pending_migrations": pending_count,
            "migrations": migration_status
        }
    
    def _calculate_checksum(self, migration: Migration) -> str:
        """Calculate migration checksum for integrity"""
        import hashlib
        content = f"{migration.version}{migration.description}"
        return hashlib.sha256(content.encode()).hexdigest()

# Global migration manager
migration_manager = MigrationManager()