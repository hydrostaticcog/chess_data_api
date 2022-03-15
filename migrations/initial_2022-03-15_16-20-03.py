# -*- coding: utf-8 -*-
""" """
from limigrations.migration import BaseMigration


class Migration(BaseMigration):
    """A migration for somehting."""

    def up(self, conn, c):
        """Run when calling 'migrate'."""
        # Do something with connection and cursor
        c.execute(
            """CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY,
            name TEXT,
            sponsor_name TEXT
            )
        """
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY,
            name TEXT,
            grade TEXT,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            team INTEGER,
            FOREIGN KEY (team) REFERENCES teams(id)
            )
        """
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS officials (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT,
            verified TEXT
            )
        """
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS tournaments (
                id INTEGER PRIMARY KEY,
                name TEXT,
                date INTEGER,
                official INTEGER,
                location TEXT,
                FOREIGN KEY (official) REFERENCES officials(id)
            )
            """
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY,
                tournament_id INTEGER,
                board INTEGER,
                white INTEGER,
                black INTEGER,
                official INTEGER,
                result TEXT,
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
                FOREIGN KEY (white) REFERENCES players(id),
                FOREIGN KEY (black) REFERENCES players(id),
                FOREIGN KEY (official) REFERENCES officials(id)
            )
            """
        )
        conn.commit()
        pass

    def down(self, conn, c):
        """Run when calling 'rollback'."""
        # Do something with connection and cursor
        pass
