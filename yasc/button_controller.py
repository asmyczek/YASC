# -*- coding: utf-8 -*-

from threading import Thread, Event
import logging
import time
from yasc.utils import ZoneAction, in_development, in_production


# RPi imports not working
if in_production():
    from yasc.pi_controller import get_button_status
else:
    from yasc.utils import get_keyboard_status, reset_keyboard_settings

    def get_button_status():
        return get_keyboard_status()


# Time-ing configuration
TIME_DELTA_STOP = 3  # Stop yasc if button
TIME_DELTA_NEXT = 1  # Action next


class ButtonController(Thread):
    def __init__(self, zone_queue):
        Thread.__init__(self, name='Button Controller')
        self.__stop = Event()
        self.__zone_queue = zone_queue
        self.__state_stack = []

    def stop(self):
        if not self.__stop.is_set():
            self.__stop.set()
        if in_development():
            reset_keyboard_settings()
        self.join()

    def run(self):
        logging.info('Button Controller started')
        current_state = get_button_status()
        while not self.__stop.is_set():
            time.sleep(0.1)
            state = get_button_status()
            if current_state != state:
                self.__state_stack.append((time.time(), state))
                # Initial delay for key press
                if in_development():
                    time.sleep(0.5)
                logging.debug('Button state change to {0}.'.format(state))
                current_state = state

            time_delta = 0 if len(self.__state_stack) is 0 else time.time() - self.__state_stack[-1][0]

            # Check for stop command
            if current_state == 1 and time_delta > TIME_DELTA_STOP:
                self.__state_stack.clear()
                self.__zone_queue.put((ZoneAction.STOP, 0))

            # Check for move/zone command
            if current_state == 0 and time_delta > TIME_DELTA_NEXT:
                count = int(len(self.__state_stack) / 2)
                self.__state_stack.clear()
                if count == 1:
                    self.__zone_queue.put((ZoneAction.NEXT, 0))
                elif count > 0:
                    self.__zone_queue.put((ZoneAction.RUN_CYCLE, 0))

        logging.info('Button Controller stopped')

