#!/usr/bin/env python

__doc__ = """
Takes a global load specification and produces per
simulation node load specification.
"""


__author__ = "Mukil Kesavan"


import os
import sys
import numpy
import ConfigParser
import shlex
import math
import random


def error_exit(error_str):
    print error_str
    sys.exit(1)


def parse_spec():
    config = ConfigParser.ConfigParser()
    config.read(sys.argv[1].strip())    
    params = dict()

    if not config.has_section("common"):
        error_exit("ERROR: 'common' section not found in spec.")

    params['type'] = config.get('common', 'TYPE').strip().lower()
    
    if params['type'] == "trace" and config.has_section("trace"):
        params['data_file'] = config.get('trace', 'DATA_FILE').strip()
        params['separator'] = config.get('trace', 'SEPARATOR').strip().lower()
        params['timestamp_col'] = int(config.get('trace', 'TIMESTAMP_COL').strip())
        params['item_id_col'] = int(config.get('trace', 'ITEM_IDENTIFIER_COL').strip())
        params['cpu_col'] = int(config.get('trace', 'CPU_COL').strip())
        params['mem_col'] = int(config.get('trace', 'MEM_COL').strip())
        params['cpu_util_format'] = config.get('trace', 'CPU_UTIL_FORMAT').strip().lower()
        params['mem_util_format'] = config.get('trace', 'MEM_UTIL_FORMAT').strip().lower()
        params['mem_limit_pct'] = int(config.get('trace', 'MEM_LIMIT_PCT').strip())
    elif params['type'] == "statistical" and config.has_section("statistical"):
        params['workload_file_cpu'] = config.get('statistical', 'WORKLOAD_DESC_FILE_CPU').strip()
        params['workload_file_mem'] = config.get('statistical', 'WORKLOAD_DESC_FILE_MEM').strip()
        params['distribution_cpu'] = config.get('statistical', 'DISTRIBUTION_CPU').strip().lower()
        params['distribution_mem'] = config.get('statistical', 'DISTRIBUTION_MEM').strip().lower()
        params['separator'] = config.get('statistical', 'SEPARATOR').strip().lower()
        params['duration_mins'] = int(config.get('statistical', 'WORKLOAD_DURATION_MINS').strip())
        params['mem_limit_pct'] = int(config.get('statistical', 'MEM_LIMIT_PCT').strip())
        if params['distribution_cpu'] == "gaussian" or params['distribution_mem'] == "gaussian":
            params['mean_col'] = int(config.get('statistical', 'GAUSSIAN_MEAN_COL').strip()) 
            params['stdev_col'] = int(config.get('statistical', 'GAUSSIAN_STDEV_COL').strip())
        if params['distribution_cpu'] == "uniform" or params['distribution_mem'] == "uniform":
            params['min_col'] = int(config.get('statistical', 'UNIFORM_MIN_COL').strip())
            params['max_col'] = int(config.get('statistical', 'UNIFORM_MAX_COL').strip())
    else:
        error_exit("ERROR: Invalid or incomplete configuration file.")

    if not config.has_section("target"):
        error_exit("ERROR: 'target' section not found in spec.")
    params['nodes'] = int(config.get('target', 'NODES').strip())
    params['tp_duration_secs'] = int(config.get('target', 'TIMEPOINT_DURATION_SECS').strip())
    params['out_dir'] = config.get('target', 'OUTPUT_DIRECTORY').strip()

    if config.has_section("spike"):
        params['has_spike'] = True
        params['spk_desc_file'] = config.get('spike', 'SPIKES_DESC_FILE').strip()
        params['spk_file_separator'] = config.get('spike', 'SEPARATOR').strip().lower()
        params['spk_start_node_col'] = int(config.get('spike', 'START_NODE_COL').strip()) 
        params['spk_end_node_col'] = int(config.get('spike', 'END_NODE_COL').strip()) 
        params['spk_resource_col'] = int(config.get('spike', 'SPIKE_RESOURCE_COL').strip()) 
        params['spk_time_start_col'] = int(config.get('spike', 'TIME_SPIKE_START_COL').strip()) 
        params['spk_time_peak_start_col'] = int(config.get('spike', 'TIME_PEAK_START_COL').strip()) 
        params['spk_time_peak_end_col'] = int(config.get('spike', 'TIME_PEAK_END_COL').strip()) 
        params['spk_time_spike_end_col'] = int(config.get('spike', 'TIME_SPIKE_END_COL').strip()) 
        params['spk_magnitude_col'] = int(config.get('spike', 'SPIKE_MAGNITUDE_MULTIPLIER_COL').strip())
    else:
        params['has_spike'] = False
        
    return params


