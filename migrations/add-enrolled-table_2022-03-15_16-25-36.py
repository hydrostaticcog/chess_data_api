# -*- coding: utf-8 -*-
""" """
from limigrations.migration import BaseMigration


class Migration(BaseMigration):
    """A migration for somehting."""

    def up(self, conn, c):
        """Run when calling 'migrate'."""
        # Do something with connection and cursor
        c.execute(
            """CREATE TABLE IF NOT EXISTS enrollment (
            id INTEGER PRIMARY KEY,
            player_id INTEGER,
            tournament_id INTEGER,
            team_id INTEGER,
            FOREIGN KEY (player_id) REFERENCES players(id),
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id),
            FOREIGN KEY (team_id) REFERENCES teams(id)
            )
        """)
        c.execute(
            """
            """
        )
        pass

    def down(self, conn, c):
        """Run when calling 'rollback'."""
        # Do something with connection and cursor
        pass
