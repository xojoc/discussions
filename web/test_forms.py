# Copyright (c) 2023 Alexandru Cojocaru AGPLv3 or later - no warranty!

import unittest

from web.forms import ADForm


class UnitADForm(unittest.TestCase):
    def test_topics(self):
        form = ADForm(data={"topics": []})
        self.assertEqual(form.errors["topics"], ["This field is required."])

        form = ADForm(data={"topics": ["hackernews"]})
        self.assertFalse(form.errors.get("topics"))

        form = ADForm(data={"topics": ["hackernews", "rust"]})
        self.assertFalse(form.errors.get("topics"))
