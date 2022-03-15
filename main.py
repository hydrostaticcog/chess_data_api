import asyncio
import sqlite3
import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Dict

import aiosqlite
from aiohttp import web


router = web.RouteTableDef()


class NotFoundException(BaseException):
    pass


def generate_id(type: int) -> int:
    ts = datetime.datetime.now().timestamp()
    node_id = 0
    return (int(ts) << 16) + (node_id << 24) + (type << 32)


async def fetch_team(db: aiosqlite.Connection, id: int) -> Dict[str, Any]:
    async with db.execute(
        f"SELECT * FROM teams WHERE id = {id}"
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"Team {id} does not exist!")
        return {
            "id": id,
            "type": "team",
            "name": row["name"],
            "sponsor": row["sponsor_name"]
        }


async def fetch_player(db: aiosqlite.Connection, id: int) -> Dict[str, Any]:
    async with db.execute(
        f"SELECT * FROM players WHERE id = {id}"
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"Player {id} does not exist!")
        return {
            "id": row["id"],
            "type": "player",
            "name": row["name"],
            "grade": row["grade"],
            "wins": row["wins"],
            "losses": row["losses"],
            "team": await fetch_team(db, row["team"])
        }


async def fetch_official(db: aiosqlite.Connection, id: int) -> Dict[str, Any]:
    async with db.execute(
        f"SELECT * FROM officials WHERE id = {id}"
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"Official {id} does not exist!")
        return {
            "id": row["id"],
            "type": "official",
            "name": row["name"],
            "email": row["email"],
            "verified": row["verified"]
        }


async def fetch_tournament(db: aiosqlite.Connection, id: int) -> Dict[str, Any]:
    async with db.execute(
        f"SELECT * FROM tournaments WHERE id = {id}"
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"Tournament {id} does not exist!")
        return {
            "id": row["id"],
            "type": "tournament",
            "name": row["name"],
            "date": row["date"],
            "location": row["location"],
            "official": (await fetch_official(db, row["official"]))
        }


async def fetch_game(db: aiosqlite.Connection, id: int) -> Dict[str, Any]:
    async with db.execute(
        f"SELECT * FROM games WHERE id = {id}"
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"game {id} does not exist!")
        if row['official'] is None:
            official_obj = None
        else:
            official_obj = await fetch_official(db, row["official"])
        return {
            "id": row["id"],
            "type": "game",
            "board": row['board'],
            "tournament": (await fetch_tournament(db, row['tournament_id'])),
            "white": (await fetch_player(db, row['white'])),
            "black": (await fetch_player(db, row['black'])),
            "official": official_obj,
            "result": row['result']
        }


def handle_json_error(
    func: Callable[[web.Request], Awaitable[web.Response]]
) -> Callable[[web.Request], Awaitable[web.Response]]:
    async def handler(request: web.Request) -> web.Response:
        try:
            return await func(request)
        except asyncio.CancelledError:
            raise
        except NotFoundException as ex:
            return web.json_response(
                {"status": str(ex)}, status=404
            )
        except Exception as ex:
            return web.json_response(
                {"status": "failed", "reason": str(ex)}, status=400
            )

    return handler


# Game Queries
@router.post("/games")
@handle_json_error
async def create_game(request: web.Request) -> web.json_response():
    info = await request.json()
    id = generate_id(3)
    tournament = info['tournament']
    white = info['white']
    black = info['black']
    board = info['board']
    db = request.config_dict['DB']
    tournament_obj = await fetch_tournament(db, tournament)
    white_obj = await fetch_player(db, white)
    black_obj = await fetch_player(db, black)
    await db.execute(
        "INSERT INTO games (id, tournament_id, board, white, black) VALUES(?, ?, ?, ?, ?)", [id, tournament, board, white, black]
    )
    await db.commit()
    return web.json_response(
        {
            "id": id,
            "type": "game",
            "tournament": tournament_obj,
            "board": board,
            "white": white_obj,
            "black": black_obj,
            "official": None,
            "result": None
        }
    )


@router.get("/games/{id}")
@handle_json_error
async def get_game(request: web.Request) -> web.json_response():
    game_id = request.match_info['id']
    db = request.config_dict['DB']
    game = await fetch_game(db, game_id)
    return web.json_response(game)


@router.patch("/games/{id}")
@handle_json_error
async def edit_game(request: web.Request) -> web.json_response():
    game_id = request.match_info['id']
    game = await request.json()
    db = request.config_dict['DB']
    fields = {}
    if "white" in game:
        fields["white"] = game["white"]
    if "black" in game:
        fields["black"] = game["black"]
    if "official" in game:
        fields["official"] = game["official"]
    if "result" in game:
        fields['result'] = game['result']
    if "board" in game:
        fields["board"] = game["board"]
    if fields:
        field_names = ", ".join(f"{name} = ?" for name in fields)
        field_values = list(fields.values())
        await db.execute(
            f"UPDATE games SET {field_names} WHERE id = ?", field_values + [game_id]
        )
    new_game = await fetch_game(db, game_id)
    return web.json_response(new_game)


