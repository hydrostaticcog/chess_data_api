# -*- coding: utf-8 -*-
""" """
from limigrations.migration import BaseMigration


class Migration(BaseMigration):
    """A migration for somehting."""

    def up(self, conn, c):
        """Run when calling 'migrate'."""
        # Do something with connection and cursor
        c.execute(
            """ALTER TABLE tournaments ADD COLUMN boards INTEGER"""
        )
        pass

    def down(self, conn, c):
        """Run when calling 'rollback'."""
        # Do something with connection and cursor
        pass
