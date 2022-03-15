# -*- coding: utf-8 -*-
""" """
from limigrations.migration import BaseMigration


class Migration(BaseMigration):
    """A migration for somehting."""

    def up(self, conn, c):
        """Run when calling 'migrate'."""
        # Do something with connection and cursor
        c.execute(
            """CREATE UNIQUE INDEX unique_index ON enrollment(player_id, tournament_id)""")
        c.execute(
            """ALTER TABLE games ADD COLUMN round INTEGER"""
        )
        c.execute(
            """ALTER TABLE tournaments ADD COLUMN rounds INTEGER"""
        )
        pass

    def down(self, conn, c):
        """Run when calling 'rollback'."""
        # Do something with connection and cursor
        pass
