import datetime
import json
from traceback import format_exception_only


def format_exception(ex):
    return format_exception_only(ex.__class__, ex)[-1].strip()


def json_dumps(obj):
    def default(o):
        if isinstance(o, (datetime.datetime, datetime.date)):
            return o.isoformat()
        raise TypeError('%r is not JSON serializable' % obj)
    return json.dumps(obj, default=default)
