# -*- coding: utf-8 -*-

from yasc.utils import CONFIG, state, ControllerMode, ZoneAction, in_production
from paho.mqtt import client as paho
from enum import Enum
from threading import Thread, Event
from time import sleep
import logging

if in_production():
    from yasc.pi_controller import led_on, led_off
else:
    def led_on(led):
        logging.debug('Led {0} on'.format(led))
        pass

    def led_off(led):
        logging.debug('Led {0} off'.format(led))
        pass


class CMD(Enum):
    ON = 1       # status
    OFF = 2      # status
    ONLINE = 3   # availability
    OFFLINE = 4  # availability


class MQTTPing(Thread):

    def __init__(self, mqtt_controller):
        Thread.__init__(self, name='MQTT Ping')
        self.__mqtt_controller = mqtt_controller
        self.__stop = Event()

    def stop(self):
        if not self.__stop.is_set():
            self.__stop.set()
        self.join()

    def run(self):
        while not self.__stop.is_set():
            self.__mqtt_controller.send_available_state()
            sleep(300 if in_production() else 5)


class MQTTController:

    def __init__(self, zone_queue):
        self.__zone_queue = zone_queue
        self.__conf = CONFIG.mqtt
        self.__user_data = {'controller': self, 'conf': self.__conf, 'connected': False}
        self.__client = None
        self.__create_mqtt_clint()
        self.__ping = MQTTPing(self)
        self.__ping.start()

    def __create_mqtt_clint(self):

        # Main message processor
        def process_message(client, user_data, message):
            topic = message.topic
            status = str(message.payload.decode('utf-8'))
            controller = user_data['controller']
            conf = user_data['conf']
            logging.debug('Status update on {0} with status {1}.'.format(topic,  status))

            # FIXME: too many if else!
            cmd = topic[len(conf.topic) + 1:]
            if cmd == 'stop':
                controller.__zone_queue.put((ZoneAction.STOP, 0))
            elif cmd == 'cycle':
                controller.__zone_queue.put((ZoneAction.RUN_CYCLE, 0))
            elif cmd.startswith('zone'):
                try:
                    zone = int(cmd[5:6])
                    if 1 <= zone <= 8:
                        action = cmd[7:]
                        if action == 'status':
                            logging.info('Zone {0} received status {1}.'.format(zone, status))
                        elif action == 'set' and state.active_controller_mode() is ControllerMode.MQTT:
                            logging.info('Zone {0} received set {1}.'.format(zone, status))
                            if status == CMD.ON.name:
                                controller.__zone_queue.put((ZoneAction.ZONE, int(zone)))
                            else:
                                controller.__zone_queue.put((ZoneAction.STOP, 0))
                        elif action == 'available':
                            logging.info('Zone {0} received available status {1}.'.format(zone, status))
                    else:
                        logging.error('Zone {0} out of range [1..8]'.format(zone))
                except ValueError:
                    logging.error('Invalid zone command {0}.'.format(cmd))
            else:
                logging.warning('Invalid topic {0}.'.format(topic))

        def on_connect(client, user_data, flags, rc):
            if rc == 0:
                logging.info('Connected to mqtt broker.')
                user_data['connected'] = True
                controller = user_data['controller']
                controller.send_available_state()

                # For Home-Assistant
                self.__client.subscribe('{0}/zone/+/status'.format(self.__conf.topic), qos=2)
                self.__client.subscribe('{0}/zone/+/set'.format(self.__conf.topic), qos=2)

                # General use
                self.__client.subscribe('{0}/cycle'.format(self.__conf.topic), qos=2)
                self.__client.subscribe('{0}/stop'.format(self.__conf.topic), qos=2)

                led_on(2)
            else:
                logging.error('Unable to establish connection. RS={0}'.format(rc))
                user_data['connected'] = False
                led_off(2)

        def on_disconnect(mqttc, user_data, rc):
            logging.info('Disconnected from mqtt broker.')
            user_data['connected'] = False
            led_off(2)

        def on_publish(mqttc, user_data, mid):
            logging.debug('Data published with mid {0}.'.format(mid))

        self.__client = paho.Client(self.__conf.client_name, transport='websockets')
        self.__client.username_pw_set(self.__conf.user, password=self.__conf.password)
        self.__client.user_data_set(self.__user_data)

        self.__client.on_connect = on_connect
        self.__client.on_disconnect = on_disconnect
        self.__client.on_message = process_message
        self.__client.on_publish = on_publish
        self.__client.on_subscribe = lambda c, ud, mid, qos: logging.debug('Subscribed with qos {0}.'.format(qos))

        self.__client.will_set('{0}/status'.format(self.__conf.topic),
                               'DOWN',
                               qos=0,
                               retain=False)

        self.__client.loop_start()

        try:
            logging.info('Starting MQTT controller.')
            self.__client.connect(self.__conf.broker, self.__conf.port)
        except Exception as e:
            logging.error(e)
            logging.exception('Unable to connect to MQTT broker!')

    def send_available_state(self, state=None):
        if self.mqtt_connected():
            logging.info('Sending availability ping.')
            zones = []
            for zone_info in CONFIG.active_zones:
                zones.append(zone_info.zone)
            for zone in range(1, 9):
                if state is None:
                    msg = CMD.ONLINE if zone in zones else CMD.OFFLINE
                else:
                    msg = state
                self.__client.publish('{0}/zone/{1}/available'.format(self.__conf.topic, zone),
                                      msg.name,
                                      qos=2,
                                      retain=False)

    def zone_on(self, zone):
        if self.__client is not None:
            self.__client.publish('{0}/zone/{1}/status'.format(self.__conf.topic, zone),
                                  CMD.ON.name,
                                  qos=2,
                                  retain=False)

    def zone_off(self, zone):
        if self.__client is not None:
            self.__client.publish('{0}/zone/{1}/status'.format(self.__conf.topic, zone),
                                  CMD.OFF.name,
                                  qos=2,
                                  retain=False)

    def mqtt_connected(self):
        return self.__user_data.get('connected', False)

    def cleanup(self):
        if self.__client is not None:
            self.send_available_state(CMD.OFFLINE)
            self.__client.publish('{0}/status'.format(self.__conf.topic),
                                  'DOWN',
                                  qos=2,
                                  retain=False)
            self.__ping.stop()
            self.__client.loop_stop()
            self.__client.disconnect()
        logging.info('MQTT Controller stopped')

