#!/usr/bin/env python3

import os
import subprocess
import signal
import sys
import time
import yaml
import paho.mqtt.publish as publish
from datetime import datetime

# uses signal to shutdown and hard kill opened processes and self
def shutdown(signum, frame):
    rtltcp.send_signal(15)
    rtlamr.send_signal(15)
    time.sleep(1)
    rtltcp.send_signal(9)
    rtlamr.send_signal(9)
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)


with open('/etc/rtlamr2mqtt.yaml','r') as config_file:
  config = yaml.safe_load(config_file)

# build mqtt configuration
mqtt_host = config['mqtt']['host']
mqtt_port = int(config['mqtt']['port'])
mqtt_topic = '/rtlamr/{}/state'

# build general configuration
sleep_time = int(config['general']['sleep_for'])

# build rtlamr configuration
protocols = []
meter_ids = []
for idx,meter in enumerate(config['meters']):
    config['meters'][idx]['name'] = str('meter_{}'.format(meter['id']))
    protocols.append(meter['protocol'])
    meter_ids.append(str(meter['id']))
rtlamr_custom = []
if 'custom_parameters' in config:
    if 'rtlamr' in config['custom_parameters']:
        rtlamr_custom = config['custom_parameters']['rtlamr'].split(' ')
rtlamr_cmd = [
    '/usr/bin/rtlamr',
    '-msgtype={}'.format(','.join(protocols)),
    '-format=csv',
    '-filterid={}'.format(','.join(meter_ids)),
    '-single=true'
    ] + rtlamr_custom

# build rtl_tcp command
rtltcp_custom = []
if 'custom_parameters' in config:
    if 'rtltcp' in config['custom_parameters']:
        rtltcp_custom = config['custom_parameters']['rtltcp'].split(' ')
rtltcp_cmd = ["/usr/bin/rtl_tcp"] + rtltcp_custom


while True:
    try:
        # start the rtl_tcp program
        rtltcp = subprocess.Popen(rtltcp_cmd, shell=True, close_fds=True)
        time.sleep(5)

        # start the rtlamr program.
        rtlamr = subprocess.Popen(rtlamr_cmd, stdout=subprocess.PIPE, universal_newlines=True)

        amrline, stderrors = rtlamr.communicate(timeout=180)
        flds = amrline.split(',')

        # proper scm+ results have 10 fields
        if len(flds) != 10:
            print('{} Received result with unexpected number of fields: \'{}\''.format(str(datetime.now()), amrline), file=sys.stderr)
            continue

        # make sure the meter id is one we want
        meter_id = flds[6]
        if meter_id not in meter_ids:
            print('{} Received result with unexpected meter id: {}'.format(str(datetime.now()), meter_id), file=sys.stderr)
            continue

        mqtt_payload = '{ "meter_value": "' + str(flds[7]) + '", "meter_time": "' + flds[0]+ '" }'

        print('{} Sending meter {}: {}'.format(str(datetime.now()), meter_id, mqtt_payload), file=sys.stderr)
        publish.single(
                topic='/rtlamr/{}/meter_reading'.format(meter_id),
                payload=mqtt_payload,
                qos=1,
                retain=True,
                hostname=mqtt_host,
                port=mqtt_port)

        rtltcp.kill()
        outs, errs = rtltcp.communicate()
        rtlamr.kill()
        outs, errs = rtlamr.communicate()

        time.sleep(sleep_time)

    except Exception as e:
        print('{} Exception squashed! {}: {}'.format(str(datetime.now()), e.__class__.__name__, e), file=sys.stderr)

        rtltcp.kill()
        outs, errs = rtltcp.communicate()
        rtlamr.kill()
        outs, errs = rtlamr.communicate()

        time.sleep(2)
