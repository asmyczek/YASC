# -*- coding: utf-8 -*-

from enum import Enum
from logging import StreamHandler
from logging.handlers import RotatingFileHandler
from collections import namedtuple, deque
from pathlib import Path
from multiprocessing import Lock, Value
from datetime import datetime
from queue import Queue
import logging
import json
import sys
import os


# Zone actions used for zone_queue
class ZoneAction(Enum):
    ZONE = 0        # Active zone x
    NEXT = 1        # Move forward by 1 zone
    STOP = 2        # Stop yasc
    TERMINATE = 3   # Terminate application
    RUN_CYCLE = 4   # Run full cycle with interval defined in manual_cycle
    NONE = 5        # Fallback in case of undefined


# Environments
class Environment(Enum):
    DEV = 0     # Development
    PROD = 1    # On yasc


class RunState(Enum):
    OFF = 0    # Not running
    SINGLE_ZONE = 1    # Running a single zone
    CYCLE = 2   # Running a cycle


class ControllerMode(Enum):
    OFF = 0     # Sprinkler is off
    AUTO = 1    # Manual trigger/ web or button
    LOCAL = 2   # Local timer
    MQTT = 3    # MQTT control


# Setup logging
APP_LOGGER_BUFFER_SIZE = 200


class AppLogHandler(StreamHandler):
    def __init__(self):
        super(StreamHandler, self).__init__()
        self.__queue = deque([], APP_LOGGER_BUFFER_SIZE)
        self.__counter = Value('i', 0)
        self.__lock = Lock()

    def emit(self, record):
        with self.__lock:
            self.__counter.value += 1
        self.__queue.append(self.format(record))

    def flush(self):
        pass

    def get_logs(self, offset=0):
        with self.__lock:
            delta = self.__counter.value - offset
            delta = 0 if delta < 0 else delta
            delta = APP_LOGGER_BUFFER_SIZE if delta > APP_LOGGER_BUFFER_SIZE else delta
            logs = [] if delta == 0 else [e for e in self.__queue.copy()]
            return {'offset': self.__counter.value,
                    'logs': logs[len(logs) - delta:]}


APP_LOG_HANDLER = AppLogHandler()
GLOBAL_LOG_HANDLER = None

log_level_str = os.getenv('YASC_LOG_LEVEL', None)
log_level = logging.INFO
if log_level_str is not None:
    log_level = logging.getLevelName(log_level_str.upper())

logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
rootLogger = logging.getLogger()
rootLogger.setLevel(log_level)

env = os.getenv('YASC_ENV', None)
if env is not None and Environment[env.upper()] == Environment.PROD:
    GLOBAL_LOG_HANDLER = RotatingFileHandler("{0}/{1}.log".format('.', 'yasc'), maxBytes=10000000, backupCount=5)
    GLOBAL_LOG_HANDLER.setFormatter(logFormatter)
    rootLogger.addHandler(GLOBAL_LOG_HANDLER)
else:
    GLOBAL_LOG_HANDLER = logging.StreamHandler()
    GLOBAL_LOG_HANDLER.setFormatter(logFormatter)
    rootLogger.addHandler(GLOBAL_LOG_HANDLER)

APP_LOG_HANDLER.setFormatter(logFormatter)
rootLogger.addHandler(APP_LOG_HANDLER)


logging.info('Starting application...')


# Get deployment environment

def __setup_environment():
    env = os.getenv('YASC_ENV', None)
    if env is None:
        logging.error('Environment variable YASC_ENV not defined!')
        logging.error('Setting environment to DEV!')
        return Environment.DEV
    else:
        try:
            return Environment[env.upper()]
        except ValueError:
            logging.error('Unrecognized environment variable YASC_ENV with value {0}.'.format(env))
            logging.error('Setting environment to DEV!')
            return Environment.DEV


_ENVIRONMENT = __setup_environment()


def in_development():
    return _ENVIRONMENT == Environment.DEV


def in_production():
    return _ENVIRONMENT == Environment.PROD


APP_PATH = Path('.').resolve()
logging.info('Application file paht is {0}'.format(APP_PATH.absolute()))


# Config
def get_project_path():
    return Path('.').resolve()


CONFIG = None

try:
    config_file = Path('config_{0}.json'.format(_ENVIRONMENT.name.lower())).resolve()
    with config_file.open() as file:
        config_str = file.read()
        CONFIG = json.loads(config_str, object_hook=lambda d: namedtuple('X', d.keys())(*d.values()))
except FileNotFoundError:
    logging.error('Config file {0} does not exist!'.format(config_file))
    sys.exit(1)
else:
    logging.info('Loaded config {0}.'.format(config_file.name))
    logging.info(json.dumps(json.loads(config_str), indent=2, sort_keys=True))


