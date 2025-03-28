import os
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import json
import asyncio
from typing import Dict, Any

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

# Topics
RECIPE_REQUEST_TOPIC = "recipe-requests"
RECIPE_RESPONSE_TOPIC = "recipe-responses"
FAVORITE_RECIPE_TOPIC = "favorite-recipes"

# Producer instance to be initialized in the app startup
producer = None

async def initialize_kafka():
    """Initialize the Kafka producer"""
    global producer
    
    try:
        producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await producer.start()
        print(f"Kafka producer connected to {KAFKA_BOOTSTRAP_SERVERS}")
        return True
    except Exception as e:
        print(f"Failed to connect to Kafka: {e}")
        return False

async def close_kafka():
    """Close the Kafka producer when the app shuts down"""
    if producer:
        await producer.stop()
        print("Kafka producer closed")

async def send_message(topic: str, message: Dict[str, Any], key: str = None):
    """Send a message to a Kafka topic"""
    if not producer:
        logger.warning("Kafka producer not initialized, message not sent")
        return False
    
    try:
        if key:
            # Use the key for partitioning (e.g., user_id)
            key_bytes = key.encode('utf-8')
            await producer.send_and_wait(topic, message, key=key_bytes)
        else:
            await producer.send_and_wait(topic, message)
        return True
    except Exception as e:
        logger.error(f"Error sending message to Kafka: {e}")
        return False

# Consumer helper function
async def create_consumer(topic: str, group_id: str):
    """Create and return a Kafka consumer"""
    try:
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=group_id,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset="earliest"
        )
        await consumer.start()
        return consumer
    except Exception as e:
        print(f"Failed to create Kafka consumer: {e}")
        return None