#!/usr/bin/env python

__doc__ = """
Sets up simulation cron jobs on all remote nodes.
"""


__author__ = "Mukil Kesavan"


import os
import sys
import time
import ConfigParser
import shlex
import subprocess
from threading import Thread
from datetime import datetime as dt


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
    params['install_path_remote'] = config.get('common', 'INSTALL_PATH_REMOTE').strip()
    params['threads'] = int(config.get('common', 'NUM_THREADS').strip())
    params['connect_timeout'] = int(config.get('common', 'CONNECT_TIMEOUT_SECS').strip())
    params['remote_username'] = config.get('common', 'REMOTE_USERNAME').strip()
    datestr = config.get('common', 'LAUNCH_DATE').strip()
    timestr = config.get('common', 'LAUNCH_TIME').strip()
    params['launch_dt'] = dt.strptime(datestr + " " + timestr, "%Y-%m-%d %H:%M:%S")
    datestr = config.get('common', 'END_DATE').strip()
    timestr = config.get('common', 'END_TIME').strip()
    params['end_dt'] = dt.strptime(datestr + " " + timestr, "%Y-%m-%d %H:%M:%S")
    params['lgen_threads'] = int(config.get('loadgen', 'NUM_LGEN_THREADS').strip())
    params['loop_len_us'] = int(config.get('loadgen', 'SMALLEST_LOOP_LENGTH_US').strip())
    params['recalibrate'] = False
    if config.get('loadgen', 'RECALIBRATE_PERIODICALLY').strip().lower() == "yes":
        params['recalibrate'] = True
    
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

        lgencmd = params['install_path_remote'] + "/wileE -l "
        lgencmd += (str(params['loop_len_us']) + " -f ")
        lgencmd += (params['install_path_remote'] + "/node" + str(nodenum) + ".dat")
        lgencmd += (" -t " + str(params['lgen_threads']))
        if params['recalibrate']:
            lgencmd += (" --recalibrate")
        lgencmd += (" > /dev/null")

        start_dt_str = params['launch_dt'].strftime("%M %H %d %m")
        end_dt_str = params['end_dt'].strftime("%M %H %d %m")

        fullcmd = "nohup " + params['install_path_remote'] + "/setupcron.sh "
        fullcmd += (start_dt_str + " \'" + lgencmd + "\' " + end_dt_str)
        fullcmd += (" \'pkill -9 wileE\'")
        
        cmdstr = "ssh -o ConnectTimeout=" + str(params['connect_timeout'])
        cmdstr += (" " + params['remote_username'])
        cmdstr += ("@" + host + " \"" + fullcmd + " &\" ")
        
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

    print "Setting up worker nodes..."
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
