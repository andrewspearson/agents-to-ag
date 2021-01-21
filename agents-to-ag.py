import argparse
import configparser
import os
from tenable.io import TenableIO
from tenable.sc import TenableSC
import time
from datetime import datetime

# Create and read configuration file
tenable_ini = """[tenable_io]
########
# Connection info
########
access_key = {{ACCESS_KEY}}
secret_key = {{SECRET_KEY}}
https_proxy =
########
# Data variables
########
# Include all assets that were last seen within x days (Default: 7)
last_seen = 7

[tenable_sc]
########
# Connection info
########
endpoint = 127.0.0.1
access_key = {{ACCESS_KEY}}
secret_key = {{SECRET_KEY}}
https_proxy =
ssl_verify = False
"""

parser = argparse.ArgumentParser(description='Auto populate a TSC Static Asset Group with IPs with Nessus agents.')
parser_group = parser.add_mutually_exclusive_group(required=True)
parser_group.add_argument('--config', metavar='<tenable.ini>', dest='config_file',
                          help='INI config file')
parser_group.add_argument('--config-gen', dest='config_gen', action='store_true',
                          help='Generate a new INI config file.')
config_file = parser.parse_args().config_file
config_gen = parser.parse_args().config_gen
if config_file:
    if not os.path.isfile(config_file):
        print(config_file + ' does not exist. Use the --config-gen flag to create one.')
        exit()
    else:
        config = configparser.ConfigParser()
        config.read(config_file)
        tio_config = config['tenable_io']
        tsc_config = config['tenable_sc']
elif config_gen:
    if os.path.isfile('tenable.ini'):
        print('tenable.ini config file already exists and will NOT be overwritten.\nIf you want to create a new '
              'config file then either rename or delete the existing tenable.ini file.')
        exit()
    else:
        file_loc = 'tenable.ini'
        file = open(file_loc, mode='w')
        file.write(tenable_ini)
        file.close()
        if not os.path.isfile(file_loc):
            print('Unable to write file: ' + file_loc)
        else:
            print('Wrote file: ' + file_loc)
        print('Edit the new INI configuration file for your environment.')
        exit()
else:
    print('Input error')
    exit()

# Establish API clients
tio_client = TenableIO(tio_config['access_key'], tio_config['secret_key'])
tsc_client = TenableSC(tsc_config['endpoint'], tsc_config['access_key'], tsc_config['secret_key'])

# Identify agent IPs via Asset Export
last_seen = int(time.time() - (int(tio_config['last_seen']) * 86400))
response = tio_client.exports.assets(sources=["NESSUS_AGENT"],
                                     last_authenticated_scan_time=last_seen)
agent_ips_list = []
agent_ips_string = ''
for asset in response:
    if asset['agent_uuid']:
        for ip in asset['ipv4s']:
            agent_ips_list.append(ip)
# Identify agent IPs from agents that have not yet run a scan (e.g. recently connected to Tenable.IO)
response = tio_client.agents.list()
for agent in response:
    if 'last_scanned' not in agent and 'last_connect' in agent and agent['last_connect'] >= last_seen:
        agent_ips_list.append(agent['ip'])
agent_ips_string = ','.join(agent_ips_list)

# Write agent IPs to Tenable.SC Asset Group
asset_group_name = 'Agent Installed - Script'
timestamp = 'Updated: ' + datetime.now().strftime("%A %Y-%m-%d %H:%M:%S")
response = tsc_client.asset_lists.list()
if any(item['name'] == asset_group_name for item in response['usable']):
    for item in response['usable']:
        if item['name'] == asset_group_name:
            tsc_client.asset_lists.edit(item['id'], ips=agent_ips_string, description=timestamp)
            break
else:
    tsc_client.asset_lists.create(asset_group_name, 'static', ips=agent_ips_string, description=timestamp)
