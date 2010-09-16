###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2009, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 as published by
# the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################
"""
Operations for Processes.

Available at:  /zport/dmd/process_router
"""

from Products import Zuul
from Products.Zuul.decorators import require
from Products.Zuul.routers import TreeRouter
from Products.ZenUtils.Ext import DirectResponse

class ProcessRouter(TreeRouter):
    """
    A JSON/ExtDirect interface to operations on processes
    """

    def _getFacade(self):
        return Zuul.getFacade('process', self.context)

    def getTree(self, id):
        """
        Returns the tree structure of an organizer hierarchy where
        the root node is the organizer identified by the id parameter.

        @type  id: string
        @param id: Id of the root node of the tree to be returned
        @rtype:   [dictionary]
        @return:  Object representing the tree
        """
        facade = self._getFacade()
        tree = facade.getTree(id)
        data = Zuul.marshal(tree)
        return [data]

    def moveProcess(self, uid, targetUid):
        """
        Move a process or organizer from one organizer to another.

        @type  uid: string
        @param uid: UID of the process or organizer to move
        @type  targetUid: string
        @param targetUid: UID of the organizer to move to
        @rtype:   DirectResponse
        @return:  B{Properties}:
           - uid: (dictionary) The new uid for moved process or organizer
        """
        facade = self._getFacade()
        primaryPath = facade.moveProcess(uid, targetUid)
        id = '.'.join(primaryPath)
        uid = '/'.join(primaryPath)
        return DirectResponse.succeed(uid=uid, id=id)

    def getInfo(self, uid, keys=None):
        """
        Get the properties of a process.

        @type  uid: string
        @param uid: Unique identifier of a process
        @type  keys: list
        @param keys: (optional) List of keys to include in the returned
                     dictionary. If None then all keys will be returned
                     (default: None)
        @rtype:   DirectResponse
        @return:  B{Properties}
            - data: (dictionary) Object representing a process's properties
        """
        facade = self._getFacade()
        process = facade.getInfo(uid)
        data = Zuul.marshal(process, keys)
        return DirectResponse.succeed(data=data)

    @require('Manage DMD')
    def setInfo(self, **data):
        """
        Set attributes on a process.
        This method accepts any keyword argument for the property that you wish
        to set. The only required property is "uid".

        @type    uid: string
        @keyword uid: Unique identifier of a process
        @rtype:   DirectResponse
        @return:  B{Properties}
            - data: (dictionary) Object representing a process's new properties
        """
        facade = self._getFacade()
        process = facade.getInfo(data['uid'])
        return DirectResponse.succeed(data=Zuul.unmarshal(data, process))

    def getInstances(self, uid, start=0, params=None, limit=50, sort='name',
                     dir='ASC'):
        """
        Get a list of instances for a process UID.

        @type  uid: string
        @param uid: Process UID to get instances of
        @type  start: integer
        @param start: (optional) Offset to return the results from; used in
                      pagination (default: 0)
        @type  params: dictionary
        @param params: (optional) Key-value pair of filters for this search.
        @type  limit: integer
        @param limit: (optional) Number of items to return; used in pagination
                      (default: 50)
        @type  sort: string
        @param sort: (optional) Key on which to sort the return results (default:
                     'name')
        @type  dir: string
        @param dir: (optional) Sort order; can be either 'ASC' or 'DESC'
                    (default: 'ASC')
        @rtype:   DirectResponse
        @return:  B{Properties}:
             - data: ([dictionary]) List of objects representing process instances
             - total: (integer) Total number of instances
        """
        facade = self._getFacade()
        instances = facade.getInstances(uid, start, limit, sort, dir, params)
        data = Zuul.marshal(instances)
        return DirectResponse.succeed(data=data, total=instances.total)

    def getSequence(self):
        """
        Get the current processes sequence.

        @rtype:   DirectResponse
        @return:  B{Properties}:
             - data: ([dictionary]) List of objects representing processes in
             sequence order
        """
        facade = self._getFacade()
        sequence = facade.getSequence()
        data = Zuul.marshal(sequence)
        return DirectResponse.succeed(data=data)

    def setSequence(self, uids):
        """
        Set the current processes sequence.

        @type  uids: [string]
        @param uids: The set of process uid's in the desired sequence
        @rtype:   DirectResponse
        @return:  Success message
        """
        facade = self._getFacade()
        facade.setSequence(uids)
        return DirectResponse.succeed()