def count_items(itemdict):
    items = 0
    for k in itemdict.keys():
        items += (len(itemdict[k]['cpu']))
    return items


def get_dict_items_by_count(itemdict, count):
    seen = 0
    for k in itemdict.keys():
        # assuming equal number of cpu and mem util values
        if (seen + len(itemdict[k]['cpu'])) > count:
            return (itemdict[k]['cpu'][(count - seen)],
                    itemdict[k]['mem'][(count - seen)])
        seen += len(itemdict[k]['cpu'])
    return None, None


def normalize_to_max(data_list, maxval, limitpct):
    limitpct = float(limitpct)
    if maxval > 0:
        for i in range(len(data_list)):
            try:
                data_list[i] = int(round(((data_list[i] * limitpct) / maxval), 0))
            except Exception as e:
                pass            
    return data_list


def get_max_2d(data):
    if len(data) <= 0:
        return None
    maxv = max(data[0])
    for ll in data:
        if maxv < max(ll):
            maxv = max(ll)
    return maxv


def write_utils_to_file(allnodescpu, allnodesmem, params):

    if allnodescpu is None or allnodesmem is None:
        return

    if len(allnodescpu) <= 0 or len(allnodesmem) <= 0:
        return

    cpumax = get_max_2d(allnodescpu)
    memmax = get_max_2d(allnodesmem)

    # each target node
    for i in range(len(allnodescpu)):
        filename = params['out_dir'] + "/" + "node" + str(i) + ".dat"
        outf = open(filename, "w")
        # utils for this node
        nodecpu = allnodescpu[i]
        nodemem = allnodesmem[i]

        for j in range(len(nodecpu)):
            outstr = (str(params['tp_duration_secs']) + "\t")
            outstr += (str(int(nodecpu[j])) + "\t")
            outstr += (str(int(nodemem[j])) + "\n")
            outf.write(outstr)
        outf.close()
    

def prepare_utils_for_output(cpu, mem, params):

    if cpu is None or mem is None or len(cpu) <= 0 or len(mem) <= 0:
        return

    allnodescpu = zip(*cpu)
    allnodesmem = zip(*mem)
    cpumax = get_max_2d(allnodescpu)
    memmax = get_max_2d(allnodesmem)
    memlimitpct = params['mem_limit_pct']

    # each target node
    for i in range(len(allnodescpu)):
        # utils for this node
        nodecpu = allnodescpu[i]
        nodemem = allnodesmem[i]
        if params['cpu_util_format'] == "relative":
            # CPU use can get up to 100% in per-node loadgen
            nodecpu = normalize_to_max(list(allnodescpu[i]), cpumax, 100)
        if params['mem_util_format'] == "relative":
            nodemem = normalize_to_max(list(allnodesmem[i]), memmax, memlimitpct)

        allnodescpu[i] = nodecpu
        allnodesmem[i] = nodemem

    return allnodescpu, allnodesmem

        
def split_line(line, separator):
    if separator == 'whitespace':
        return shlex.split(line)
    elif separator == 'comma':
        return line.split(",")


def process_trace_file(params):

    if not os.path.exists(params['data_file']):
        error_exit("ERROR: Specified data file does not exist.")

    ifp = open(params['data_file'], "r")
    reftime = None
    cpuutilsbytime = []
    memutilsbytime = []
    items = dict()
    
    while True:
        gline = ifp.readline().strip()
        if len(gline) <= 0:
            break
        elif gline[0] == "#":
            continue
        
        gdata = split_line(gline, params['separator'])

        if reftime is None:
            reftime = int(gdata[0])            

        if reftime < int(gdata[0]):        
            cur_tp_cpuutils = numpy.zeros(params['nodes'])
            cur_tp_memutils = numpy.zeros(params['nodes'])

            if count_items(items) < params['nodes']:
                nodesperitem = int(math.ceil(float(params['nodes']) / count_items(items)))
                for n in range(len(cur_tp_cpuutils)):
                    count = int(math.ceil(float(n)/nodesperitem))
                    cur_tp_cpuutils[n], cur_tp_memutils[n] = get_dict_items_by_count(items, count)
            else: # more items than target nodes
                itemspernode = int(math.ceil(float(count_items(items)) / params['nodes']))
                itcount = 0
                for it in items.keys():
                    itcpulist = items[it]['cpu']
                    itmemlist = items[it]['mem']
                    # assuming equal number of cpu and mem util values
                    for i in range(len(itcpulist)):
                        index = int(math.ceil(float(itcount) / itemspernode))
                        index = min(index, len(cur_tp_cpuutils) - 1)
                        cur_tp_cpuutils[index] += itcpulist[i]
                        cur_tp_memutils[index] += itmemlist[i]
                        itcount += 1

            cpuutilsbytime.append(cur_tp_cpuutils)
            memutilsbytime.append(cur_tp_memutils)
                        
            items = dict()
            reftime = int(gdata[0])
        elif reftime == int(gdata[0]):
            itid = gdata[params['item_id_col']].strip()
            try:
                items[itid]['cpu'].append(float(gdata[params['cpu_col']]))
                items[itid]['mem'].append(float(gdata[params['mem_col']]))
            except KeyError, e:
                items[itid] = dict()
                items[itid]['cpu'] = [float(gdata[params['cpu_col']])]
                items[itid]['mem'] = [float(gdata[params['mem_col']])]

    ifp.close()
    return cpuutilsbytime, memutilsbytime


