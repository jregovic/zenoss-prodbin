##############################################################################
#
# Copyright (C) Zenoss, Inc. 2017, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import unittest
from Products.ZenTestCase.BaseTestCase import BaseTestCase

from Products.Zuul.catalog.indexable import MODEL_INDEX_UID_FIELD as MI_UID, OBJECT_UID_FIELD as UID
from Products.Zuul.catalog.interfaces import IModelCatalogTool
from zenoss.modelindex.spec import IndexSpec
from zenoss.modelindex.constants import ZENOSS_MODEL_COLLECTION_NAME
from zenoss.modelindex.model_index import SearchParams


from zope.event import notify

from Products.Zuul.catalog.events import IndexingEvent

class ModelCatalogTestsDrawer(BaseTestCase):

    def afterSetUp(self):
        super(ModelCatalogTestsDrawer, self).afterSetUp()
        self.model_catalog = IModelCatalogTool(self.dmd)
        self.data_manager = self.model_catalog.model_catalog_client._data_manager
        self.model_index = self.model_catalog.model_index

    def test_stale_brain(self):
        # Lets create a fake document in solr cloning dmd.Devices
        bad_uid = "/zport/dmd/Devices/intruder"
        spec = IndexSpec(self.dmd.Devices)
        spec.set_field_value(MI_UID, bad_uid)
        spec.set_field_value(UID, bad_uid)
        spec.set_field_value("name", "intruder")
        spec.set_field_value("id", "intruder")
        spec.set_field_value("tx_state", self.data_manager._get_tid())
        self.model_index.do_index(spec, ZENOSS_MODEL_COLLECTION_NAME, commit=True)
        results = self.model_catalog.search(query={UID:bad_uid})
        self.assertTrue( results.total == 1 )
        brain = results.results.next()
        self.assertTrue(brain.getPath() == bad_uid)
        obj = brain.getObject()
        self.assertIsNone(obj)
        results = self.model_catalog.search(query={UID:bad_uid})
        self.assertTrue( results.total == 0 )

    def test_zproperty_with_invalid_chars(self):
        zProperty_key = "zTestProp"
        zProperty_value = '\x9fg`\x00\x1f\x18\xc3\xfd7\x95#\x06\xd01\x05\x95'
        dc = self.dmd.Devices.createOrganizer("dc_with_invalid_chars")
        dc.setZenProperty(zProperty_key, zProperty_value)
        notify(IndexingEvent(dc))
        dc_uid = dc.idx_uid()
        self.data_manager.do_mid_transaction_commit() # this should not raise any exceptions
        results = self.model_catalog.search(query={UID:dc_uid}, fields="zProperties")
        self.assertTrue( results.total == 1 )
        brain = results.results.next()
        self.assertEquals(brain.zProperties[zProperty_key], zProperty_value)


def test_suite():
    return unittest.TestSuite((unittest.makeSuite(ModelCatalogTestsDrawer),))


if __name__=="__main__":
    unittest.main(defaultTest='test_suite')

