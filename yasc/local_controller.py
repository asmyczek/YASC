# -*- coding: utf-8 -*-

from enum import Enum
from yasc.utils import CONFIG, state, ControllerMode, ZoneAction, in_production
from datetime import datetime
from time import sleep
from threading import Thread, Event
from re import compile
from schedule import Scheduler, Job
import logging


class Day(Enum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


TIME_PATTERN = compile('^\s*(\d{1,2}):(\d{1,2})\s*$')


def __parse_time(time_str):
    h, m = TIME_PATTERN.findall(time_str)[0]

    return (0 <= int(h) <= 24 and 0 <= int(m) <= 59) and datetime.strptime(time_str, '%H:%M') or None


def parse_config():
    local_timer = CONFIG.local_timer
    if local_timer is not None:
        days = []
        for day in local_timer.days:
            days.append(Day[day.upper()])
        start_time = __parse_time(local_timer.start_time)
        logging.info('Local timer config: {0} {1}'.format(days, start_time))
        return days, start_time
    else:
        logging.error('No local_timer defined in config!')
    return None, None


class LocalController(Thread):

    def __init__(self):
        Thread.__init__(self, name='Local Timer')
        self.__stop = Event()
        self.__days, self.__start_time = parse_config()
        self.__scheduler = Scheduler()

    def stop(self):
        if not self.__stop.is_set():
            self.__stop.set()
        self.join()

    def next_run(self):
        return self.__scheduler.next_run

    def __run_cycle(self):
        state.run_zone_action((ZoneAction.RUN_CYCLE, 0))

    def __schedule_job(self):
        if in_production():
            for day in self.__days:
                job = Job(1, self.__scheduler)
                job.start_day = day.name.lower()
                job.unit = 'weeks'
                job.at(self.__start_time.strftime("%H:%M")).do(self.__run_cycle)
        else:
            self.__scheduler.every(3).minutes.do(self.__run_cycle)
        logging.info('Next run scheduled for {0}.'.format(self.__scheduler.next_run))

    def control_mode_changed(self):
        mode = state.active_controller_mode()
        if mode is not ControllerMode.LOCAL:
            self.__scheduler.clear()
        elif mode is ControllerMode.LOCAL:
            self.__schedule_job()

    def run(self):
        logging.info('Local cycle run controller started.')
        self.__schedule_job()
        while not self.__stop.is_set():
            if state.active_controller_mode() is ControllerMode.LOCAL:
                self.__scheduler.run_pending()
            sleep(1)
        self.__scheduler.clear()
        logging.info('Local cycle run controller stopped.')

