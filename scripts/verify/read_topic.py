import sys
import json
from kafka import KafkaConsumer
from urllib.error import URLError

def main():
    if len(sys.argv) < 2:
        print("Usage: python read_topic.py <topic_name>")
        sys.exit(1)
        
    topic_name = sys.argv[1]
    group_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"Reading messages from topic: {topic_name} (Group: {group_id or 'None'}). Press Ctrl+C to stop...")
    
    try:
        consumer = KafkaConsumer(
            topic_name,
            bootstrap_servers='127.0.0.1:9092',
            group_id=group_id,
            auto_offset_reset='earliest',
            enable_auto_commit=True if group_id else False,
            value_deserializer=lambda x: str(x, 'utf-8', errors='replace'),
            api_version=(3,6,0)
        )
        
        count = 0
        for message in consumer:
            count += 1
            print(f"[{count}] Offset {message.offset}: {message.value[:200]}...")
            
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"Error reading from topic: {e}")

if __name__ == "__main__":
    main()
