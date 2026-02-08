import asyncio
from collections import defaultdict, deque
import logging
import json
import time

logger = logging.getLogger(__name__)

class MockRedisPubSub:
    """Mock Redis PubSub object."""
    def __init__(self, channels, message_queue):
        self.channels = channels
        self.message_queue = message_queue
        self.active = True
        
    def get_message(self, ignore_subscribe_messages=False, timeout=0):
        if not self.active or not self.message_queue:
            return None
            
        try:
            # Non-blocking pop from the shared queue for this subscriber
            # In a real Redis, this would block or poll.
            # Here, we assume the Backtester pushes messages to this queue 
            # and the Strategy pops them.
            if len(self.message_queue) > 0:
                return self.message_queue.popleft()
        except Exception:
            return None
        return None

    def close(self):
        self.active = False

    def psubscribe(self, *args):
        # Register the patterns as keys in the shared _pubsub_subs dict
        # The MockRedis class uses these keys to route messages in publish()
        self.subscribe(*args) # Reuse subscribe since we hacked publish to handle * patterns in keys

class MockRedis:
    """
    High-Fidelity Mock for redis.Redis.
    Simulates Pub/Sub for backtesting without a real Redis server.
    """
    def __init__(self, host='localhost', port=6379, decode_responses=False):
        self.host = host
        self.port = port
        self.decode_responses = decode_responses
        
        # Data Store (Key-Value)
        self._data = {}
        
        # PubSub Channels
        # channel_name -> list of subscriber_queues
        self._pubsub_subs = defaultdict(list)
        
        # For capturing signals for the backtester to inspect
        self._published_messages = defaultdict(list)

    def ping(self):
        return True
        
    def publish(self, channel, message):
        """
        Publish a message to a channel.
        - Delivers to any active subscribers (MockPubSubs).
        - Records the message for the Backtester to inspect (e.g. Trade Signals).
        """
        # 1. Record for inspection
        self._published_messages[channel].append({
            'channel': channel,
            'data': message,
            'timestamp': time.time()
        })
        
        # 2. Deliver to subscribers
        # Handle pattern matching? converting patterns to list
        # For now, exact match for simplicity, or simple * wildcard
        
        # Direct match
        if channel in self._pubsub_subs:
            for queue in self._pubsub_subs[channel]:
                queue.append({
                    'type': 'message',
                    'pattern': None,
                    'channel': channel,
                    'data': message
                })
        
        # HACK for psubscribe 'market_data_*'
        # If we publish to 'market_data_BTC-USD', we must deliver to 'market_data_*' subs
        for sub_pattern, queues in self._pubsub_subs.items():
            if sub_pattern.endswith('*'):
                prefix = sub_pattern[:-1]
                if channel.startswith(prefix):
                    for queue in queues:
                        queue.append({
                            'type': 'pmessage',
                            'pattern': sub_pattern,
                            'channel': channel,
                            'data': message
                        })
        return 1 # Number of clients received

    def pubsub(self, **kwargs):
        """Return a PubSub object that can subscribe to channels."""
        # Create a queue for this specific pubsub instance
        q = deque()
        
        # We need to capture the 'subscribe' calls on this object to register the queue
        # So we return a wrapped object or modify the standard one.
        # Let's use a custom class.
        
        mock_ps = MockRedisPubSub(self._pubsub_subs, q)
        
        # Monkey patch subscribe/psubscribe to register this queue
        original_psubscribe = mock_ps.psubscribe
        
        def start_subscribe(*args):
             for channel in args:
                 self._pubsub_subs[channel].append(q)
        
        mock_ps.subscribe = start_subscribe
        mock_ps.psubscribe = start_subscribe # treat both same for routing logic above
        
        return mock_ps

    def get(self, key):
        return self._data.get(key)
        
    def set(self, key, value):
        self._data[key] = value
        return True

    def close(self):
        pass

    # Helper for Backtester to inject messages "from the outside"
    def inject_message(self, channel, message):
        """
        Used by the EventDrivenBacktester to push Market Data into the system.
        """
        return self.publish(channel, message)

    # Helper for Backtester to read signals "output by the strategy"
    def get_published_messages(self, channel):
        """
        Retrieve and clear messages published to a specific channel.
        Used by Backtester to capture Trade Signals.
        """
        msgs = self._published_messages.get(channel, [])
        # Clear after read? Or keep?
        # Usually backtest loop reads active signals.
        self._published_messages[channel] = []
        return msgs
