#!/usr/bin/env python
#
# Copyright (C) 2016 Hewlett Packard Enterprise Development LP
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import json
import httplib
import random
import urllib
import ssl
import os
import time
import pytest

from opsvsi.opsvsitest import *
from copy import deepcopy
from string import rstrip

BASIC_PORT_DATA = {
    "configuration": {
        "name": "1",
        "interfaces": ["/rest/v1/system/interfaces/1"]
    },
    "referenced_by": [{"uri": "/rest/v1/system/bridges/bridge_normal"}]
}

BASIC_INT_DATA = {
    "configuration": {
        "type": "system",
        "name": "1"
    }
}


def get_switch_ip(switch):
    switch_ip = switch.cmd("python -c \"import socket;\
                            print socket.gethostbyname(socket.gethostname())\"")
    switch_ip = switch_ip.rstrip("\r\n")
    return switch_ip


def compare_dict(dict1, dict2):
    if dict1 is None or dict2 is None:
        return False

    if type(dict1) is not dict or type(dict2) is not dict:
        return False

    shared_keys = set(dict2.keys()) & set(dict2.keys())

    if not (len(shared_keys) == len(dict1.keys()) and
            len(shared_keys) == len(dict2.keys())):
        return False

    dicts_are_equal = True
    for key in dict1.keys():
        if type(dict1[key]) is dict:
            dicts_are_equal = dicts_are_equal and compare_dict(dict1[key],
                                                               dict2[key])
        elif type(dict1[key]) is list:
            intersection = set(dict1[key]) ^ set(dict2[key])
            dicts_are_equal = dicts_are_equal and len(intersection) == 0
        else:
            dicts_are_equal = dicts_are_equal and (dict1[key] == dict2[key])

    return dicts_are_equal


def execute_request(path, http_method, data, ip, full_response=False,
                    xtra_header=None):

    url = path.replace(';', '&')

    headers = {"Content-type": "application/json", "Accept": "text/plain"}
    if xtra_header:
        headers.update(xtra_header)

    sslcontext = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    sslcontext.verify_mode = ssl.CERT_REQUIRED
    sslcontext.check_hostname = False
    src_path = os.path.dirname(os.path.realpath(__file__))
    src_file = os.path.join(src_path, 'server.crt')
    sslcontext.load_verify_locations(src_file)
    conn = httplib.HTTPSConnection(ip, 443, context=sslcontext)
    conn.request(http_method, url, data, headers)
    response = conn.getresponse()
    status_code, response_data = response.status, response.read()
    conn.close()

    if full_response:
        return response, response_data
    else:
        return status_code, response_data


def query_object(switch_ip, path):
    """
    Query a port
    """
    status_code, response_data = execute_request(path, "GET", None, switch_ip)
    assert status_code == httplib.OK, "Wrong status code %s " % status_code

    assert response_data is not None, "Response data is empty"

    json_data = {}
    try:
        json_data = json.loads(response_data)
    except:
        assert False, "Malformed JSON"

    return json_data


def fill_with_function(f, n):
    list = [f for i in xrange(n)]
    return list


def random_mac():
    random.seed()
    mac = "%02x:%02x:%02x:%02x:%02x:%02x" % (random.randint(0, 255),
                                             random.randint(0, 255),
                                             random.randint(0, 255),
                                             random.randint(0, 255),
                                             random.randint(0, 255),
                                             random.randint(0, 255))
    return mac


def random_ip6_address():
    random.seed()
    ipv6 = ':'.join('{:x}'.format(random.randint(0, 2 ** 16 - 1))
                    for i in range(8))
    return ipv6


def login(dut, user_name, user_password):

    sslcontext = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    sslcontext.verify_mode = ssl.CERT_REQUIRED
    sslcontext.check_hostname = False
    src_path = os.path.dirname(os.path.realpath(__file__))
    src_file = os.path.join(src_path, 'server.crt')
    sslcontext.load_verify_locations(src_file)
    conn = httplib.HTTPSConnection(dut.SWITCH_IP, 443, context=sslcontext)
    url = '/login'

    body = {'username': user_name, 'password': user_password}
    headers = {"Content-type": "application/x-www-form-urlencoded",
               "Accept": "text/plain"}
    conn.request('POST', url, urllib.urlencode(body), headers)

    response = conn.getresponse()
    dut.HEADERS = {'Cookie': response.getheader('set-cookie')}

    status_code, response_data = response.status, response.read()
    conn.close()
    if not dut.HEADERS['Cookie'] is None:
        return True
    else:
        return False


def get_json(response_data):
    json_data = {}
    try:
        json_data = json.loads(response_data)
    except:
        assert False, "Malformed JSON"

    return json_data


def validate_keys_complete_object(json_data):
    assert json_data["configuration"] is not None, \
        "configuration key is not present"
    assert json_data["statistics"] is not None, \
        "statistics key is not present"
    assert json_data["status"] is not None, "status key is not present"

    return True


def rest_sanity_check(switch_ip):
    info("\nSwitch Sanity Check: Verify if System table row and bridge "
         "_normal exist\n")
    # Check if bridge_normal is ready, loop until ready or timeout finish
    system_path = "/rest/v1/system"
    bridge_path = "/rest/v1/system/bridges/bridge_normal"
    count = 1
    max_retries = 60  # 1 minute
    while count <= max_retries:
        info("\nSwitch Sanity Check: Try count %d \n" % count)
        status_system, response_system = execute_request(system_path, "GET",
                                                         None, switch_ip)
        status_bridge, response_bridge = execute_request(bridge_path, "GET",
                                                         None, switch_ip)
        if status_system is httplib.OK and response_system is not None and \
           status_bridge is httplib.OK and response_bridge is not None:
            break
        count += 1
        info("\nSwitch Sanity Check: Retrying\n")
        time.sleep(1)

    assert count <= max_retries, "Switch Sanity check failure: "\
        "After waiting %d seconds, the switch is still not ready to "\
        "run the tests" % max_retries
