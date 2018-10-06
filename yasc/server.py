# -*- coding: utf-8 -*-

import cherrypy
from cherrypy.lib import auth_digest
from yasc.utils import CONFIG, state, APP_LOG_HANDLER, GLOBAL_LOG_HANDLER, \
    ControllerMode, ZoneAction, in_production, get_project_path
from yasc.__init__ import __version__
from datetime import datetime
import logging


if in_production():
    from yasc.pi_controller import get_active_zone
else:
    from yasc.zone_controller import get_active_zone


class App(object):

    @cherrypy.expose
    def index(self):
        return open('webapp/index.html')


@cherrypy.expose
class Api(object):
    pass


@cherrypy.expose
class ApiStatus(object):
    @cherrypy.tools.json_out()
    def GET(self,  **kwargs):
        return {'active_zone': get_active_zone(),
                'run_state': state.run_state().name,
                'active_controller_mode': state.active_controller_mode().name,
                'controller_mode': state.control_mode().name,
                'next_run': state.next_run().strftime('%a %d %b %Y at %H:%M'),
                'now': datetime.now().strftime('%H:%M:%S'),
                'mqtt_connected': state.mqtt_connected()}


@cherrypy.expose
class ApiLogs(object):
    @cherrypy.tools.json_out()
    def GET(self,  offset):
        return APP_LOG_HANDLER.get_logs(int(offset))


@cherrypy.expose
class ApiConfig(object):
    @cherrypy.tools.json_out()
    def GET(self, **kwargs):
        zones = []
        for zone in CONFIG.active_zones:
            zones.append({'zone': zone.zone,
                          'name': zone.name})
        return {'environment': 'prod' if in_production() else 'dev',
                'active_zones': zones,
                'version': __version__}


@cherrypy.expose
class ApiSetControllerMode(object):

    @cherrypy.tools.json_out()
    def POST(self, **kwargs):
        mode = kwargs.get('mode', 'None')
        if mode != 'None':
            logging.info('Setting controller mode to {0}'.format(mode))
            state.set_control_mode(ControllerMode[mode])
        else:
            logging.error('Mode not defined!')


@cherrypy.expose
class ApiRunCycle(object):

    @cherrypy.tools.json_out()
    def POST(self, **kwargs):
        logging.debug('POST run cycle')
        state.run_zone_action((ZoneAction.RUN_CYCLE, 0))


@cherrypy.expose
class ApiActivateZone(object):

    @cherrypy.tools.json_out()
    def POST(self, **kwargs):
        logging.debug('Activate zone request {0}'.format(kwargs))
        zone = kwargs.get('zone', '0')
        if int(zone) > 0:
            state.run_zone_action((ZoneAction.ZONE, int(zone)))
        return True


@cherrypy.expose
class ApiStopSprinkler(object):

    @cherrypy.tools.json_out()
    def POST(self, **kwargs):
        state.run_zone_action((ZoneAction.STOP, 0))


def start_server(start_callback, stop_callback):

    config = {
        '/': {
            'tools.sessions.on': True,
            'tools.staticdir.root': str(get_project_path().absolute())
        },
        '/api': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'text/json')],
        },
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': './webapp'
        }
    }

    cherrypy.engine.subscribe('start', start_callback)
    cherrypy.engine.subscribe('stop', stop_callback)

    app = App()
    app.api = Api()
    app.api.status = ApiStatus()
    app.api.config = ApiConfig()
    app.api.logs = ApiLogs()
    app.api.set_controller_mode = ApiSetControllerMode()
    app.api.activate_zone = ApiActivateZone()
    app.api.run_cycle = ApiRunCycle()
    app.api.stop_sprinkler = ApiStopSprinkler()

    user = {CONFIG.server.user: CONFIG.server.password}

    cherrypy.config.update({'log.screen': False,
                            'log.access_file': '',
                            'log.error_file': '',
                            'tools.auth_digest.on': True,
                            'tools.auth_digest.realm': 'localhost',
                            'tools.auth_digest.get_ha1': auth_digest.get_ha1_dict_plain(user),
                            'tools.auth_digest.key': 'b361e37146791cfb',
                            'tools.auth_digest.accept_charset': 'UTF-8'
                            })
    logging.getLogger("cherrypy").propagate = False
    logging.getLogger("cherrypy.error").addHandler(GLOBAL_LOG_HANDLER)

    cherrypy.config.update({'server.socket_host': '0.0.0.0',
                            'server.socket_port': CONFIG.server.port})
    cherrypy.quickstart(app, '/', config)
