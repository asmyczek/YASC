# -*- coding: utf-8 -*-

from threading import Thread, Event
from yasc.utils import CONFIG, state, ZoneAction, in_production, ControllerMode
from datetime import datetime, timedelta
from time import sleep
import logging

# RPi imports not working
if in_production():
    from yasc.pi_controller import get_active_zone, activate_zone, stop_sprinkler
else:
    __dev_zone = 0

    def activate_zone(zone):
        logging.debug('Activation zone {0}.'.format(zone))
        global __dev_zone
        __dev_zone = zone
        state.zone_on(zone)

    def get_active_zone():
        return __dev_zone

    def stop_sprinkler():
        logging.debug('Stopping sprinkler zone')
        global __dev_zone
        if __dev_zone > 0:
            logging.debug('Stopping zone {0}.'.format(__dev_zone))
            state.zone_off(__dev_zone)
            __dev_zone = 0


# FIXME: use thread pool

class ManualRunner(Thread):
    def __init__(self, zone, interval):
        Thread.__init__(self, name='Zone Run')
        self.__interval = interval
        self.__zone = zone
        self.__stop = Event()

    def stop(self):
        logging.info('Stop manual run for zone {0}.'.format(self.__zone))
        if not self.__stop.is_set():
            self.__stop.set()

    def run(self):
        state.single_zone_on()
        start_time = datetime.now()
        activate_zone(self.__zone)
        while not self.__stop.is_set():
            now = datetime.now()
            timediff = timedelta(minutes=self.__interval) if in_production() else timedelta(seconds=self.__interval)
            if now - start_time > timediff:
                self.__stop.set()
            sleep(1)
        stop_sprinkler()
        state.run_off()
        logging.info('Manual run for zone {0} end.'.format(self.__zone))


class CycleRunner(Thread):
    def __init__(self, interval):
        Thread.__init__(self, name='Cycle Run')
        self.__interval = interval
        self.__stop = Event()

    def stop(self):
        logging.info('Stop cycle.')
        if not self.__stop.is_set():
            self.__stop.set()

    def __start_zone(self, zone_index):
        zone_info = CONFIG.active_zones[zone_index]
        activate_zone(zone_info.zone)

        interval = getattr(zone_info, "interval", self.__interval)
        logging.info('Running zone {0} for {1} min/sec.'.format(zone_info.zone, interval))
        return datetime.now(), timedelta(minutes=interval) if in_production() else timedelta(seconds=interval)

    def run(self):
        logging.info('Starting cycle.')
        state.cycle_on()
        zone_index = 0
        zone_count = len(CONFIG.active_zones)
        start_time, interval = self.__start_zone(zone_index)
        while not self.__stop.is_set():
            now = datetime.now()
            if now - start_time > interval:
                zone_index += 1
                if zone_index < zone_count:
                    stop_sprinkler()
                    start_time, interval = self.__start_zone(zone_index)
                else:
                    self.__stop.set()
            sleep(1)
        stop_sprinkler()
        state.run_off()
        logging.info('Cycle end.')


class ZoneController(Thread):
    def __init__(self):
        Thread.__init__(self, name='Zone Controller')
        self.__stop = Event()
        self.__manual_runner = None
        self.__cycle_runner = None

    def __stop_cycle_runner(self):
        if self.__cycle_runner is not None and self.__cycle_runner.is_alive():
            logging.warning('Cycle is running. Terminating...')
            self.__cycle_runner.stop()
            self.__cycle_runner.join()
            self.__cycle_runner = None

    def is_cycle_running(self):
        return self.__cycle_runner is not None and self.__cycle_runner.is_alive()

    def __stop_manual_runner(self):
        if self.__manual_runner is not None and self.__manual_runner.is_alive():
            logging.warning('Manual runner is acitve. Terminating...')
            self.__manual_runner.stop()
            self.__manual_runner.join()
            self.__manual_runner = None

    def is_manual_running(self):
        return self.__manual_runner is not None and self.__manual_runner.is_alive()

    def get_active_zone(self):
        return get_active_zone()

    def stop(self):
        if not self.__stop.is_set():
            self.__stop.set()
        self.__stop_manual_runner()
        self.__stop_cycle_runner()
        state.run_zone_action((ZoneAction.TERMINATE, 0))
        self.join()

    def control_mode_changed(self):
        if state.active_controller_mode() is ControllerMode.OFF:
            state.run_zone_action((ZoneAction.STOP, 0))

    def __get_zone_index(self, zone):
        for index, zone_info in enumerate(CONFIG.active_zones):
            if zone_info.zone == zone:
                return index
        return -1

    def __zone_in_active_zones(self, zone):
        for zone_info in CONFIG.active_zones:
            if zone_info.zone == zone:
                return True
        return False

    def __queue_processor(self, queue):
        action_type, event_value = queue.get()
        logging.debug('Received action {0} with event value {1}.'.format(action_type, event_value))
        self.__stop_manual_runner()
        self.__stop_cycle_runner()
        if action_type in [ZoneAction.TERMINATE, ZoneAction.STOP]:
            # Leave dummy for now
            pass
        elif action_type == ZoneAction.RUN_CYCLE:
            self.__cycle_runner = CycleRunner(CONFIG.default_interval)
            self.__cycle_runner.start()
        elif action_type == ZoneAction.NEXT:
            current_active = get_active_zone()
            current_index = self.__get_zone_index(current_active)
            next_index = current_index + 1
            if -1 < next_index < len(CONFIG.active_zones):
                zone = CONFIG.active_zones[next_index].zone
                self.__manual_runner = ManualRunner(zone, CONFIG.default_interval)
                self.__manual_runner.start()
            else:
                logging.debug('Next index {0} outside active zone range. Stop yasc.'.format(next_index))
        elif action_type == ZoneAction.ZONE:
            if self.__zone_in_active_zones(event_value):
                self.__manual_runner = ManualRunner(event_value, CONFIG.default_interval)
                self.__manual_runner.start()
            else:
                logging.error('Zone {0} is not an active zone!'.format(event_value))

        queue.task_done()

    def run(self):
        logging.info('Zone Controller started')
        while not self.__stop.is_set():
            state.process_queue(self.__queue_processor)

        logging.info('Zone Controller stopped')

