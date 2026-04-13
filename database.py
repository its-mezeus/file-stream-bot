#!/usr/bin/env python3
"""
MongoDB Database for File Stream Bot
By Zeus ⚡
"""
from pymongo import MongoClient
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class StreamBotDB:
    def __init__(self, mongo_url: str = None):
        """Initialize MongoDB connection"""
        # Use environment variable or default
        if mongo_url is None:
            import os
            from dotenv import load_dotenv
            load_dotenv()
            mongo_url = os.getenv("DATABASE_URL", "mongodb://localhost:27017/")
        try:
            self.client = MongoClient(mongo_url)
            self.db = self.client['filestream_bot']
            
            # Collections
            self.users = self.db['users']
            self.force_channels = self.db['force_channels']
            
            # Create indexes for better performance
            self.users.create_index("user_id", unique=True)
            self.force_channels.create_index("channel_id", unique=True)
            
            logger.info("✅ MongoDB connected successfully!")
            
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise
    
    # ==================== USER METHODS ====================
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None):
        """Add new user or update existing"""
        try:
            user_data = {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "first_seen": datetime.now(),
                "last_active": datetime.now(),
                "files_uploaded": 0,
                "is_banned": False,
                "ban_reason": None,
                "ban_date": None
            }
            
            result = self.users.find_one({"user_id": user_id})
            if not result:
                self.users.insert_one(user_data)
            else:
                self.users.update_one(
                    {"user_id": user_id},
                    {"$set": {"last_active": datetime.now(), "username": username, "first_name": first_name}}
                )
            return True
        except Exception as e:
            logger.error(f"Error adding user {user_id}: {e}")
            return False
    
    def update_user_activity(self, user_id: int):
        """Update user's last active time"""
        try:
            self.users.update_one(
                {"user_id": user_id},
                {"$set": {"last_active": datetime.now()}}
            )
        except Exception as e:
            logger.error(f"Error updating user activity: {e}")
    
    def increment_user_files(self, user_id: int):
        """Increment user's file upload count"""
        try:
            self.users.update_one(
                {"user_id": user_id},
                {"$inc": {"files_uploaded": 1}}
            )
        except Exception as e:
            logger.error(f"Error incrementing files: {e}")
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user data"""
        try:
            return self.users.find_one({"user_id": user_id})
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None
    
    def is_banned(self, user_id: int) -> bool:
        """Check if user is banned"""
        try:
            user = self.users.find_one({"user_id": user_id}, {"is_banned": 1})
            return user.get("is_banned", False) if user else False
        except Exception as e:
            logger.error(f"Error checking ban status: {e}")
            return False
    
    def ban_user(self, user_id: int, reason: str = "No reason provided", admin_id: int = None):
        """Ban a user"""
        try:
            self.users.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "is_banned": True,
                        "ban_reason": reason,
                        "ban_date": datetime.now(),
                        "banned_by": admin_id
                    }
                }
            )
            logger.info(f"✅ User {user_id} banned: {reason}")
            return True
        except Exception as e:
            logger.error(f"Error banning user: {e}")
            return False
    
    def unban_user(self, user_id: int):
        """Unban a user"""
        try:
            self.users.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "is_banned": False,
                        "ban_reason": None,
                        "ban_date": None,
                        "banned_by": None
                    }
                }
            )
            logger.info(f"✅ User {user_id} unbanned")
            return True
        except Exception as e:
            logger.error(f"Error unbanning user: {e}")
            return False
    
    def get_banned_users(self) -> List[Dict]:
        """Get all banned users"""
        try:
            return list(self.users.find({"is_banned": True}))
        except Exception as e:
            logger.error(f"Error getting banned users: {e}")
            return []
    
    def get_all_users(self, skip: int = 0, limit: int = 50) -> List[Dict]:
        """Get all users with pagination"""
        try:
            return list(self.users.find().skip(skip).limit(limit).sort("first_seen", -1))
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return []
    
    def get_total_users(self) -> int:
        """Get total user count"""
        try:
            return self.users.count_documents({})
        except Exception as e:
            logger.error(f"Error getting user count: {e}")
            return 0
    
    # ==================== FORCE CHANNEL METHODS ====================
    
    def add_force_channel(self, channel_id: int, channel_username: str = None, 
                         channel_title: str = None, added_by: int = None):
        """Add force join channel"""
        try:
            channel_data = {
                "channel_id": channel_id,
                "channel_username": channel_username,
                "channel_title": channel_title,
                "added_by": added_by,
                "date_added": datetime.now(),
                "is_active": True
            }
            
            self.force_channels.update_one(
                {"channel_id": channel_id},
                {"$set": channel_data},
                upsert=True
            )
            logger.info(f"✅ Force channel added: {channel_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding force channel: {e}")
            return False
    
    def remove_force_channel(self, channel_id: int):
        """Remove force join channel"""
        try:
            result = self.force_channels.delete_one({"channel_id": channel_id})
            if result.deleted_count > 0:
                logger.info(f"✅ Force channel removed: {channel_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing force channel: {e}")
            return False
    
    def get_force_channels(self) -> List[Dict]:
        """Get all active force join channels"""
        try:
            return list(self.force_channels.find({"is_active": True}))
        except Exception as e:
            logger.error(f"Error getting force channels: {e}")
            return []
    
    def get_force_channel_ids(self) -> List[int]:
        """Get list of force channel IDs only"""
        try:
            channels = self.force_channels.find({"is_active": True}, {"channel_id": 1})
            return [ch["channel_id"] for ch in channels]
        except Exception as e:
            logger.error(f"Error getting channel IDs: {e}")
            return []
    
    def toggle_force_channel(self, channel_id: int, active: bool):
        """Enable/disable force channel without deleting"""
        try:
            self.force_channels.update_one(
                {"channel_id": channel_id},
                {"$set": {"is_active": active}}
            )
            return True
        except Exception as e:
            logger.error(f"Error toggling channel: {e}")
            return False
    
    # ==================== STATS METHODS ====================
    
    def get_stats(self) -> Dict:
        """Get bot statistics"""
        try:
            total_users = self.users.count_documents({})
            banned_users = self.users.count_documents({"is_banned": True})
            active_channels = self.force_channels.count_documents({"is_active": True})
            
            # Total files uploaded
            pipeline = [
                {"$group": {"_id": None, "total": {"$sum": "$files_uploaded"}}}
            ]
            files_result = list(self.users.aggregate(pipeline))
            total_files = files_result[0]["total"] if files_result else 0
            
            return {
                "total_users": total_users,
                "banned_users": banned_users,
                "active_users": total_users - banned_users,
                "total_files": total_files,
                "force_channels": active_channels
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
    
    def get_top_uploaders(self, limit: int = 10) -> List[Dict]:
        """Get top file uploaders"""
        try:
            return list(
                self.users.find({"files_uploaded": {"$gt": 0}})
                .sort("files_uploaded", -1)
                .limit(limit)
            )
        except Exception as e:
            logger.error(f"Error getting top uploaders: {e}")
            return []
    
    # ==================== UTILITY METHODS ====================
    
    def close(self):
        """Close MongoDB connection"""
        try:
            self.client.close()
            logger.info("MongoDB connection closed")
        except Exception as e:
            logger.error(f"Error closing connection: {e}")


# Test connection
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("🧪 Testing MongoDB Database...")
    db = StreamBotDB()
    
    # Test user operations
    print("\n📝 Testing user operations...")
    db.add_user(123456, "test_user", "Test User")
    user = db.get_user(123456)
    print(f"✅ User added: {user}")
    
    # Test ban
    db.ban_user(123456, "Testing ban")
    print(f"✅ User banned: {db.is_banned(123456)}")
    
    db.unban_user(123456)
    print(f"✅ User unbanned: {db.is_banned(123456)}")
    
    # Test force channels
    print("\n📝 Testing force channels...")
    db.add_force_channel(-1001234567890, "@testchannel", "Test Channel")
    channels = db.get_force_channels()
    print(f"✅ Force channels: {len(channels)}")
    
    # Test stats
    print("\n📊 Testing stats...")
    stats = db.get_stats()
    print(f"✅ Stats: {stats}")
    
    db.close()
    print("\n✅ All tests passed!")
