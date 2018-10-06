var environment = 'dev';
var running = false;
var log_offset = 0;
var active_zones = {0: 'None'};

loadConfig = function(config) {
    window.environment = config.environment;
    $.each(config.active_zones, function(index, zone) {
        window.active_zones[zone.zone] = zone.name;
        $('#zones').append('<button onclick="activate_zone(' + zone.zone + ')" class="button button-zone">' + zone.name + '</button>');
    });
    $('#version').html(config.version);
}

update_status = function() {
    $.get('api/status', function(data) {
        if (window.environment == 'dev') {
            console.log(data);
        };
        var running = 'OFF'
        window.running = false;
        if (data.run_state == 'CYCLE') {
            running = 'Cycle'
            window.running = true;
        } else if (data.run_state == 'SINGLE_ZONE') {
            running = 'Zone'
            window.running = true;
        } else if (data.run_state == 'OFF') {
            running = 'Off'
            window.running = false;
        } else {
            running = data.run_state;
            window.running = false;
        };
        if ($('#onoff').is(':checked') != data.is_on) {
            $('#onoff').prop('checked', data.is_on);
            };
        $('#running').html(running);
        $('#activezone').html(window.active_zones[data.active_zone]);
        $('#controller-mode').html(data.controller_mode)
        $('#active-controller-mode').html(data.active_controller_mode)
        $('#environment').html(window.environment)
        if (data.mqtt_connected) {
            $('#mqtt').html('connected')
        } else {
            $('#mqtt').html('disconnected')
        }
        if (data.active_controller_mode == "LOCAL") {
            $('#next_run').html(data.next_run)
        } else {
            $('#next_run').html('Not defined');
        };
        $('#now').html(data.now)
        setTimeout(update_status, 1000);
        });
}

update_logs = function() {
    $.get('api/logs', {'offset': window.log_offset}, function(data) {
        window.log_offset = data.offset
        $.each(data.logs, function(index, log) {
            $('#logs').append(log + '<br />');
        });
        setTimeout(update_logs, 5000);
        });
}

set_mode = function(mode) {
    $.post('api/set_controller_mode', { 'mode': mode });
}

activate_zone = function(zone) {
    if (window.running) {
        if (confirm('Sprinkler is currently running. Cancel current run?')) {
            $.post('api/activate_zone', { 'zone': zone });
        }
    } else {
        $.post('api/activate_zone', { 'zone': zone });
    }
}

run_cycle = function() {
    if (window.running) {
        if (confirm('Sprinkler is currently running. Cancel current run?')) {
            $.post('api/run_cycle');
        }
    } else {
        $.post('api/run_cycle');
    }
}

stop_sprinkler = function() {
    if (window.running) {
        if (confirm('Do you want to stop current run?')) {
            $.post('api/stop_sprinkler');
        }
    } else {
        $.post('api/stop_sprinkler');
    }
}