def get_rand_value(speclist, distribution, params, max_util_limit):
    retval = None
    if distribution == "gaussian":
        mean = float(speclist[params['mean_col']].strip())
        deviation = float(speclist[params['stdev_col']].strip())
        retval = int(math.ceil(random.gauss(mean, deviation)))
    elif distribution == "uniform":
        minv = float(speclist[params['min_col']].strip())
        maxv = float(speclist[params['max_col']].strip())
        retval = int(math.ceil(random.uniform(minv, maxv)))
    # utilization can't be greater than limit or less than 0
    return min(max(0, retval), max_util_limit)


def generate_stat_utils(resource, params):
    ifp = None
    limit_pct = 100
    distribution = None
    nodeutils = []
    wkutils = []
    
    if resource == "cpu":
        if not os.path.exists(params['workload_file_cpu']):
            error_exit("ERROR: Specified data file does not exist.")
        ifp = open(params['workload_file_cpu'], "r")
        distribution = params['distribution_cpu']
    elif resource == "mem":
        if not os.path.exists(params['workload_file_mem']):
            error_exit("ERROR: Specified data file does not exist.")
        ifp = open(params['workload_file_mem'], "r")
        limit_pct = params['mem_limit_pct']
        distribution = params['distribution_mem']

    numsamples = int(math.ceil((params['duration_mins'] * 60) / params['tp_duration_secs']))
                   
    while True:
        gline = ifp.readline().strip()
        if len(gline) <= 0:
            break
        elif gline[0] == "#":
            continue
        gd = split_line(gline, params['separator'])
        utils = numpy.zeros(numsamples)
        for i in range(numsamples):
            utils[i] = get_rand_value(gd, distribution, params, limit_pct)
        wkutils.append(utils)

    # evenly divide available workload utils between nodes
    if len(wkutils) < params['nodes']:
        nodesperwk = int(math.ceil(float(params['nodes']) / len(wkutils)))
        for n in range(params['nodes']):
            index = min(int(math.ceil(float(n) / nodesperwk)), len(wkutils)-1)
            nodeutils.append(wkutils[index])
    else:
        # evenly divide available nodes among workload utils
        wkspernode = int(math.ceil(float(len(wkutils)) / params['nodes']))
        for n in range(params['nodes']):
            nodeutils.append(numpy.zeros(numsamples))
            start_wk = n * wkspernode
            end_wk = min(start_wk + wkspernode, len(wkutils))
            for w in range(start_wk, end_wk):
                nodeutils[n] = nodeutils[n] + wkutils[w]
            # remap combined values to (0, 100) range
            nodeutils[n] = normalize_to_max(nodeutils[n], max(nodeutils[n]), limit_pct)

    ifp.close()
    return nodeutils


def add_spike_to_utils(resutils, t_spikestart, t_peakstart, t_peakend, t_spikeend, mag, limitpct):

    if t_spikestart < 0 or t_peakstart < 0 or t_peakstart < 0\
            or t_peakend < 0 or t_spikeend < 0 or mag <= 0 or \
            limitpct <= 0 or limitpct > 100:
        print "Error in spike parameter(s)."
        return resutils

    if resutils is None or len(resutils) <= 0:
        return resutils

    spike_startval = resutils[t_spikestart]
    peaktargetutil = min((spike_startval * mag), limitpct)
    peaktargetutil = int(math.ceil(peaktargetutil))

    # m = (y - b)/x
    slopetopeak = int(math.ceil((peaktargetutil - spike_startval) / float(t_peakstart - t_spikestart)))
    slopetonormal = int(math.ceil((peaktargetutil - spike_startval) / float(t_spikeend - t_peakend)))

    ## spike to peak
    for i in range(t_spikestart + 1, t_peakstart):
        # y = mx + b
        resutils[i] = resutils[i] + (slopetopeak * (i - t_spikestart))
        resutils[i] = min(resutils[i], limitpct)
    ## the peak - hold max value
    for i in range(t_peakstart, t_peakend):
        resutils[i] = resutils[i] + (slopetopeak * (t_peakstart - t_spikestart))
        resutils[i] = min(resutils[i], limitpct)
    ## slope to normalcy
    for i in range(t_peakend, t_spikeend):
        # y = mx + b
        resutils[i] = resutils[i] + (slopetopeak * (t_peakstart - t_spikestart))
        resutils[i] = min(resutils[i], limitpct)
        resutils[i] = resutils[i] - (slopetonormal * (i - t_peakend))
        resutils[i] = max(resutils[i], 0)

    return resutils


