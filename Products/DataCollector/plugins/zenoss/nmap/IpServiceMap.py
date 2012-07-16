###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2007, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

__doc__="""IpServiceMap

IpServiceMap uses nmap to model the list of listening TCP ports from any
device. It should be used when zenoss.snmp.IpServiceMap won't work due to
IPv6 listeners or if a device has no SNMP support.

"""

from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.ZenUtils.Utils import binPath
from twisted.internet.utils import getProcessOutput
from Products.ZenUtils.ZenTales import talesCompile, getEngine
import re

NMAPDEFAULTS = "-p 1-1024 -sT -oG -"
class IpServiceMap(PythonPlugin):
    
    transport = "python"
    maptype = "IpServiceMap"
    compname = "os"
    relname = "ipservices"
    modname = "Products.ZenModel.IpService"
    deviceProperties = PythonPlugin.deviceProperties + (
        'zNmapPortscanOptions',)

    def collect(self, device, log):
        nmapoptions = getattr(device, 'zNmapPortscanOptions', NMAPDEFAULTS) 
        #compile Tales expressions
        tales = readyopts = None
        try:
            tales = talesCompile('string:' + nmapoptions)
            readyopts = tales(getEngine().getContext({'here':device, 'device':device, 'dev':device}))
            readyopts = readyopts + " " + device.manageIp
        #if there was an error make a best effort
        except Exception, e:
            log.error("zNmapPortscanOptions contain illegal Tales expression, please review: %s" % e)
            readyopts = NMAPDEFAULTS + " " + device.manageIp
        nmapoptions = readyopts.split(" ") 
        log.info("running the following nmap command: %s %s" % \
                  (binPath('nmap'), " ".join(nmapoptions)))
        return getProcessOutput(binPath('nmap'), nmapoptions)


    def process(self, device, results, log):
        rm = self.relMap()
        lines = portMatch = None
        #determine grep-friendly vs. std. output
        if results.find("# Nmap") > -1:
            lines = results.split('\n')
            if lines[1]: 
                if 'Status:' in lines[1]:
                    lines = lines[2].split(" ")
                else:
                    lines = lines[1].split(" ")
            portMatch = re.compile('^(\d+)\/open\/tcp')
        else:
            portMatch = re.compile('^(\d+)\/tcp\s+open\s+')
            lines = results.split('\n')

        for section in lines:
            match = portMatch.search(section)
            if not match: continue
            port = int(match.groups()[0])
            om = self.objectMap()
            om.id = 'tcp_%05d' % port
            om.ipaddresses = ['0.0.0.0',]
            om.protocol = 'tcp'
            om.port = port
            om.setServiceClass = {'protocol': 'tcp', 'port':port}
            om.discoveryAgent = self.name()
            rm.append(om)

        if len(rm.maps) == 0:
            log.warn("No services found, or nmap output wasn't processed properly.")
        return rm

