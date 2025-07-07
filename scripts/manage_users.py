#!/usr/bin/env python3
"""
User Management Script for WhatsApp Bot Authorization System

This script allows administrators to manage authorized users for the bot.
It supports both WhatsApp (phone numbers) and Telegram (chat IDs) users.

Usage:
    python scripts/manage_users.py add-user --platform whatsapp --identifier 5511999999999 --name "John Doe"
    python scripts/manage_users.py list-users --platform whatsapp
    python scripts/manage_users.py suspend-user --platform telegram --identifier 123456789
    python scripts/manage_users.py stats
"""

import asyncio
import sys
import argparse
from datetime import datetime, timedelta
from typing import Optional
import json
import csv
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.domain.entities.authorized_user import AuthorizedUser, Platform, UserRole, UserStatus
from app.infrastructure.database.repositories.authorized_user import AuthorizedUserRepository
from app.infrastructure.database.mongodb import MongoDB


class UserManager:
    """User management operations"""
    
    def __init__(self):
        self.repo = AuthorizedUserRepository()
    
    async def add_user(
        self,
        platform: str,
        identifier: str,
        name: str,
        role: str = "user",
        daily_limit: int = 50,
        monthly_limit: int = 1000,
        expires_days: Optional[int] = None,
        features: Optional[list] = None
    ):
        """Add a new authorized user"""
        try:
            # Validate platform
            if platform not in ["whatsapp", "telegram"]:
                print(f"❌ Invalid platform: {platform}. Use 'whatsapp' or 'telegram'")
                return False
            
            # Validate role
            if role not in ["admin", "user", "limited"]:
                print(f"❌ Invalid role: {role}. Use 'admin', 'user', or 'limited'")
                return False
            
            platform_enum = Platform.WHATSAPP if platform == "whatsapp" else Platform.TELEGRAM
            role_enum = UserRole.ADMIN if role == "admin" else (UserRole.LIMITED if role == "limited" else UserRole.USER)
            
            # Set default features based on role
            if not features:
                if role == "admin":
                    features = ["audio_analysis", "text_commands", "admin_commands", "user_management"]
                elif role == "limited":
                    features = ["text_commands"]
                else:
                    features = ["audio_analysis", "text_commands"]
            
            # Check if user already exists
            existing_user = await self.repo.get_user(platform_enum, identifier)
            if existing_user:
                print(f"❌ User already exists: {existing_user.unified_id}")
                print(f"   Name: {existing_user.display_name}")
                print(f"   Status: {existing_user.status}")
                return False
            
            # Create new user
            user = AuthorizedUser(
                platform_identifier=identifier,
                platform=platform_enum,
                display_name=name,
                role=role_enum,
                status=UserStatus.ACTIVE,
                daily_limit=daily_limit,
                monthly_limit=monthly_limit,
                allowed_features=features
            )
            
            # Set expiration if specified
            if expires_days:
                user.set_expiration(expires_days)
            
            # Save user
            await self.repo.save_user(user)
            
            print(f"✅ User added successfully!")
            print(f"   Unified ID: {user.unified_id}")
            print(f"   Name: {user.display_name}")
            print(f"   Role: {user.role}")
            print(f"   Daily Limit: {user.daily_limit}")
            print(f"   Monthly Limit: {user.monthly_limit}")
            print(f"   Features: {', '.join(user.allowed_features)}")
            if user.expires_at:
                print(f"   Expires: {user.expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error adding user: {str(e)}")
            return False
    
    async def list_users(self, platform: Optional[str] = None, status: Optional[str] = None):
        """List all authorized users"""
        try:
            platform_enum = None
            if platform:
                if platform not in ["whatsapp", "telegram"]:
                    print(f"❌ Invalid platform: {platform}")
                    return
                platform_enum = Platform.WHATSAPP if platform == "whatsapp" else Platform.TELEGRAM
            
            status_enum = None
            if status:
                if status not in ["active", "suspended", "expired"]:
                    print(f"❌ Invalid status: {status}")
                    return
                status_enum = UserStatus.ACTIVE if status == "active" else (
                    UserStatus.SUSPENDED if status == "suspended" else UserStatus.EXPIRED
                )
            
            users = await self.repo.list_users(platform_enum, status_enum)
            
            if not users:
                print("📝 No users found")
                return
            
            print(f"📋 Found {len(users)} user(s):")
            print()
            
            for user in users:
                status_emoji = "✅" if user.status == UserStatus.ACTIVE else ("⛔" if user.status == UserStatus.SUSPENDED else "⏰")
                platform_emoji = "📱" if user.platform == Platform.WHATSAPP else "💬"
                
                print(f"{status_emoji} {platform_emoji} {user.unified_id}")
                print(f"   Name: {user.display_name}")
                print(f"   Role: {user.role}")
                print(f"   Status: {user.status}")
                print(f"   Usage: {user.usage_stats.daily_count}/{user.daily_limit} daily, {user.usage_stats.monthly_count}/{user.monthly_limit} monthly")
                print(f"   Total Messages: {user.usage_stats.total_messages}")
                if user.last_used_at:
                    print(f"   Last Used: {user.last_used_at.strftime('%Y-%m-%d %H:%M:%S')}")
                if user.expires_at:
                    print(f"   Expires: {user.expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print()
                
        except Exception as e:
            print(f"❌ Error listing users: {str(e)}")
    
    async def suspend_user(self, platform: str, identifier: str, reason: Optional[str] = None):
        """Suspend a user"""
        try:
            platform_enum = Platform.WHATSAPP if platform == "whatsapp" else Platform.TELEGRAM
            user = await self.repo.get_user(platform_enum, identifier)
            
            if not user:
                print(f"❌ User not found: {platform}:{identifier}")
                return False
            
            user.suspend(reason)
            await self.repo.save_user(user)
            
            print(f"✅ User suspended: {user.unified_id}")
            print(f"   Name: {user.display_name}")
            if reason:
                print(f"   Reason: {reason}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error suspending user: {str(e)}")
            return False
    
    async def activate_user(self, platform: str, identifier: str):
        """Activate a user"""
        try:
            platform_enum = Platform.WHATSAPP if platform == "whatsapp" else Platform.TELEGRAM
            user = await self.repo.get_user(platform_enum, identifier)
            
            if not user:
                print(f"❌ User not found: {platform}:{identifier}")
                return False
            
            user.activate()
            await self.repo.save_user(user)
            
            print(f"✅ User activated: {user.unified_id}")
            print(f"   Name: {user.display_name}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error activating user: {str(e)}")
            return False
    
    async def delete_user(self, platform: str, identifier: str):
        """Delete a user"""
        try:
            platform_enum = Platform.WHATSAPP if platform == "whatsapp" else Platform.TELEGRAM
            user = await self.repo.get_user(platform_enum, identifier)
            
            if not user:
                print(f"❌ User not found: {platform}:{identifier}")
                return False
            
            # Confirm deletion
            print(f"⚠️  Are you sure you want to delete user: {user.unified_id} ({user.display_name})?")
            response = input("Type 'yes' to confirm: ")
            
            if response.lower() != 'yes':
                print("❌ Deletion cancelled")
                return False
            
            await self.repo.delete_user(platform_enum, identifier)
            
            print(f"✅ User deleted: {user.unified_id}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error deleting user: {str(e)}")
            return False
    
    async def update_limits(self, platform: str, identifier: str, daily_limit: Optional[int] = None, monthly_limit: Optional[int] = None):
        """Update user limits"""
        try:
            platform_enum = Platform.WHATSAPP if platform == "whatsapp" else Platform.TELEGRAM
            user = await self.repo.get_user(platform_enum, identifier)
            
            if not user:
                print(f"❌ User not found: {platform}:{identifier}")
                return False
            
            if daily_limit is not None:
                user.daily_limit = daily_limit
            if monthly_limit is not None:
                user.monthly_limit = monthly_limit
            
            await self.repo.save_user(user)
            
            print(f"✅ Limits updated for user: {user.unified_id}")
            print(f"   Daily Limit: {user.daily_limit}")
            print(f"   Monthly Limit: {user.monthly_limit}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error updating limits: {str(e)}")
            return False
    
    async def reset_usage(self, platform: str, identifier: str):
        """Reset user usage counters"""
        try:
            platform_enum = Platform.WHATSAPP if platform == "whatsapp" else Platform.TELEGRAM
            user = await self.repo.get_user(platform_enum, identifier)
            
            if not user:
                print(f"❌ User not found: {platform}:{identifier}")
                return False
            
            user.usage_stats.daily_count = 0
            user.usage_stats.monthly_count = 0
            user.usage_stats.last_reset_date = datetime.now()
            
            await self.repo.save_user(user)
            
            print(f"✅ Usage reset for user: {user.unified_id}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error resetting usage: {str(e)}")
            return False
    
    async def get_stats(self):
        """Get platform statistics"""
        try:
            stats = await self.repo.get_usage_stats()
            total_users = await self.repo.count_users()
            active_users = await self.repo.count_users(status=UserStatus.ACTIVE)
            
            print("📊 Platform Statistics:")
            print(f"   Total Users: {total_users}")
            print(f"   Active Users: {active_users}")
            print()
            
            for platform, data in stats.items():
                emoji = "📱" if platform == "whatsapp" else "💬"
                print(f"{emoji} {platform.title()}:")
                print(f"   Total Users: {data['total_users']}")
                print(f"   Active Users: {data['active_users']}")
                print(f"   Total Messages: {data['total_messages']}")
                print(f"   Daily Messages: {data['daily_messages']}")
                print(f"   Monthly Messages: {data['monthly_messages']}")
                print()
                
        except Exception as e:
            print(f"❌ Error getting stats: {str(e)}")
    
    async def import_from_csv(self, csv_file: str):
        """Import users from CSV file"""
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                success_count = 0
                error_count = 0
                
                for row in reader:
                    try:
                        result = await self.add_user(
                            platform=row.get('platform', 'whatsapp'),
                            identifier=row['identifier'],
                            name=row['name'],
                            role=row.get('role', 'user'),
                            daily_limit=int(row.get('daily_limit', 50)),
                            monthly_limit=int(row.get('monthly_limit', 1000)),
                            expires_days=int(row['expires_days']) if row.get('expires_days') else None,
                            features=row.get('features', '').split(',') if row.get('features') else None
                        )
                        
                        if result:
                            success_count += 1
                        else:
                            error_count += 1
                            
                    except Exception as e:
                        print(f"❌ Error importing row {row}: {str(e)}")
                        error_count += 1
                
                print(f"📥 Import completed: {success_count} success, {error_count} errors")
                
        except Exception as e:
            print(f"❌ Error importing CSV: {str(e)}")


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="User Management Script for WhatsApp Bot")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Add user command
    add_parser = subparsers.add_parser("add-user", help="Add a new authorized user")
    add_parser.add_argument("--platform", required=True, choices=["whatsapp", "telegram"], help="Platform type")
    add_parser.add_argument("--identifier", required=True, help="Phone number (WhatsApp) or Chat ID (Telegram)")
    add_parser.add_argument("--name", required=True, help="User display name")
    add_parser.add_argument("--role", default="user", choices=["admin", "user", "limited"], help="User role")
    add_parser.add_argument("--daily-limit", type=int, default=50, help="Daily message limit")
    add_parser.add_argument("--monthly-limit", type=int, default=1000, help="Monthly message limit")
    add_parser.add_argument("--expires-days", type=int, help="Expiration in days")
    add_parser.add_argument("--features", help="Comma-separated list of allowed features")
    
    # List users command
    list_parser = subparsers.add_parser("list-users", help="List authorized users")
    list_parser.add_argument("--platform", choices=["whatsapp", "telegram"], help="Filter by platform")
    list_parser.add_argument("--status", choices=["active", "suspended", "expired"], help="Filter by status")
    
    # Suspend user command
    suspend_parser = subparsers.add_parser("suspend-user", help="Suspend a user")
    suspend_parser.add_argument("--platform", required=True, choices=["whatsapp", "telegram"], help="Platform type")
    suspend_parser.add_argument("--identifier", required=True, help="Phone number or Chat ID")
    suspend_parser.add_argument("--reason", help="Suspension reason")
    
    # Activate user command
    activate_parser = subparsers.add_parser("activate-user", help="Activate a user")
    activate_parser.add_argument("--platform", required=True, choices=["whatsapp", "telegram"], help="Platform type")
    activate_parser.add_argument("--identifier", required=True, help="Phone number or Chat ID")
    
    # Delete user command
    delete_parser = subparsers.add_parser("delete-user", help="Delete a user")
    delete_parser.add_argument("--platform", required=True, choices=["whatsapp", "telegram"], help="Platform type")
    delete_parser.add_argument("--identifier", required=True, help="Phone number or Chat ID")
    
    # Update limits command
    limits_parser = subparsers.add_parser("update-limits", help="Update user limits")
    limits_parser.add_argument("--platform", required=True, choices=["whatsapp", "telegram"], help="Platform type")
    limits_parser.add_argument("--identifier", required=True, help="Phone number or Chat ID")
    limits_parser.add_argument("--daily-limit", type=int, help="New daily limit")
    limits_parser.add_argument("--monthly-limit", type=int, help="New monthly limit")
    
    # Reset usage command
    reset_parser = subparsers.add_parser("reset-usage", help="Reset user usage counters")
    reset_parser.add_argument("--platform", required=True, choices=["whatsapp", "telegram"], help="Platform type")
    reset_parser.add_argument("--identifier", required=True, help="Phone number or Chat ID")
    
    # Stats command
    subparsers.add_parser("stats", help="Show platform statistics")
    
    # Import CSV command
    import_parser = subparsers.add_parser("import-csv", help="Import users from CSV file")
    import_parser.add_argument("--file", required=True, help="CSV file path")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize MongoDB connection
    await MongoDB.connect()
    
    manager = UserManager()
    
    try:
        if args.command == "add-user":
            features = args.features.split(',') if args.features else None
            await manager.add_user(
                args.platform, args.identifier, args.name, args.role,
                args.daily_limit, args.monthly_limit, args.expires_days, features
            )
        
        elif args.command == "list-users":
            await manager.list_users(args.platform, args.status)
        
        elif args.command == "suspend-user":
            await manager.suspend_user(args.platform, args.identifier, args.reason)
        
        elif args.command == "activate-user":
            await manager.activate_user(args.platform, args.identifier)
        
        elif args.command == "delete-user":
            await manager.delete_user(args.platform, args.identifier)
        
        elif args.command == "update-limits":
            await manager.update_limits(args.platform, args.identifier, args.daily_limit, args.monthly_limit)
        
        elif args.command == "reset-usage":
            await manager.reset_usage(args.platform, args.identifier)
        
        elif args.command == "stats":
            await manager.get_stats()
        
        elif args.command == "import-csv":
            await manager.import_from_csv(args.file)
            
    finally:
        await MongoDB.disconnect()


if __name__ == "__main__":
    asyncio.run(main())