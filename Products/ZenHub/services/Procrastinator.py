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

from sets import Set
from twisted.internet import reactor

class Procrastinate(object):
    "A class to delay executing a change to a device"

    _DO_LATER_DELAY = 5
    _DO_NOW_DELAY = 0.05

    def __init__(self, cback):
        self.cback = cback
        self.devices = Set()
        self.timer = None

    def clear(self):
        self.devices = Set()

    def doLater(self, device = None):
        if self.timer and not self.timer.called:
            self.timer.cancel()
        self.devices.add(device)
        self.timer = reactor.callLater(Procrastinate._DO_LATER_DELAY, self._doNow)


    def _doNow(self, *unused):
        if self.devices:
            device = self.devices.pop()
            self.cback(device)
            if self.devices:
                reactor.callLater(Procrastinate._DO_NOW_DELAY, self._doNow)
