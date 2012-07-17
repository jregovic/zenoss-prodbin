###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2011, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################
import re
from hashlib import md5
import logging
from cStringIO import StringIO
from zope.interface import implements
from Products.ZenModel.DeviceClass import DeviceClass
from Products.ZenModel.IpAddress import IpAddress
from Products.ZenModel.IpNetwork import IpNetwork
from Products.ZenModel.OSProcessOrganizer import OSProcessOrganizer
from Products.ZenModel.OSProcessClass import OSProcessClass
from Products.Zuul.interfaces import ICatalogTool

from .interfaces import IInvalidationFilter, FILTER_EXCLUDE, FILTER_CONTINUE

log = logging.getLogger('zen.InvalidationFilter')


class IpInvalidationFilter(object):
    implements(IInvalidationFilter)

    def initialize(self, context):
        pass

    def include(self, obj):
        if isinstance(obj, (IpAddress, IpNetwork)):
            return FILTER_EXCLUDE
        return FILTER_CONTINUE


class BaseOrganizerFilter(object):
    """
    Base invalidation filter for organizers. Calculates a checksum for
    the organizer based on its sorted z/c properties.
    """
    implements(IInvalidationFilter)

    weight = 10
    iszorcustprop = re.compile("^[zc][A-Z]").search

    def __init__(self, types):
        self._types = types

    def getRoot(self, context):
        return context.dmd.primaryAq()

    def initialize(self, context):
        root = self.getRoot(context)
        brains = ICatalogTool(root).search(self._types)
        results = {}
        for brain in brains:
            obj = brain.getObject()
            results[brain.getPath()] = self.organizerChecksum(obj)
        self.checksum_map = results

    def getZorCProperties(self, organizer):
        for zId in sorted(organizer.zenPropertyIds(pfilt=self.iszorcustprop)):
            if organizer.zenPropIsPassword(zId):
                propertyString = organizer.getProperty(zId, '')
            else:
                propertyString = organizer.zenPropertyString(zId)
            yield zId, propertyString

    def generateChecksum(self, organizer, md5_checksum):
        # Checksum all zProperties and custom properties
        for zId, propertyString in self.getZorCProperties(organizer):
            md5_checksum.update('%s|%s' % (zId, propertyString))

    def organizerChecksum(self, organizer):
        m = md5()
        self.generateChecksum(organizer, m)
        return m.hexdigest()

    def include(self, obj):
        # Move on if it's not one of our types
        if not isinstance(obj, self._types):
            return FILTER_CONTINUE

        # Checksum the device class
        current_checksum = self.organizerChecksum(obj)
        organizer_path = '/'.join(obj.getPrimaryPath())

        # Get what we have right now and compare
        existing_checksum = self.checksum_map.get(organizer_path)
        if current_checksum != existing_checksum:
            log.debug('%r has a new checksum! Including.', obj)
            self.checksum_map[organizer_path] = current_checksum
            return FILTER_CONTINUE
        log.debug('%r checksum unchanged. Skipping.', obj)
        return FILTER_EXCLUDE


class DeviceClassInvalidationFilter(BaseOrganizerFilter):
    """
    Subclass of BaseOrganizerFilter with specific logic for
    Device classes. Uses both z/c properties as well as locally
    bound RRD templates to create the checksum.
    """

    def __init__(self):
        super(DeviceClassInvalidationFilter, self).__init__((DeviceClass,))

    def getRoot(self, context):
        return context.dmd.Devices.primaryAq()

    def generateChecksum(self, organizer, md5_checksum):
        """
        Generate a checksum representing the state of the device class as it
        pertains to configuration. This takes into account templates and
        zProperties, nothing more.
        """
        s = StringIO()
        # Checksum includes all bound templates
        for tpl in organizer.rrdTemplates():
            s.seek(0)
            s.truncate()
            # TODO: exportXml is a bit of a hack. Sorted, etc. would be better.
            tpl.exportXml(s)
            md5_checksum.update(s.getvalue())
        # Include z/c properties from base class
        super(DeviceClassInvalidationFilter, self).generateChecksum(organizer, md5_checksum)


class OSProcessOrganizerFilter(BaseOrganizerFilter):
    """
    Invalidation filter for OSProcessOrganizer objects. This filter only
    looks at z/c properties defined on the organizer.
    """

    def __init__(self):
        super(OSProcessOrganizerFilter, self).__init__((OSProcessOrganizer,))

    def getRoot(self, context):
        return context.dmd.Processes.primaryAq()


class OSProcessClassFilter(BaseOrganizerFilter):
    """
    Invalidation filter for OSProcessClass objects. This filter uses
    z/c properties as well as local _properties defined on the organizer
    to create a checksum.
    """

    def __init__(self):
        super(OSProcessClassFilter, self).__init__((OSProcessClass,))

    def getRoot(self, context):
        return context.dmd.Processes.primaryAq()

    def generateChecksum(self, organizer, md5_checksum):
        # Include properties of OSProcessClass
        for prop in organizer._properties:
            prop_id = prop['id']
            md5_checksum.update("%s|%s" % (prop_id, getattr(organizer, prop_id, '')))
        # Include z/c properties from base class
        super(OSProcessClassFilter, self).generateChecksum(organizer, md5_checksum)