def process_spike_file(params, allnodescpu, allnodesmem):

    if not os.path.exists(params['spk_desc_file']):
        error_exit("ERROR: Specified data file does not exist.")

    if allnodescpu is None or allnodesmem is None:
        return allnodescpu, allnodesmem

    if len(allnodescpu) <= 0 or len(allnodesmem) <= 0:
        return allnodescpu, allnodesmem
        
    ifp = open(params['spk_desc_file'], "r")
    while True:
        gline = ifp.readline().strip()
        if len(gline) <= 0:
            break
        elif gline[0] == "#":
            continue        
        gd = split_line(gline, params['spk_file_separator'])

        t_ss = int(gd[params['spk_time_start_col']].strip())
        t_ss = int(math.ceil(float(t_ss) / params['tp_duration_secs']))
        t_ps = int(gd[params['spk_time_peak_start_col']].strip())
        t_ps = int(math.ceil(float(t_ps) / params['tp_duration_secs']))
        t_pe = int(gd[params['spk_time_peak_end_col']].strip())
        t_pe = int(math.ceil(float(t_pe) / params['tp_duration_secs']))
        t_se = int(gd[params['spk_time_spike_end_col']].strip())
        t_se = int(math.ceil(float(t_se) / params['tp_duration_secs']))
        magmul = float(gd[params['spk_magnitude_col']].strip())
        limitpct = 100

        # assuming equal number of cpu and mem samples
        if t_ss >= len(allnodescpu) or t_ps >= len(allnodescpu) or \
                t_pe >= len(allnodescpu) or t_se >= len(allnodescpu):
            print "Error: Invalid spike parameters in line:"
            print ("\t" + gline)
            continue

        if gd[params['spk_resource_col']].lower().strip() == "cpu":
            s = int(gd[params['spk_start_node_col']].strip())
            e = int(gd[params['spk_end_node_col']].strip()) + 1
            if s < 0 or e >= params['nodes']:
                error_exit("Error: Invalid nodes in spike specification.")
            for i in range(s, e):
                allnodescpu[i] = add_spike_to_utils(allnodescpu[i], t_ss, t_ps, t_pe, t_se, magmul, limitpct)
        elif gd[params['spk_resource_col']].lower().strip() == "mem":
            s = int(gd[params['spk_start_node_col']].strip())
            e = int(gd[params['spk_end_node_col']].strip()) + 1
            limitpct = params['mem_limit_pct']
            if s < 0 or e >= params['nodes']:
                error_exit("Error: Invalid nodes in spike specification.")
            for i in range(s, e):
                allnodesmem[i] = add_spike_to_utils(allnodesmem[i], t_ss, t_ps, t_pe, t_se, magmul, limitpct)

    return allnodescpu, allnodesmem


def run():
    if len(sys.argv) < 2:
        error_exit("Usage: " + sys.argv[0] + " <spec-file>")

    print "Processing config parameters..."        
    params = parse_spec()

    print "Computing utilizations..."
    allnodescpu = None
    allnodesmem = None
    if params['type'] == "trace":
        cpubytime, membytime = process_trace_file(params)
        allnodescpu, allnodesmem = prepare_utils_for_output(cpubytime, membytime, params)
    elif params['type'] == "statistical":
        allnodescpu = generate_stat_utils("cpu", params)
        allnodesmem = generate_stat_utils("mem", params)

    if params['has_spike']:
        print "Adding volume spike(s)..."
        allnodescpu, allnodesmem = process_spike_file(params, allnodescpu, allnodesmem)
        
    print "Writing load files..."
    write_utils_to_file(allnodescpu, allnodesmem, params)
    print "DONE"

   
if __name__ == '__main__':
    run()