# State
class _State(object):

    def __init__(self):
        self.__zone_queue = Queue()
        self.__lock_mode = Lock()
        self.__mode = Value('i', ControllerMode.AUTO.value)
        self.__lock_run_state = Lock()
        self.__run_state = Value('i', RunState.OFF.value)
        self.__active_zones = set()
        self.__status_file = None
        self.__zone_on_callback = []
        self.__zone_off_callback = []
        self.__mode_changed_callback = []
        self.__next_run_callback = None
        self.__mqtt_status_callback = None
        self.__load_status()

    def __load_status(self):
        try:
            self.__status_file = Path('state_{0}.json'.format(_ENVIRONMENT.name.lower())).resolve()
            with self.__status_file.open() as file:
                status_str = file.read()
                status = json.loads(status_str)
                self.__mode.value = ControllerMode[status['controller_mode']].value
                logging.info('Loaded status file {0}.'.format(self.__status_file))
        except FileNotFoundError:
            logging.info('Creating new status file {0}.'.format(self.__status_file))
            with self.__lock_mode:
                self.__save_status()

    def __save_status(self):
        logging.debug('Writing status file to {0}.'.format(self.__status_file))
        with open('state_{0}.json'.format(_ENVIRONMENT.name.lower()), 'w') as file:
            status = {'_comment': 'DO NOT EDIT! THIS FILE IS AUTO-GENERATED.',
                      'controller_mode': ControllerMode(self.__mode.value).name}
            json.dump(status, file, indent=4, sort_keys=True)
        self.__status_file = Path('state_{0}.json'.format(_ENVIRONMENT.name.lower())).resolve()

    def add_zone_on_callback(self, callback):
        self.__zone_on_callback.append(callback)

    def add_zone_off_callback(self, callback):
        self.__zone_off_callback.append(callback)

    def add_mode_changed_callback(self, callback):
        self.__mode_changed_callback.append(callback)

    def set_next_run_callback(self, callback):
        self.__next_run_callback = callback

    def set_mqtt_status_callback(self, callback):
        self.__mqtt_status_callback = callback

    def active_controller_mode(self):
        with self.__lock_mode:
            if self.__mode.value == ControllerMode.AUTO.value:
                return ControllerMode.MQTT if self.mqtt_connected() else ControllerMode.LOCAL
            else:
                return ControllerMode(self.__mode.value)

    def run_zone_action(self, action):
        self.__zone_queue.put(action)

    def process_queue(self, lf):
         lf(self.__zone_queue)

    def next_run(self):
        next_run = self.__next_run_callback() if self.__next_run_callback is not None else None
        return next_run if next_run is not None else datetime.max

    def mqtt_connected(self):
        if self.__mqtt_status_callback is not None:
            return self.__mqtt_status_callback()
        else:
            logging.warning('MQTT status callback not set. Returning False.')
            return False

    def control_mode(self):
        with self.__lock_mode:
            return ControllerMode(self.__mode.value)

    def set_control_mode(self, mode):
        with self.__lock_mode:
            if self.__mode.value != mode.value:
                self.__mode.value = mode.value
                self.__save_status()
                for callback in self.__mode_changed_callback:
                    callback(ControllerMode(self.__mode.value))

    def zone_on(self, zone):
        with self.__lock_run_state:
            self.__active_zones.add(zone)
            for callback in self.__zone_on_callback:
                callback(zone)

    def zone_off(self, zone):
        with self.__lock_run_state:
            try:
                self.__active_zones.remove(zone)
            except KeyError:
                logging.warning('Zone {0} is stopped or invalid.'.format(zone))
            for callback in self.__zone_off_callback:
                callback(zone)

    def cycle_on(self):
        with self.__lock_run_state:
            if len(self.__active_zones) > 0:
                logging.warning('Zones {0} are still active.'.format(self.__active_zones))
            self.__run_state.value = RunState.CYCLE.value

    def single_zone_on(self):
        with self.__lock_run_state:
            if len(self.__active_zones) > 0:
                logging.warning('Zones {0} are still active.'.format(self.__active_zones))
            self.__run_state.value = RunState.SINGLE_ZONE.value

    def run_off(self):
        with self.__lock_run_state:
            self.__run_state.value = RunState.OFF.value

    def run_state(self):
        with self.__lock_run_state:
            return RunState(self.__run_state.value)


state = _State()

# ------ key logger for development ----
if in_development():
    import sys
    import termios
    import tty
    import select

    def get_keyboard_status():
        kp = select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])
        if kp:
            sys.stdin.read(1)
            return 1
        else:
            return 0

    def reset_keyboard_settings():
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    old_settings = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())
# ----------------------------------
