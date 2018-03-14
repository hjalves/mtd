import re
from mtd.metric import MetricType
from mtd.plugin import BasePlugin
from mtd.subproc import SubProcessController


REGEX_SPECIAL_CHARS = r'([\.\*\+\?\|\(\)\{\}\[\]])'
REGEX_LOG_FORMAT_VARIABLE = r'\$([a-zA-Z0-9\_]+)'
LOG_FORMAT_COMBINED = '$remote_addr - $remote_user [$time_local] ' \
                      '"$request" $status $body_bytes_sent ' \
                      '"$http_referer" "$http_user_agent"'


def build_pattern(log_format=None):
    """Build regular expression to parse given format"""
    if not log_format:
        log_format = LOG_FORMAT_COMBINED
    pattern = re.sub(REGEX_SPECIAL_CHARS, r'\\\1', log_format)
    pattern = re.sub(REGEX_LOG_FORMAT_VARIABLE, '(?P<\\1>.*)', pattern)
    return re.compile(pattern)


class NginxPlugin(BasePlugin):

    async def loop(self):
        logfile = self.config.get('logfile', '/var/log/nginx/access.log')
        self._pattern = build_pattern(self.config.get('logformat'))

        subproc = SubProcessController(self.stdout_cb, self.stderr_cb)
        self.process = await subproc.start('tail', '-n0', '-F', logfile)
        return_code = await self.process.wait()
        return return_code

    def stop(self):
        return self.process.terminate()

    def process_records(self, records):
        request = records.get('request')
        status = records.get('status')
        remote_addr = records.get('remote_addr')
        http_x_forwarded_for = records.get('http_x_forwarded_for')
        if http_x_forwarded_for and http_x_forwarded_for != '-':
            remote_addr = http_x_forwarded_for
        self.logger.debug('%s: %s [status: %s] ', remote_addr, request, status)
        if status and len(status) == 3:
            comb_status = status[0] + 'xx'
            self.push(status, 1, MetricType.COUNTER)
            self.push(comb_status, 1, MetricType.COUNTER)

    def stdout_cb(self, line):
        line = line.decode(errors='replace')
        match = self._pattern.match(line)
        if match is not None:
            records = match.groupdict()
            self.process_records(records)

    def stderr_cb(self, line):
        line = line.decode(errors='replace')
        self.logger.error('stderr: %r', line)
        # TODO: this should be improved
        #self.stop()


Plugin = NginxPlugin
