import os
import time
from google.cloud import pubsub_v1

# Ensure this script runs with correct environment variables
if not os.getenv("PUBSUB_EMULATOR_HOST"):
    print("⚠️  PUBSUB_EMULATOR_HOST not set. Defaulting to localhost:8085")
    os.environ["PUBSUB_EMULATOR_HOST"] = "localhost:8085"

project_id = os.getenv('PUBSUB_PROJECT_ID', 'mathematricks-trader')

print(f"Initializing Pub/Sub for project: {project_id}")
print(f"Emulator Host: {os.environ.get('PUBSUB_EMULATOR_HOST')}")

publisher = pubsub_v1.PublisherClient()
subscriber = pubsub_v1.SubscriberClient()

# Topics to create
topics = [
    'standardized-signals', 
    'trading-orders', 
    'execution-confirmations', 
    'account-updates', 
    'order-commands'
]

# Subscriptions to create: (subscription_name, topic_name, ack_deadline)
subscriptions = [
    ('standardized-signals-sub', 'standardized-signals', 600),
    ('trading-orders-sub', 'trading-orders', 600),
    ('execution-confirmations-sub', 'execution-confirmations', 600),
    ('account-updates-sub', 'account-updates', 600),
    ('order-commands-sub', 'order-commands', 600)
]

def create_resources():
    # Create Topics
    print("\nCreating Topics...")
    for topic_name in topics:
        topic_path = publisher.topic_path(project_id, topic_name)
        try:
            publisher.create_topic(request={"name": topic_path})
            print(f"✅ Created topic: {topic_name}")
        except Exception as e:
            if 'AlreadyExists' in str(e):
                print(f"ℹ️  Topic {topic_name} already exists")
            else:
                print(f"❌ Error creating {topic_name}: {e}")

    # Create Subscriptions
    print("\nCreating Subscriptions...")
    for sub_name, topic_name, ack_deadline in subscriptions:
        topic_path = publisher.topic_path(project_id, topic_name)
        sub_path = subscriber.subscription_path(project_id, sub_name)
        try:
            subscriber.create_subscription(
                request={
                    "name": sub_path,
                    "topic": topic_path,
                    "ack_deadline_seconds": ack_deadline
                }
            )
            print(f"✅ Created subscription: {sub_name}")
        except Exception as e:
            if 'AlreadyExists' in str(e):
                print(f"ℹ️  Subscription {sub_name} already exists")
            else:
                print(f"❌ Error creating {sub_name}: {e}")

if __name__ == "__main__":
    # Wait for emulator to be ready
    print("Waiting for Pub/Sub emulator...")
    time.sleep(5)
    
    try:
        create_resources()
        print("\n✨ Pub/Sub initialization complete!")
    except Exception as e:
        print(f"\n❌ Fatal error during initialization: {e}")
        # Keep container alive briefly to see logs
        time.sleep(5)
        exit(1)