@router.post("/games/{id}/resolve")
@handle_json_error
async def resolve_game(request: web.Request) -> web.json_response():
    game_id = request.match_info['id']
    info = await request.json()
    db = request.config_dict['DB']
    game = await fetch_game(db, game_id)
    fields = {}
    if game['result'] is None and game['official'] is None:
        official = info['official']
        fields['official'] = official
        result = info['result']
        fields['result'] = result
    else:
        return web.json_response({"status": "game already resolved!"}, status=409)
    if fields:
        field_names = ", ".join(f"{name} = ?" for name in fields)
        field_values = list(fields.values())
        await db.execute(
            f"UPDATE games SET {field_names} WHERE id = ?", field_values + [game_id]
        )
    new_game = await fetch_game(db, game_id)
    return web.json_response(new_game)


@router.delete("/games/{id}")
@handle_json_error
async def delete_game(request: web.Request) -> web.json_response():
    game_id = request.match_info['id']
    db = request.config_dict['DB']
    async with db.execute("DELETE FROM games WHERE id = ? CASCACE", [game_id]) as cursor:
        if cursor.rowcount == 0:
            return web.json_response({
                "status": f"Game {id} was not found"
            }, status=404
            )
    await db.commit()
    return web.json_response({"status": "ok", "id": game_id})


# Tournament Queries
@router.post("/tournaments")
@handle_json_error
async def create_tournament(request: web.Request) -> web.json_response():
    info = await request.json()
    id = generate_id(3)
    name = info['name']
    date = info['date']
    official = info['official']
    location = info['location']
    db = request.config_dict['DB']
    official_obj = await fetch_official(db, official)
    await db.execute(
        "INSERT INTO tournaments (id, name, date, official, location) VALUES(?, ?, ?, ?, ?)", [id, name, date, official, location]
    )
    await db.commit()
    return web.json_response(
        {
            "id": id,
            "type": "tournament",
            "name": name,
            "date": date,
            "location": location,
            "official": official_obj
        }
    )


@router.get("/tournaments/{id}")
@handle_json_error
async def get_tournaments(request: web.Request) -> web.json_response():
    tournament_id = request.match_info['id']
    db = request.config_dict['DB']
    tournament = await fetch_tournament(db, tournament_id)
    return web.json_response(tournament)


@router.patch("/tournaments/{id}")
@handle_json_error
async def edit_tournaments(request: web.Request) -> web.json_response():
    tournament_id = request.match_info['id']
    tournament = await request.json()
    db = request.config_dict['DB']
    fields = {}
    if "name" in tournament:
        fields["name"] = tournament["name"]
    if "date" in tournament:
        fields["date"] = tournament["date"]
    if "official" in tournament:
        fields["official"] = tournament["official"]
    if "location" in tournament:
        fields['location'] = tournament['location']
    if fields:
        field_names = ", ".join(f"{name} = ?" for name in fields)
        field_values = list(fields.values())
        await db.execute(
            f"UPDATE tournaments SET {field_names} WHERE id = ?", field_values + [tournament_id]
        )
    new_tournament = await fetch_tournament(db, tournament_id)
    return web.json_response(new_tournament)


# Official Queries
@router.get("/officials/{id}")
@handle_json_error
async def get_officials(request: web.Request) -> web.json_response():
    official_id = request.match_info['id']
    db = request.config_dict['DB']
    official = await fetch_official(db, official_id)
    return web.json_response(official)


@router.post("/officials")
@handle_json_error
async def create_officials(request: web.Request) -> web.json_response():
    info = await request.json()
    id = generate_id(3)
    name = info['name']
    email = info['email']
    db = request.config_dict['DB']
    await db.execute(
        "INSERT INTO officials (id, name, email) VALUES(?, ?, ?)", [id, name, email]
    )
    await db.commit()
    return web.json_response(
        {
            "id": id,
            "type": "official",
            "name": name,
            "email": email,
            "verified": "false"
        }
    )


@router.patch("/officials/{id}")
@handle_json_error
async def edit_official(request: web.Request) -> web.json_response():
    official_id = request.match_info['id']
    official = await request.json()
    db = request.config_dict['DB']
    fields = {}
    if "name" in official:
        fields["name"] = official["name"]
    if "email" in official:
        fields["email"] = official["email"]
    if fields:
        field_names = ", ".join(f"{name} = ?" for name in fields)
        field_values = list(fields.values())
        await db.execute(
            f"UPDATE officials SET {field_names} WHERE id = ?", field_values + [official_id]
        )
    new_official = await fetch_official(db, official_id)
    return web.json_response(new_official)


