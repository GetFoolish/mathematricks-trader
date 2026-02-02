#!/usr/bin/env python3
"""
Add SystemHealth Widget to Main-One Dashboard

This script adds a SystemHealth widget to the Main-One dashboard.
"""
import pymongo
from datetime import datetime

# MongoDB connection (use localhost:27018 when running from host machine)
# Note: directConnection=true to avoid replica set hostname resolution issues
MONGODB_URI = 'mongodb://localhost:27018/?directConnection=true'
client = pymongo.MongoClient(MONGODB_URI)
db = client['mathematricks_trading']

# Find Main-One dashboard
dashboard = db.dashboards.find_one({"name": "Main-One"})

if not dashboard:
    print("❌ Main-One dashboard not found!")
    print("Creating Main-One dashboard...")
    
    dashboard_id = f"dashboard-{int(datetime.utcnow().timestamp() * 1000)}-mainone"
    db.dashboards.insert_one({
        "dashboard_id": dashboard_id,
        "name": "Main-One",
        "created_by": "admin",
        "widgets": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    })
    dashboard = db.dashboards.find_one({"dashboard_id": dashboard_id})
    print(f"✅ Created Main-One dashboard: {dashboard_id}")

# Check if SystemHealth widget already exists
existing_widgets = dashboard.get("widgets", [])
has_system_health = any(w.get("widget_type") == "SystemHealth" for w in existing_widgets)

if has_system_health:
    print("⚠️  SystemHealth widget already exists in Main-One dashboard")
else:
    # Add SystemHealth widget
    widget_id = f"widget-{int(datetime.utcnow().timestamp() * 1000)}-systemhealth"
    
    new_widget = {
        "widget_id": widget_id,
        "widget_type": "SystemHealth",
        "position": {
            "x": 0,
            "y": 0,
            "w": 6,
            "h": 4
        },
        "config": {}
    }
    
    db.dashboards.update_one(
        {"dashboard_id": dashboard["dashboard_id"]},
        {
            "$push": {"widgets": new_widget},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    print(f"✅ Added SystemHealth widget to Main-One dashboard")
    print(f"   Widget ID: {widget_id}")
    print(f"   Position: (0, 0), Size: 6x4")

# Show current widgets
updated_dashboard = db.dashboards.find_one({"dashboard_id": dashboard["dashboard_id"]})
print(f"\nMain-One dashboard now has {len(updated_dashboard['widgets'])} widgets:")
for widget in updated_dashboard["widgets"]:
    print(f"  - {widget['widget_type']} (ID: {widget['widget_id']})")

client.close()
print("\n✅ Done!")
