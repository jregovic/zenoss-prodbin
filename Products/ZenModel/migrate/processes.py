#################################################################
#
#   Copyright (c) 2006 Zenoss, Inc. All rights reserved.
#
#################################################################

__doc__='''

Add Processes organizer and friends.

'''

__version__ = "$Revision$"[11:-2]

from Acquisition import aq_base

import Migrate
import os

class Processes(Migrate.Step):
    version = 22.0

    def cutover(self, dmd):
        if hasattr(dmd, 'Processes'):
            return

        import Zope2
        Zope2.configure(os.path.join(os.environ['ZENHOME'], "etc/zope.conf"))
        app = Zope2.app()
        zdmd = app.zport.dmd

        from Products.ZenModel.OSProcessOrganizer \
             import manage_addOSProcessOrganizer
        manage_addOSProcessOrganizer(zdmd, 'Processes')

        if getattr(dmd.Devices.rrdTemplates, 'OSProcess', None) is None:
            from Products.ZenRelations.ImportRM import ImportRM
            imp = ImportRM(noopts=True, app=dmd.getPhysicalRoot())
            imp.options.noCommit = True
            imp.options.infile = os.path.join(os.environ['ZENHOME'],
                'Products', 'ZenModel', 'data', 'osproc.update')
            imp.loadDatabase()

Processes()
