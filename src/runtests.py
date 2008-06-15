#!/usr/bin/env python

import unittest

from Tests.ImageServerTests import PersistenceTests, DomainTests, ImageEngineTests

if __name__ == "__main__":
    alltests = unittest.TestSuite((PersistenceTests.suite(), DomainTests.suite(), ImageEngineTests.suite()))
    #unittest.main()
    runner = unittest.TextTestRunner()
    runner.run(alltests)
