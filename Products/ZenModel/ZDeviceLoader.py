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

__doc__="""ZDeviceLoader.py

load devices from a GUI screen in the ZMI

"""

import socket
from logging import StreamHandler, Formatter, getLogger
log = getLogger("zen.DeviceLoader")

from ipaddr import IPAddress

import transaction
from zope.interface import implements
from AccessControl import ClassSecurityInfo
from AccessControl import Permissions as permissions

from OFS.SimpleItem import SimpleItem

from Products.ZenUtils.Utils import isXmlRpc, setupLoggingHeader 
from Products.ZenUtils.Utils import binPath, clearWebLoggingStream
from Products.ZenUtils.IpUtil import getHostByName, ipwrap

from Products.ZenUtils.Exceptions import ZentinelException
from Products.ZenModel.Exceptions import DeviceExistsError, NoSnmp
from Products.ZenModel.Device import manage_createDevice
from Products.ZenWidgets import messaging
from Products.Jobber.interfaces import IJobStatus
from Products.Jobber.jobs import ShellCommandJob
from Products.Jobber.status import SUCCESS, FAILURE
from ZenModelItem import ZenModelItem
from zExceptions import BadRequest
from Products.ZenModel.interfaces import IDeviceLoader
from Products.ZenEvents.Event import Event


def manage_addZDeviceLoader(context, id="", REQUEST = None):
    """make a DeviceLoader"""
    if not id: id = "DeviceLoader"
    d = ZDeviceLoader(id)
    context._setObject(id, d)

    if REQUEST is not None:
        REQUEST['RESPONSE'].redirect(context.absolute_url()
                                     +'/manage_main')

class BaseDeviceLoader(object):
    implements(IDeviceLoader)

    context = None
    request = None
    deviceobj = None

    def __init__(self, context):
        self.context = context

    def run_zendisc(self, deviceName, devicePath, performanceMonitor):
        """
        Various ways of doing this should be implemented in subclasses.
        """
        raise NotImplementedError

    def cleanup(self):
        """
        Delete the device object, presumably because discovery failed.
        """
        if self.deviceobj is not None:
            try:
                self.deviceobj._p_jar.sync()
            except AttributeError:
                pass
            else:
                if self.deviceobj.isTempDevice(): 
                    # Flag's still True, so discovery failed somehow.  Clean up
                    # the device object.
                    self.deviceobj.deleteDevice(True, True, True)
                    self.deviceobj = None

    def load_device(self, deviceName, devicePath='/Discovered', 
                    discoverProto='snmp', performanceMonitor='localhost',
                    manageIp="", zProperties=None, deviceProperties=None):
        """
        Load a single device into the database.
        """
        # Make the config dictionaries the proper type
        try:
            if zProperties is None:
                zProperties = {}
            if deviceProperties is None:
                deviceProperties = {}

            # Remove spaces from the name
            deviceName = deviceName.replace(' ', '')
            manageIp = manageIp.replace(' ', '')

            # Check to see if we got passed in an IPv6 address
            try:
                ipv6addr = IPAddress(deviceName)
                manageIp = deviceName
                deviceName = ipwrap(deviceName)
                deviceProperties.setdefault('title', manageIp)
            except ValueError:
                pass

            # If we're not discovering and we have no IP, attempt the IP lookup
            # locally
            if discoverProto=='none':
                if not manageIp:
                    try:
                        manageIp = getHostByName(deviceName)
                    except socket.error:
                        pass

            # move the zProperties required by manage_createDevice to
            # deviceProperties
            for key in 'zSnmpCommunity', 'zSnmpPort', 'zSnmpVer':
                if zProperties.has_key(key):
                    deviceProperties[key] = zProperties.pop(key)

            # Make a device object in the database
            self.deviceobj = manage_createDevice(self.context, deviceName,
                                 devicePath,
                                 performanceMonitor=performanceMonitor,
                                 manageIp=manageIp,
                                 zProperties=zProperties,
                                 **deviceProperties)

            # Flag this device as temporary. If discovery goes well, zendisc will
            # flip this to False.
            self.deviceobj._temp_device = True

            # If we're not discovering, we're done
            if discoverProto=='none':
                return self.deviceobj

            # Otherwise, time for zendisc to do its thing
            self.run_zendisc(deviceName, devicePath, performanceMonitor)

        finally:
            # Check discovery's success and clean up accordingly
            self.cleanup()

        return self.deviceobj


