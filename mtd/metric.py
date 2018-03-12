from enum import Enum


class MetricType(Enum):
    AUTO = 'auto'
    STRING = 'string'
    COUNTER = 'counter'
    GAUGE = 'gauge'
    HISTOGRAM = 'histogram'
