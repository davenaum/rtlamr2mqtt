#!/usr/bin/env python3

import os
import sys
import yaml
import signal
import subprocess
from time import sleep
from json import dumps,loads
import paho.mqtt.client as mqtt

# uses signal to shutdown and hard kill opened processes and self
def shutdown(signum, frame):
    if rtltcp.returncode is None:
        rtltcp.terminate()
        try:
            rtltcp.wait(timeout=5)
        except subprocess.TimeoutExpired:
            rtltcp.kill()
            rtltcp.wait()
    if rtlamr.returncode is None:
        rtlamr.terminate()
        try:
            rtlamr.wait(timeout=5)
        except subprocess.TimeoutExpired:
            rtlamr.kill()
            rtlamr.wait()
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

##################### BUILD CONFIGURATION #####################
with open('/etc/rtlamr2mqtt.yaml','r') as config_file:
  config = yaml.safe_load(config_file)

# Build MQTT configuration
mqtt_host = "127.0.0.1" if 'host' not in config['mqtt'] else config['mqtt']['host']
mqtt_port = 1883 if 'port' not in config['mqtt'] else int(config['mqtt']['port'])
state_topic = '/rtlamr/{}/state'
mqtt_client = mqtt.Client(client_id='rtlamr2mqtt')

if 'general' in config:
    sleep_for = 0 if 'sleep_for' not in config['general'] else config['general']['sleep_for']
else:
    sleep_for = 0

# Build RTLAMR config
protocols = []
meter_ids = []
meter_readings = {}
for idx,meter in enumerate(config['meters']):
    config['meters'][idx]['name'] = str('meter_{}'.format(meter['id'])) if 'name' not in meter else str(meter['name'])
    config['meters'][idx]['unit_of_measurement'] = '' if 'unit_of_measurement' not in meter else str(meter['unit_of_measurement'])
    config['meters'][idx]['icon'] = 'mdi:gauge' if 'icon' not in meter else str(meter['icon'])
    protocols.append(meter['protocol'])
    meter_ids.append(str(meter['id']))
    meter_readings[str(meter['id'])] = 0

rtlamr_custom = []
if 'custom_parameters' in config:
    if 'rtlamr' in config['custom_parameters']:
        rtlamr_custom = config['custom_parameters']['rtlamr'].split(' ')
rtlamr_cmd = ['/usr/bin/rtlamr', '-msgtype={}'.format(','.join(protocols)), '-format=json', '-filterid={}'.format(','.join(meter_ids))] + rtlamr_custom
#################################################################

# Build RTLTCP command
rtltcp_custom = []
if 'custom_parameters' in config:
    if 'rtltcp' in config['custom_parameters']:
        rtltcp_custom = config['custom_parameters']['rtltcp'].split(' ')
rtltcp_cmd = ["/usr/bin/rtl_tcp"] + rtltcp_custom
#################################################################

# Main loop
while True:
    # Is this the first time are we executing this loop? Or is rtltcp running?
    if 'rtltcp' not in locals() or rtltcp.poll() is not None:
        # start the rtl_tcp program
        rtltcp = subprocess.Popen(rtltcp_cmd, stderr=subprocess.DEVNULL)
        print('RTL_TCP started with PID {}'.format(rtltcp.pid), file=sys.stderr)
        # Wait 2 seconds to settle
        sleep(2)
    # Is this the first time are we executing this loop? Or is rtlamr running?
    if 'rtlamr' not in locals() or rtlamr.poll() is not None:
        # start the rtlamr program.
        rtlamr = subprocess.Popen(rtlamr_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True)
        print('RTLAMR started with PID {}'.format(rtlamr.pid), file=sys.stderr)
    for amrline in rtlamr.stdout:
        try:
            json_output = loads(amrline)
        except json.decoder.JSONDecodeError:
            json_output = None
        if json_output is not None and 'Message' in json_output:
            if 'EndpointID' in json_output['Message']:
                meter_id = str(json_output['Message']['EndpointID']).strip()
            elif 'ID' in json_output['Message']:
                meter_id = str(json_output['Message']['ID']).strip()
            else:
                meter_id = None
            if 'Consumption' in json_output['Message']:
                raw_reading = str(json_output['Message']['Consumption']).strip()
            else:
                raw_reading = None
            if meter_id is not None and raw_reading is not None:
                for meter in config['meters']: # We have a reading, but we don't know for which meter is it, let's check
                    if meter_id == str(meter['id']).strip():
                        if 'format' in meter:
                            formated_reading = meter['format'].replace('#','{}').format(*raw_reading.zfill(meter['format'].count('#')))
                        else:
                            formated_reading = raw_reading
                        print('Meter "{}" - Consumption {}. Sending value to MQTT.'.format(meter_id, formated_reading), file=sys.stderr)
                        mqtt_client.connect(host=mqtt_host, port=mqtt_port)
                        mqtt_client.publish(topic=state_topic.format(meter['name']), payload=str(formated_reading).encode('utf-8'), qos=0, retain=True)
                        mqtt_client.disconnect()
                        meter_readings[meter_id] += 1
        if sleep_for > 0:
            # Check if we have readings for all meters
            if len({k:v for (k,v) in meter_readings.items() if v > 0}) >= len(meter_readings):
                # Set all values to 0
                meter_readings = dict.fromkeys(meter_readings, 0)
                # Exit from the main for loop and stop reading the rtlamr output
                break
    # Kill all process
    if rtltcp.returncode is None:
        rtltcp.terminate()
        try:
            rtltcp.wait(timeout=5)
        except subprocess.TimeoutExpired:
            rtltcp.kill()
            rtltcp.wait()
    if rtlamr.returncode is None:
        rtlamr.terminate()
        try:
            rtlamr.wait(timeout=5)
        except subprocess.TimeoutExpired:
            rtlamr.kill()
            rtlamr.wait()
    sleep(sleep_for)
