# -*- coding: utf-8 -*-

from yasc.utils import state
import RPi.GPIO as GPIO
import logging
from time import sleep
from threading import Thread, Event

SLEEP_AFTER_OFF_SEC = 1
FLASH_SLEEP = 0.2

ZONES = [4, 17, 27, 22, 5, 6, 13, 19]
LEDS = [26, 21]
BUTTON = 20


def setup_pi():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    for zone in ZONES:
        GPIO.setup(zone, GPIO.OUT)

    for led in LEDS:
        GPIO.setup(led, GPIO.OUT)

    GPIO.setup(20, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    logging.info('Setting up PI config.')


def get_button_status():
    return 0
    # FIXME: bug in board
    #return 0 if GPIO.getmode() is None else GPIO.input(BUTTON)


def get_active_zone():
    for index, zone in enumerate(ZONES):
        if GPIO.input(zone):
            return index + 1
    return 0


def stop_sprinkler():
    logging.info('Stopping yasc')
    for index, zone in enumerate(ZONES):
        if GPIO.input(zone):
            state.zone_off(index + 1)
        GPIO.output(zone, 0)


def activate_zone(zone):
    logging.info('Activating zone {0}.'.format(zone))
    if get_active_zone() > 0:
        stop_sprinkler()
        sleep(SLEEP_AFTER_OFF_SEC)
    zone_index = zone - 1
    if 0 <= zone_index < len(ZONES):
        state.zone_on(zone)
        GPIO.output(ZONES[zone_index], 1)
    else:
        logging.warning('Zone {0} out of range!'.format(zone))


# Flash thread list
LEDS_FLASH = [None] * len(LEDS)


# Flash thread
class Flash(Thread):

    def __init__(self, no):
        Thread.__init__(self)
        self.__stop = Event()
        self.__no = no

    def stop(self):
        if not self.__stop.is_set():
            self.__stop.set()
            self.join()

    def run(self):
        state = 1
        while not self.__stop.is_set():
            GPIO.output(LEDS[self.__no - 1], state)
            sleep(FLASH_SLEEP)
            state = 1 - state


def led_on(no):
    if 1 <= no <= len(LEDS):
        GPIO.output(LEDS[no - 1], 1)
    else:
        logging.warning('Led number {0} out of range'.format(no))


def led_flash(no):
    if 1 <= no <= len(LEDS):
        flash = Flash(no)
        flash.start()
        LEDS_FLASH[no - 1] = flash
    else:
        logging.warning('Led number {0} out of range'.format(no))


def is_led_flashing(no):
    return LEDS_FLASH[no - 1] is not None


def led_off(no):
    if 1 <= no <= len(LEDS):
        flash = LEDS_FLASH[no - 1]
        if flash is not None:
            flash.stop()
            LEDS_FLASH[no - 1] = None
        GPIO.output(LEDS[no - 1], 0)
    else:
        logging.warning('Led number {0} out of range'.format(no))


def is_led_on(no):
    if 1 <= no <= len(LEDS):
        return GPIO.input(LEDS[no - 1]) or LEDS_FLASH[no - 1] is not None
    else:
        logging.warning('Led number {0} out of range'.format(no))


def leds_off():
    for flesh in LEDS_FLASH:
        if flesh is not None:
            flesh.stop()
    for idx in range(1):
        LEDS_FLASH[idx] = None
    for led in LEDS:
        GPIO.output(led, 0)


def cleanup_pi():
    logging.info('Cleaning up PI config.')
    stop_sprinkler()
    leds_off()
    sleep(0.5) # recommended delay
    GPIO.cleanup()

