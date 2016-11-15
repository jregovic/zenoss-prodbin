##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import common
import unittest


class test_AddHMasterRegionServerGraphConfigs(unittest.TestCase, common.ServiceMigrationTestCase):
    """
    Test that the HMaster and RegionServer have graphs configs.
    """
    initial_servicedef = 'zenoss-resmgr-5.1.5.json'
    expected_servicedef = 'zenoss-resmgr-5.1.5-AddHMasterRegionServerGraphConfigs.json'
    migration_module_name = 'AddHMasterRegionServerGraphConfigs'
    migration_class_name = 'AddHMasterRegionServerGraphConfigs'
