##############################################################################
#
# Copyright (C) Zenoss, Inc. 2007, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import os, sys
if __name__ == '__main__':
    framework = None                    # quiet pyflakes
    execfile(os.path.join(sys.path[0], 'framework.py'))

from ZenModelBaseTest import ZenModelBaseTest
from Products.ZenModel.Device import manage_createDevice
from Products.ZenModel.RRDDataPointAlias import (
    RRDDataPointAlias, EVAL_KEY, manage_addDataPointAlias
)
from Products.ZenModel.tests.RRDTestUtils import createTemplate


def createDevice(dmd, deviceId):
    return manage_createDevice(dmd, deviceId)


class TestRRDDataPointAlias(ZenModelBaseTest):

    def afterSetUp(self):
        ZenModelBaseTest.afterSetUp(self)
        self.device = createDevice(self.dmd, 'testdevice')
        self.device.rackSlot = 5

    def beforeTearDown(self):
        self.device.deleteDevice()
        del self.device
        ZenModelBaseTest.beforeTearDown(self)

    def testCreate(self):
        name = 'testalias'
        formula = 'testformula'
        alias = RRDDataPointAlias(name)
        alias.formula = formula
        self.assert_(alias.id == name)
        self.assert_(alias.formula == formula)

        name2 = 'testalias2'
        alias = RRDDataPointAlias(name2)
        self.assert_(alias.id == name2)
        self.assert_(alias.formula is None)

    def testCreateByMethod(self):
        aliasName = 'testalias3'
        aliasFormula = 'testformula2'
        t = createTemplate(self.dmd)
        ds0 = t.datasources()[0]
        dp0 = ds0.datapoints()[0]
        alias = manage_addDataPointAlias(dp0, aliasName, aliasFormula)
        self.assert_(alias.id == aliasName)
        self.assert_(alias.formula == aliasFormula)

    def testNoFormula(self):
        alias = RRDDataPointAlias('alias1')
        self.assert_(alias.evaluate(self.device) is None)

    def testEmptyFormula(self):
        # Empty formula
        alias = RRDDataPointAlias('alias2')
        alias.formula = ''
        self.assert_(alias.evaluate(self.device) is None)

    def testSimpleRPNFormula(self):
        # Simple RPN formula
        simpleRpn = '100,/'
        alias = RRDDataPointAlias('alias3')
        alias.formula = simpleRpn
        self.assert_(alias.evaluate(self.device) == simpleRpn)

    def testSingleSubstitution(self):
        # Single substitution
        singleSubstitution = '100,*,${here/rackSlot},/'
        alias = RRDDataPointAlias('alias4')
        alias.formula = singleSubstitution
        self.assert_(alias.evaluate(self.device) == '100,*,5,/')

    def testMultipleSubstitution(self):
        # Multiple substitution
        multiSubstitution = \
            '100,*,3,${here/rackSlot},LT,10,20,IF,${here/rackSlot},*'
        alias = RRDDataPointAlias('alias5')
        alias.formula = multiSubstitution
        self.assert_(alias.evaluate(self.device) == '100,*,3,5,LT,10,20,IF,5,*')

    def testNoContext(self):
        # Evaluation (no context)
        evaluationNoContext = EVAL_KEY + '"100,*," + str(len("12345")) + ",/"'
        alias = RRDDataPointAlias('alias6')
        alias.formula = evaluationNoContext
        self.assert_(alias.evaluate(self.device) == '100,*,5,/')

    def testWithContext(self):
        # Evaluation (use context)
        evaluationWithContext = EVAL_KEY + \
            '"100,*," + str(len("12345") * here.rackSlot) + ",/"'
        alias = RRDDataPointAlias('alias7')
        alias.formula = evaluationWithContext
        self.assert_(alias.evaluate(self.device) == '100,*,25,/')

    def testPythonAndTalesContext(self):
        # Evaluation (use context in python and TALES)
        evaluationWithContextUsedTwice = EVAL_KEY + \
            '"100,*,${here/rackSlot},/," + str(here.rackSlot) + ",*"'
        alias = RRDDataPointAlias('alias8')
        alias.formula = evaluationWithContextUsedTwice
        self.assert_(alias.evaluate(self.device) == '100,*,5,/,5,*')


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestRRDDataPointAlias))
    return suite


if __name__ == "__main__":
    framework()
