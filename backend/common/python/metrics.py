class MockMetric:
    def labels(self, *args, **kwargs):
        return self
    
    def set(self, value):
        pass
        
    def inc(self, amount=1):
        pass
        
    def observe(self, value):
        pass

# Instantiate mock metrics
SERVICE_STATUS = MockMetric()
REALIZED_PNL = MockMetric()
UNREALIZED_PNL = MockMetric()
CURRENT_POSITION = MockMetric()
PORTFOLIO_VALUE = MockMetric()
INDICATOR_VALUE = MockMetric()
SIGNALS_GENERATED = MockMetric()
SIGNAL_LATENCY = MockMetric()
TICKS_RECEIVED = MockMetric() 
MARKET_PRICE = MockMetric() # Added missing metric

def start_metrics_server(port):
    pass

def record_error(source, error_code):
    print(f"METRIC ERROR: {source} - {error_code}")
