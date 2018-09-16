# -*- coding: utf-8 -*-

from yasc.utils import in_production, state
from yasc.button_controller import ButtonController
from yasc.zone_controller import ZoneController
from yasc.mqtt_controller import MQTTController
from yasc.server import start_server
from yasc.local_controller import LocalController
from queue import Queue
import logging

# RPi imports not working
if in_production():
    from yasc.pi_controller import setup_pi, cleanup_pi, led_on
else:
    def setup_pi():
        logging.debug('Setting up PI.')

    def cleanup_pi():
        logging.debug('Cleaning up PI config.')

    def led_on(led):
        logging.debug('Led {0} on.'.format(led))
        pass


def main():

    zone_queue = Queue()
    zone_controller = None
    local_controller = None
    button_controller = None
    mqtt_controller = None

    def start():
        led_on(1)

    def stop():
        if button_controller is not None:
            button_controller.stop()
        if local_controller is not None:
            local_controller.stop()
        if zone_controller is not None:
            zone_controller.stop()
        if mqtt_controller is not None:
            mqtt_controller.cleanup()

        cleanup_pi()

    try:
        setup_pi()

        zone_controller = ZoneController(zone_queue)
        zone_controller.start()

        mqtt_controller = MQTTController(zone_queue)
        state.add_zone_on_callback(mqtt_controller.zone_on)
        state.add_zone_off_callback(mqtt_controller.zone_off)
        state.set_mqtt_status_callback(mqtt_controller.mqtt_connected)

        local_controller = LocalController(zone_queue)
        local_controller.start()

        state.set_next_run_callback(local_controller.next_run)

        button_controller = ButtonController(zone_queue)
        button_controller.start()

        start_server(start, stop, zone_queue)

    finally:
        stop()

    logging.info('Application stopped')


if __name__ == '__main__':
    main()