# Player Queries
@router.post("/players")
@handle_json_error
async def create_player(request: web.Request) -> web.json_response():
    info = await request.json()
    id = generate_id(1)
    name = info['name']
    grade = info['grade']
    team = info['team']
    db = request.config_dict['DB']
    team_obj = await fetch_team(db, team)
    await db.execute(
        "INSERT INTO players (id, name, grade, team) VALUES(?, ?, ?, ?)", [id, name, grade, team]
    )
    await db.commit()
    return web.json_response(
        {
            "id": id,
            "type": "player",
            "name": name,
            "grade": grade,
            "team": team_obj,
            "wins": 0,
            "losses": 0
        }
    )


@router.get("/players/{id}")
@handle_json_error
async def get_player(request: web.Request) -> web.json_response():
    player_id = request.match_info['id']
    db = request.config_dict['DB']
    player = await fetch_player(db, player_id)
    return web.json_response(player)


@router.patch("/players/{id}")
@handle_json_error
async def edit_player(request: web.Request) -> web.json_response():
    player_id = request.match_info['id']
    player = await request.json()
    db = request.config_dict['DB']
    fields = {}
    if "name" in player:
        fields["name"] = player["name"]
    if "grade" in player:
        fields["grade"] = player["grade"]
    if fields:
        field_names = ", ".join(f"{name} = ?" for name in fields)
        field_values = list(fields.values())
        await db.execute(
            f"UPDATE players SET {field_names} WHERE id = ?", field_values + [player_id]
        )
    new_player = await fetch_player(db, player_id)
    return web.json_response(new_player)


@router.delete("/players/{id}")
@handle_json_error
async def delete_players(request: web.Request) -> web.json_response():
    player_id = request.match_info['id']
    db = request.config_dict['DB']
    async with db.execute("DELETE FROM players WHERE id = ?", [player_id]) as cursor:
        if cursor.rowcount == 0:
            return web.json_response({
                "status": f"Player {id} was not found"
            }, status=404
            )
    await db.commit()
    return web.json_response({"status": "ok", "id": player_id})


# Team Queries
@router.post("/teams")
async def create_team(request: web.Request) -> web.json_response():
    info = await request.json()
    id = generate_id(2)
    name = info['name']
    sponsor = info['sponsor']
    db = request.config_dict['DB']
    await db.execute(
        f"INSERT INTO teams (id, name, sponsor_name) VALUES ({id}, '{name}', '{sponsor}')"
    )
    await db.commit()
    return web.json_response(
        {
            "id": id,
            "type": "team",
            "name": name,
            "sponsor": sponsor
        }
    )


@router.get("/teams/{id}")
@handle_json_error
async def get_teams(request: web.Request) -> web.json_response():
    team_id = request.match_info['id']
    db = request.config_dict['DB']
    team = await fetch_team(db, team_id)
    return web.json_response(team)


@router.patch("/teams/{id}")
@handle_json_error
async def edit_team(request: web.Request) -> web.json_response():
    team_id = request.match_info['id']
    team = await request.json()
    db = request.config_dict['DB']
    fields = {}
    if "name" in team:
        fields["name"] = team["name"]
    if "sponsor" in team:
        fields["sponsor_name"] = team["sponsor"]
    if fields:
        field_names = ", ".join(f"{name} = ?" for name in fields)
        field_values = list(fields.values())
        await db.execute(
            f"UPDATE teams SET {field_names} WHERE id = ?", field_values + [team_id]
        )
    new_team = await fetch_team(db, team_id)
    return web.json_response(new_team)


# Ping
@router.get("/ping")
@handle_json_error
async def ping(request: web.Request) -> web.json_response():
    return web.json_response(data={"ping": "pong"})


def get_db_path() -> Path:
    here = Path.cwd()
    while not (here / ".git").exists():
        if here == here.parent:
            raise RuntimeError("Cannot find root github dir")
        here = here.parent

    return here / "db.sqlite3"


async def init_db(app: web.Application) -> AsyncIterator[None]:
    sqlite_db = get_db_path()
    db = await aiosqlite.connect(sqlite_db)
    db.row_factory = aiosqlite.Row
    app["DB"] = db
    yield
    await db.close()


async def init_app() -> web.Application:
    app = web.Application()
    app.add_routes(router)
    app.cleanup_ctx.append(init_db)
    return app


def try_make_db() -> None:
    sqlite_db = get_db_path()
    if sqlite_db.exists():
        return

    with sqlite3.connect(sqlite_db) as conn:
        cur = conn.cursor()
        cur.execute(
            """CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY,
            name TEXT,
            sponsor_name TEXT
            )
        """
        )
        cur.execute(
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
        cur.execute(
            """CREATE TABLE IF NOT EXISTS officials (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT,
            verified TEXT
            )
        """
        )
        cur.execute(
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
        cur.execute(
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


try_make_db()


web.run_app(init_app())