class JobDeviceLoader(BaseDeviceLoader):
    implements(IDeviceLoader)

    def run_zendisc(self, deviceName, devicePath, performanceMonitor):
        """
        In this subclass, just commit to database,
        so everybody can find the new device
        """
        transaction.commit()

    def cleanup(self):
        """
        Delegate cleanup to the Job itself.
        """
        pass


class DeviceCreationJob(ShellCommandJob):
    def __init__(self, jobid, deviceName, devicePath="/Discovered", tag="",
                 serialNumber="", rackSlot=0, productionState=1000,
                 comments="", hwManufacturer="", hwProductName="",
                 osManufacturer="", osProductName="", locationPath="",
                 groupPaths=[], systemPaths=[], performanceMonitor="localhost",
                 discoverProto="snmp", priority=3, manageIp="",
                 zProperties=None, title=None, zendiscCmd=[]):

        # Store device name for later finding
        self.deviceName = deviceName
        self.devicePath = devicePath
        self.performanceMonitor = performanceMonitor
        self.discoverProto = discoverProto
        self.manageIp = manageIp.replace(' ', '')

        # Save the device stuff to set after adding
        self.zProperties = zProperties
        self.deviceProps = dict(tag=tag,
                          serialNumber=serialNumber,
                          rackSlot=rackSlot,
                          productionState=productionState,
                          comments=comments,
                          hwManufacturer=hwManufacturer,
                          hwProductName = hwProductName,
                          osManufacturer = osManufacturer,
                          osProductName = osProductName,
                          locationPath = locationPath,
                          groupPaths = groupPaths,
                          systemPaths = systemPaths,
                          priority = priority,
                          title= title)

        zendiscCmd.extend(['--job', jobid])
        super(DeviceCreationJob, self).__init__(jobid, zendiscCmd)


    def run(self, r):
        # Store zProperties on the job
        self.getStatus().setZProperties(**self.zProperties)

        self._v_loader = JobDeviceLoader(self)
        # Create the device object and generate the zendisc command
        try:
            self._v_loader.load_device(self.deviceName, self.devicePath,
                                    self.discoverProto,
                                    self.performanceMonitor, self.manageIp,
                                    self.zProperties, self.deviceProps)
            if self.discoverProto == 'none':
                #need to commit otherwise the status object will lose 
                #started time attribute and everything will break
                transaction.commit()
        except Exception, e:
            log.exception("Encountered error. Rolling back initial device add.")
            transaction.abort()
            job_log = self.getStatus().getLog()
            job_log.write(str(e.args[0]))
            job_log.finish()
            self.finished(FAILURE)
            transaction.commit()
        else:
            if self.discoverProto != 'none':
                super(DeviceCreationJob, self).run(r)
            else:
                job_log = self.getStatus().getLog()
                job_log.write("device added without modeling")
                job_log.finish()
                self.finished(SUCCESS)

    def finished(self, r):
        if self._v_loader.deviceobj is not None and r!=FAILURE:
            result = SUCCESS
            self.dmd.ZenEventManager.sendEvent(Event(
                    summary='Added device: '+self.deviceName,
                    severity=2, #info
                    eventClass='/Change/Add', #zEventAction=history
                    device=self.deviceName))
        else:
            result = FAILURE
        super(DeviceCreationJob, self).finished(result)

class WeblogDeviceLoader(BaseDeviceLoader):
    def __init__(self, context, request):
        self.context = context
        self.request = request

    def run_zendisc(self, deviceName, devicePath, performanceMonitor):
        # Commit to database so everybody can find the new device
        transaction.commit()
        collector = self.deviceobj.getPerformanceServer()
        collector._executeZenDiscCommand(deviceName, devicePath,
                                         performanceMonitor,
                                         REQUEST=self.request)


