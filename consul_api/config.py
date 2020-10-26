import os
import re
import argparse
import sys

from ansible.module_utils.six.moves import configparser

try:
    import consul
except ImportError as e:
    sys.exit("""failed=True msg='python-consul required for this module.
See https://python-consul.readthedocs.io/en/latest/#installation'""")


def get_log_filename():
    tty_filename = '/dev/tty'
    stdout_filename = '/dev/stdout'

    if not os.path.exists(tty_filename):
        return stdout_filename
    if not os.access(tty_filename, os.W_OK):
        return stdout_filename
    if os.getenv('TEAMCITY_VERSION'):
        return stdout_filename

    return tty_filename


def setup_logging():
    filename = get_log_filename()

    import logging.config
    logging.config.dictConfig({
        'version': 1,
        'formatters': {
            'simple': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            },
        },
        'root': {
            'level': os.getenv('ANSIBLE_INVENTORY_CONSUL_IO_LOG_LEVEL', 'WARN'),
            'handlers': ['console'],
        },
        'handlers': {
            'console': {
                'class': 'logging.FileHandler',
                'filename': filename,
                'formatter': 'simple',
            },
        },
        'loggers': {
            'iso8601': {
                'qualname': 'iso8601',
                'level': 'INFO',
            },
        },
    })
    logger = logging.getLogger('consul_io.py')
    logger.debug('Invoked with %r', sys.argv)


if os.getenv('ANSIBLE_INVENTORY_CONSUL_IO_LOG_ENABLED'):
    setup_logging()

class ConsulConfig(dict):
    def __init__(self):
        self.read_settings()
        self.read_cli_args()
        self.read_env_vars()

    def has_config(self, name):
        if hasattr(self, name):
            return getattr(self, name)
        else:
            return False

    def read_settings(self):
        ''' Reads the settings from the consul_io.ini file (or consul.ini for backwards compatibility)'''
        config = configparser.SafeConfigParser()
        if os.path.isfile(os.path.dirname(os.path.realpath(__file__)) + '/consul_io.ini'):
            config.read(os.path.dirname(os.path.realpath(__file__)) + '/consul_io.ini')
        else:
            config.read(os.path.dirname(os.path.realpath(__file__)) + '/consul.ini')

        config_options = ['host', 'token', 'datacenter', 'servers_suffix',
                          'tags', 'kv_metadata', 'kv_groups', 'availability',
                          'unavailable_suffix', 'available_suffix', 'url',
                          'domain', 'suffixes', 'bulk_load']
        for option in config_options:
            value = None
            if config.has_option('consul', option):
                value = config.get('consul', option).lower()
            setattr(self, option, value)

    def read_cli_args(self):
        ''' Command line argument processing '''
        parser = argparse.ArgumentParser(description='Produce an Ansible Inventory file based nodes in a Consul cluster')

        parser.add_argument('--list', action='store_true',
                            help='Get all inventory variables from all nodes in the consul cluster')
        parser.add_argument('--host', action='store',
                            help='Get all inventory variables about a specific consul node,'
                                 'requires datacenter set in consul.ini.')
        parser.add_argument('--datacenter', action='store',
                            help='Get all inventory about a specific consul datacenter')

        args = parser.parse_args()
        arg_names = ['host', 'datacenter']

        for arg in arg_names:
            if getattr(args, arg):
                setattr(self, arg, getattr(args, arg))

    def read_env_vars(self):
        env_var_options = ['datacenter', 'url']
        for option in env_var_options:
            value = None
            env_var = 'CONSUL_' + option.upper()
            if os.environ.get(env_var):
                setattr(self, option, os.environ.get(env_var))

    def get_availability_suffix(self, suffix, default):
        if self.has_config(suffix):
            return self.has_config(suffix)
        return default

    def get_consul_api(self):
        '''get an instance of the api based on the supplied configuration'''
        host = 'localhost'
        port = 8500
        token = None
        scheme = 'http'

        if hasattr(self, 'url'):
            from ansible.module_utils.six.moves.urllib.parse import urlparse
            o = urlparse(self.url)
            if o.hostname:
                host = o.hostname
            if o.port:
                port = o.port
            if o.scheme:
                scheme = o.scheme

        if hasattr(self, 'token'):
            token = self.token
            if not token:
                token = 'anonymous'
        return consul.Consul(host=host, port=port, token=token, scheme=scheme)
