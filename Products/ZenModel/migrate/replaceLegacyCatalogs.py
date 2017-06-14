##############################################################################
#
# Copyright (C) Zenoss, Inc. 2017, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import Migrate

from Products.ZCatalog.ZCatalog import ZCatalog
from Products.Zuul.catalog.legacy import LegacyCatalogAdapter

import logging
log = logging.getLogger("zen.migrate")

class ReplaceLegacyCatalogs(Migrate.Step):
    """
    Remove layer2, layer3, device, ip and global catalogs and
    replace them with a Model Catalog adapter
    """
    version = Migrate.Version(112, 0, 0)

    def _replace_ZCatalog(self, cat_parent, cat_name, context):
        if hasattr(cat_parent, cat_name):
            cat = getattr(cat_parent, cat_name)
            if isinstance(cat, ZCatalog):
                cat_parent._delObject(cat_name)
                catalog_adapter = LegacyCatalogAdapter(context, cat_name)
                setattr(cat_parent, cat_name, catalog_adapter)
                log.info("Legacy '{}' catalog replaced with Model Catalog adapter".format(cat_name))

    def cutover(self, dmd):
        to_replace = [
            (dmd.ZenLinkManager, "layer2_catalog", dmd),
            (dmd.ZenLinkManager, "layer3_catalog", dmd),
            (dmd.Devices, "deviceSearch", dmd.Devices),
            (dmd.IPv6Networks, "ipSearch", dmd.IPv6Networks),
            (dmd.Networks, "ipSearch", dmd.Networks),
            (dmd.zport, "global_catalog", dmd),
        ]
        
        for cat in to_replace:
            self._replace_ZCatalog(*cat)

ReplaceLegacyCatalogs()