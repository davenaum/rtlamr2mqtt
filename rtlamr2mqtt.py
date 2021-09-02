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
    '-filterid={}'.format(','.join(meter_ids))
    ] + rtlamr_custom

# build rtl_tcp command
rtltcp_custom = []
if 'custom_parameters' in config:
    if 'rtltcp' in config['custom_parameters']:
        rtltcp_custom = config['custom_parameters']['rtltcp'].split(' ')
rtltcp_cmd = ["/usr/bin/rtl_tcp"] + rtltcp_custom




# start the rtl_tcp program
rtltcp = subprocess.Popen(rtltcp_cmd, shell=True, close_fds=True)
time.sleep(5)

# start the rtlamr program.
rtlamr = subprocess.Popen(rtlamr_cmd, stdout=subprocess.PIPE, universal_newlines=True)

while True:
    try:
        amrline = rtlamr.stdout.readline().strip()
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

        # get meter reading
        meter_value = flds[7]

        print('{} Sending meter {} reading: {}'.format(str(datetime.now()), meter_id, meter_value), file=sys.stderr)
        publish.single(
                topic='/rtlamr/{}/meter_reading'.format(meter_id),
                payload=meter_value,
                qos=1,
                retain=True,
                hostname=mqtt_host,
                port=mqtt_port)

    except Exception as e:
        print('Exception squashed! {}: {}', e.__class__.__name__, e, file=sys.stderr)
        time.sleep(2)
