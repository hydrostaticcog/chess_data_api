# -*- coding: utf-8 -*-
""" """
from limigrations.migration import BaseMigration


class Migration(BaseMigration):
    """A migration for somehting."""

    def up(self, conn, c):
        """Run when calling 'migrate'."""
        # Do something with connection and cursor
        c.execute(
            """CREATE TABLE teams (
            id INTEGER PRIMARY KEY,
            name TEXT,
            sponsor_name TEXT
            )
        """
        )
        c.execute(
            """CREATE TABLE players (
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
            """CREATE TABLE officials (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT,
            verified TEXT
            )
        """
        )
        c.execute(
            """CREATE TABLE tournaments (
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
            """CREATE TABLE games (
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
            """CREATE UNIQUE INDEX unique_index ON enrollment(player_id, tournament_id)""")
        c.execute(
            """ALTER TABLE games ADD COLUMN round INTEGER"""
        )
        c.execute(
            """ALTER TABLE tournaments ADD COLUMN rounds INTEGER NOT NULL DEFAULT 3"""
        )
        c.execute(
            """ALTER TABLE tournaments ADD COLUMN boards INTEGER NOT NULL DEFAULT 10"""
        )
        c.execute(
            """alter table players add column draws INTEGER DEFAULT 0"""
        )
        conn.commit()
        pass

    def down(self, conn, c):
        """Run when calling 'rollback'."""
        # Do something with connection and cursor
        pass
