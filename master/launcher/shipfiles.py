#!/usr/bin/env python

__doc__ = """
Ships file and folders to hosts in parallel.
"""


__author__ = "Mukil Kesavan"


import os
import sys
import time
import ConfigParser
import shlex
import subprocess
from threading import Thread


def error_exit(error_str):
    print error_str
    sys.exit(1)


def parse_spec():
    config = ConfigParser.ConfigParser()
    config.read(sys.argv[1].strip())    
    params = dict()

    if not config.has_section("common"):
        error_exit("ERROR: 'common' section not found in spec.")

    params['hostfile'] = config.get('common', 'HOSTFILE').strip()

    if not os.path.exists(params['hostfile']):
        error_exit("ERROR: Specified hostfile does not exist.")

    params['separator'] = config.get('common', 'SEPARATOR').strip().lower()
    params['hfile_nodenum_col'] = int(config.get('common', 'HOSTFILE_NODENUM_COL').strip())
    params['hfile_host_col'] = int(config.get('common', 'HOSTFILE_HOST_COL').strip())
    params['remote_ship_data_path'] = config.get('common', 'REMOTE_SHIP_DATA_PATH').strip()
    params['threads'] = int(config.get('common', 'NUM_THREADS').strip())
    params['connect_timeout'] = int(config.get('common', 'CONNECT_TIMEOUT_SECS').strip())
    params['remote_username'] = config.get('common', 'REMOTE_USERNAME').strip()
    params['local_ship_data_path'] = config.get('common', 'LOCAL_SHIP_DATA_PATH').strip()
    params['shipping_load_specs'] = False
    if config.get('common', 'SHIPPING_LOAD_SPECS').strip().lower() == 'yes':
        params['shipping_load_specs'] = True

    if not os.path.exists(params['local_ship_data_path']):
        error_exit("ERROR: Specified local data to ship does not exist.")
    elif params['shipping_load_specs'] and not os.path.isdir(params['local_ship_data_path']):
        error_exit("ERROR: shipping_load_specs set but local_ship_data_path is not a directory.")
    
    return params


def exec_cmd_timeout(cmdstr, timeout_secs):
        POLLING_GRANULARITY_SECS = 1
        seconds_passed = 0
        p = subprocess.Popen(cmdstr, shell=True)
        # poll for timeout or cmd completion.
        # for some reason the scp or ssh connection 
        # timeout parameter doesn't seem to work in all cases.
        while (p.poll() == None and seconds_passed < timeout_secs):
            time.sleep(POLLING_GRANULARITY_SECS)
            seconds_passed += POLLING_GRANULARITY_SECS
        if p.poll() == None:
            p.terminate()


def sshfunc(tlines, params):

    for i in range(len(tlines)):

        if len(tlines[i].strip()) <= 0 or tlines[i].strip()[0] == '#':
            continue
    
        hdesc = split_line(tlines[i].strip(), params['separator'])
        host = hdesc[params['hfile_host_col']].strip()
        nodenum = int(hdesc[params['hfile_nodenum_col']])

        localshipdata = params['local_ship_data_path'] + "/"

        if params['shipping_load_specs']:
            localshipdata += ("node" + str(nodenum) + ".dat")

        cmdstr = "scp -o ConnectTimeout=" + str(params['connect_timeout'])
        cmdstr += (" -r " + localshipdata + " " + params['remote_username'])
        cmdstr += ("@" + host + ":" + params['remote_ship_data_path'])
        exec_cmd_timeout(cmdstr, params['connect_timeout'])


def split_line(line, separator):
    if separator == 'whitespace':
        return shlex.split(line)
    elif separator == 'comma':
        return line.split(",")


def run():
    if len(sys.argv) < 2:
        error_exit("Usage: " + sys.argv[0] + " <spec-file>")

    print "Processing config parameters..."
    params = parse_spec()

    hf = open(params['hostfile'], "r")
    ffls = hf.readlines()
    
    t = []
    threads = params['threads']    
    threads = min(threads, len(ffls))
    step = max(1, (len(ffls)/threads) - 1)
    splits = range(0, len(ffls), step)[1:]
    splits[len(splits) - 1] = len(ffls)

    tstart = 0

    print "Shipping files..."
    for i in range(0, len(splits)):
            tend = splits[i]
            tlines = ffls[tstart:tend]
            th = Thread(target=sshfunc, args=(tlines, params, ))
            t.append(th)
            th.start()
            tstart = tend

    for th in t:
        th.join()

    print "DONE."


if __name__ == '__main__':
    run()