class ZDeviceLoader(ZenModelItem,SimpleItem):
    """Load devices into the DMD database"""

    portal_type = meta_type = 'DeviceLoader'

    manage_options = ((
            {'label':'ManualDeviceLoader', 'action':'manualDeviceLoader'},
            ) + SimpleItem.manage_options)


    security = ClassSecurityInfo()

    factory_type_information = (
        {
            'immediate_view' : 'addDevice',
            'actions'        :
            (
                { 'id'            : 'status'
                , 'name'          : 'Status'
                , 'action'        : 'addDevice'
                , 'permissions'   : (
                  permissions.view, )
                },
            )
        },
        )

    def __init__(self, id):
        self.id = id


    def loadDevice(self, deviceName, devicePath="/Discovered",
            tag="", serialNumber="",
            zSnmpCommunity="", zSnmpPort=161, zSnmpVer=None,
            rackSlot=0, productionState=1000, comments="",
            hwManufacturer="", hwProductName="",
            osManufacturer="", osProductName="",
            locationPath="", groupPaths=[], systemPaths=[],
            performanceMonitor="localhost",
            discoverProto="snmp",priority=3,REQUEST=None):
        """
        Load a device into the database connecting its major relations
        and collecting its configuration.
        """
        device = None
        if not deviceName: return self.callZenScreen(REQUEST)
        xmlrpc = isXmlRpc(REQUEST)
        if REQUEST and not xmlrpc:
            handler = setupLoggingHeader(self, REQUEST)

        loader = WeblogDeviceLoader(self, REQUEST)

        try:
            device = loader.load_device(deviceName, devicePath, discoverProto,
                                        performanceMonitor,
                                        zProperties=dict(
                                            zSnmpCommunity=zSnmpCommunity,
                                            zSnmpPort=zSnmpPort,
                                            zSnmpVer=zSnmpVer
                                        ),
                                        deviceProperties=dict(
                                            tag=tag,
                                            serialNumber=serialNumber,
                                            rackSlot=rackSlot,
                                            productionState=productionState,
                                            comments=comments,
                                            hwManufacturer=hwManufacturer,
                                            hwProductName=hwProductName,
                                            osManufacturer=osManufacturer,
                                            osProductName=osProductName,
                                            locationPath=locationPath,
                                            groupPaths=groupPaths,
                                            systemPaths=systemPaths,
                                            priority=priority
                                        ))
        except (SystemExit, KeyboardInterrupt): 
            raise
        except ZentinelException, e:
            log.info(e)
            if xmlrpc: return 1
        except DeviceExistsError, e:
            log.info(e)
            if xmlrpc: return 2
        except NoSnmp, e:
            log.info(e)
            if xmlrpc: return 3
        except Exception, e:
            log.exception(e)
            log.exception('load of device %s failed' % deviceName)
            transaction.abort()
        if device is None:
            log.error("Unable to add the device %s" % deviceName)
        else:
            log.info("Device %s loaded!" % deviceName)

        if REQUEST and not xmlrpc:
            self.loaderFooter(device, REQUEST.RESPONSE)
            clearWebLoggingStream(handler)
        if xmlrpc: return 0

    def addManufacturer(self, newHWManufacturerName=None,
                        newSWManufacturerName=None, REQUEST=None):
        """add a manufacturer to the database"""
        mname = newHWManufacturerName
        field = 'hwManufacturer'
        if not mname:
            mname = newSWManufacturerName
            field = 'osManufacturer'
        try:
            self.getDmdRoot("Manufacturers").createManufacturer(mname)
        except BadRequest, e:
            if REQUEST:
                messaging.IMessageSender(self).sendToBrowser(
                    'Error',
                    str(e),
                    priority=messaging.WARNING
                )
            else:
                raise e

        if REQUEST:
            REQUEST[field] = mname
            return self.callZenScreen(REQUEST)


    security.declareProtected('Change Device', 'setHWProduct')
    def setHWProduct(self, newHWProductName, hwManufacturer, REQUEST=None):
        """set the productName of this device"""
        if not hwManufacturer and REQUEST:
            messaging.IMessageSender(self).sendToBrowser(
                'Error',
                'Please select a HW Manufacturer',
                priority=messaging.WARNING
            )
            return self.callZenScreen(REQUEST) 

        self.getDmdRoot("Manufacturers").createHardwareProduct(
                                        newHWProductName, hwManufacturer)
        if REQUEST:
            REQUEST['hwProductName'] = newHWProductName
            return self.callZenScreen(REQUEST)


    security.declareProtected('Change Device', 'setOSProduct')
    def setOSProduct(self, newOSProductName, osManufacturer, REQUEST=None):
        """set the productName of this device"""
        if not osManufacturer and REQUEST:
            messaging.IMessageSender(self).sendToBrowser(
                'Error',
                'Please select an OS Manufacturer.',
                priority=messaging.WARNING
            )
            return self.callZenScreen(REQUEST)

        self.getDmdRoot("Manufacturers").createSoftwareProduct(
                                        newOSProductName, osManufacturer, isOS=True)
        if REQUEST:
            REQUEST['osProductName'] = newOSProductName
            return self.callZenScreen(REQUEST)


    security.declareProtected('Change Device', 'addLocation')
    def addLocation(self, newLocationPath, REQUEST=None):
        """add a location to the database"""
        try:
            self.getDmdRoot("Locations").createOrganizer(newLocationPath)
        except BadRequest, e:
            if REQUEST:
                messaging.IMessageSender(self).sendToBrowser(
                    'Error',
                    str(e),
                    priority=messaging.WARNING
                )
            else: 
                raise e
            
        if REQUEST:
            REQUEST['locationPath'] = newLocationPath
            return self.callZenScreen(REQUEST)


    security.declareProtected('Change Device', 'addSystem')
    def addSystem(self, newSystemPath, REQUEST=None):
        """add a system to the database"""
        try:
            self.getDmdRoot("Systems").createOrganizer(newSystemPath)
        except BadRequest, e:
            if REQUEST:
                messaging.IMessageSender(self).sendToBrowser(
                    'Error',
                    str(e),
                    priority=messaging.WARNING
                )
            else: 
                raise e

        syss = REQUEST.get('systemPaths', [])
        syss.append(newSystemPath)
        if REQUEST:
            REQUEST['systemPaths'] = syss
            return self.callZenScreen(REQUEST)


    security.declareProtected('Change Device', 'addDeviceGroup')
    def addDeviceGroup(self, newDeviceGroupPath, REQUEST=None):
        """add a device group to the database"""
        try:
            self.getDmdRoot("Groups").createOrganizer(newDeviceGroupPath)
        except BadRequest, e:
            if REQUEST:
                messaging.IMessageSender(self).sendToBrowser(
                    'Error',
                    str(e),
                    priority=messaging.WARNING
                )
            else: 
                raise e

        groups = REQUEST.get('groupPaths', [])
        groups.append(newDeviceGroupPath)
        if REQUEST:
            REQUEST['groupPaths'] = groups
            return self.callZenScreen(REQUEST)


    security.declareProtected('Change Device', 'setPerformanceMonitor')
    def setPerformanceMonitor(self, newPerformanceMonitor, REQUEST=None):
        """add new performance monitor to the database"""
        try:
            self.getDmdRoot("Monitors").getPerformanceMonitor(newPerformanceMonitor)
        except BadRequest, e:
            if REQUEST:
                messaging.IMessageSender(self).sendToBrowser(
                    'Error',
                    str(e),
                    priority=messaging.WARNING
                )
            else: 
                raise e 
        if REQUEST:
            REQUEST['performanceMonitor'] = newPerformanceMonitor
            return self.callZenScreen(REQUEST)


    def setupLog(self, response):
        """setup logging package to send to browser"""
        root = getLogger()
        self._v_handler = StreamHandler(response)
        fmt = Formatter("""<tr class="tablevalues">
        <td>%(asctime)s</td><td>%(levelname)s</td>
        <td>%(name)s</td><td>%(message)s</td></tr>
        """, "%Y-%m-%d %H:%M:%S")
        self._v_handler.setFormatter(fmt)
        root.addHandler(self._v_handler)
        root.setLevel(10)


    def clearLog(self):
        alog = getLogger()
        if getattr(self, "_v_handler", False):
            alog.removeHandler(self._v_handler)


    def loaderFooter(self, devObj, response):
        """add navigation links to the end of the loader output"""
        if not devObj: return
        devurl = devObj.absolute_url()
        response.write("""<tr class="tableheader"><td colspan="4">
            Navigate to device <a href=%s>%s</a></td></tr>""" 
            % (devurl, devObj.getId()))
        response.write("</table></body></html>")
