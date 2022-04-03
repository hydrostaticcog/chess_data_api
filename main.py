import asyncio
import datetime
import random
import json
from limigrations import limigrations
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List

import aiosqlite
from aiohttp import web
from aiohttp_basicauth import BasicAuthMiddleware

with open("config.json", "r") as f:
    creds = json.load(f)

router = web.RouteTableDef()


class CustomAuth(BasicAuthMiddleware):
    async def check_credentials(self, username, password, request):
        return username == creds['username'] and password == creds['password']


custom_auth = CustomAuth()


def sort_by_wins(e):
    return e['wins'] + (e['draws'] * .5)


class NotFoundException(BaseException):
    pass


def generate_id(type: int) -> int:
    ts = datetime.datetime.utcnow().timestamp()
    node_id = 0
    return (int(ts) << 16) + (node_id << 20) + (type << 24) + (random.randint(1, 1000) << 32)


async def fetch_team_members(db: aiosqlite.Connection, id: int):
    async with db.execute(
            "SELECT * FROM players WHERE team = ?", [id]
    ) as cursor:
        rows = await cursor.fetchall()
        members = []
        for row in rows:
            m = await fetch_player_light(db, row['id'])
            members.append(m)
        members.sort(key=lambda s: s['name'].split()[-1])
        return members


async def fetch_team_leaderboard(db: aiosqlite.Connection, id: int):
    async with db.execute(
            "SELECT * FROM players WHERE team = ?", [id]
    ) as cursor:
        rows = await cursor.fetchall()
        members = []
        for row in rows:
            m = await fetch_player_light(db, row['id'])
            members.append(m)
        members.sort(reverse=True, key=lambda s: (s['wins'] + .5 * s['draws']) - (s['losses'] + .5 * s['draws']))
        return members


async def fetch_team(db: aiosqlite.Connection, id: int) -> Dict[str, Any]:
    async with db.execute(
            "SELECT * FROM teams WHERE id = ?", [id]
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"Team {id} does not exist!")
        return {
            "id": id,
            "type": "team",
            "name": row["name"],
            "sponsor": row["sponsor_name"],
            "members": [await fetch_team_members(db, id)]
        }


async def fetch_team_light(db: aiosqlite.Connection, id: int) -> Dict[str, Any]:
    async with db.execute(
            "SELECT * FROM teams WHERE id = id", [id]
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"Team {id} does not exist!")
        return {
            "id": id,
            "type": "team",
            "name": row["name"],
            "sponsor": row["sponsor_name"],
            "members": None
        }


async def fetch_player(db: aiosqlite.Connection, id: int) -> Dict[str, Any]:
    async with db.execute(
            "SELECT * FROM players WHERE id = ?", [id]
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"Player {id} does not exist!")
        return {
            "id": row["id"],
            "type": "player",
            "name": row["name"],
            "grade": int(row["grade"]),
            "wins": row["wins"],
            "losses": row["losses"],
            "draws": row["draws"],
            "team": await fetch_team(db, row["team"])
        }


async def fetch_player_light(db: aiosqlite.Connection, id: int) -> Dict[str, Any]:
    async with db.execute(
            "SELECT * FROM players WHERE id = ?", [id]
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"Player {id} does not exist!")
        return {
            "id": row["id"],
            "type": "player",
            "name": row["name"],
            "grade": int(row["grade"]),
            "wins": row["wins"],
            "draws": row["draws"],
            "losses": row["losses"],
            "team": row['team']
        }


async def fetch_player_standings(db: aiosqlite.Connection, id: int, tournament_id: int) -> Dict[str, Any]:
    async with db.execute(
            "SELECT * FROM games WHERE (tournament_id = ? AND ? in (black, white))", [tournament_id, id]
    ) as cursor:
        rows = await cursor.fetchall()
        wins = 0
        losses = 0
        draws = 0
        print(rows)
        for row in rows:
            print(row)
            if row['result'] == id:
                wins += 1
            elif row['result'] == 'draw':
                draws += 1
            elif row['result'] is None:
                continue
            else:
                losses += 1
        return {
            "id": id,
            "type": "player-tournament_standings",
            "tournament": tournament_id,
            "wins": wins,
            "losses": losses,
            "draws": draws
        }


async def fetch_official(db: aiosqlite.Connection, id: int) -> Dict[str, Any]:
    async with db.execute(
            "SELECT * FROM officials WHERE id = ?", [id]
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
            "SELECT * FROM tournaments WHERE id = ?", [id]
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"Tournament {id} does not exist!")
        rounds = {}
        c = 0
        while c < row['rounds']:
            rounds.update({f"{c + 1}": (await fetch_games_by_rounds(db, id, c + 1))})
            c += 1
        return {
            "id": row["id"],
            "type": "tournament",
            "name": row["name"],
            "date": row["date"],
            "boards": row['boards'],
            "rounds": row['rounds'],
            "location": row["location"],
            "official": (await fetch_official(db, row["official"])),
            "games": rounds
        }


async def fetch_tournament_light(db: aiosqlite.Connection, id: int) -> Dict[str, Any]:
    async with db.execute(
            "SELECT * FROM tournaments WHERE id = ?", [id]
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"Tournament {id} does not exist!")
        return {
            "id": row["id"],
            "type": "tournament",
            "name": row["name"],
            "date": row["date"],
            "boards": row['boards'],
            "rounds": row['rounds'],
            "location": row["location"],
            "official": row["official"],
            "games": None
        }


async def fetch_game(db: aiosqlite.Connection, id: int) -> Dict[str, Any]:
    async with db.execute(
            "SELECT * FROM games WHERE id = ?", [id]
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
            "round": row['round'],
            "tournament": (await fetch_tournament_light(db, row['tournament_id'])),
            "white": (await fetch_player_light(db, row['white'])),
            "black": (await fetch_player_light(db, row['black'])),
            "official": official_obj,
            "result": row['result']
        }


async def fetch_game_light(db: aiosqlite.Connection, id: int) -> Dict[str, Any]:
    async with db.execute(
            "SELECT * FROM games WHERE id = ?", [id]
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
            "round": row['round'],
            "tournament": row['tournament_id'],
            "white": (await fetch_player_light(db, row['white'])),
            "black": (await fetch_player_light(db, row['black'])),
            "official": official_obj,
            "result": row['result']
        }


async def fetch_enrollment(db: aiosqlite.Connection, id: int) -> Dict[str, Any]:
    async with db.execute(
            "SELECT * FROM enrollment WHERE id = ?", [id]
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise NotFoundException(f"enrollment card {id} does not exist!")
        return {
            "id": row['id'],
            "type": "enrollment",
            "player": (await fetch_player_light(db, row['player_id'])),
            "tournament": (await fetch_tournament(db, row['tournament_id'])),
            "team": (await fetch_team_light(db, row['team_id']))
        }


async def fetch_games_by_rounds(db: aiosqlite.Connection, id: int, round: int) -> List[Dict[str, Any]]:
    async with db.execute(
            "SELECT * FROM games WHERE tournament_id = ? AND round = ?", [id, round]
    ) as cursor:
        rows = await cursor.fetchall()
        games = []
        for row in rows:
            m = await fetch_game_light(db, row['id'])
            games.append(m)
        return games


async def add_win(db: aiosqlite.Connection, id: int) -> Dict[str, Any]:
    player = await fetch_player(db, id)
    await db.execute(
            f"UPDATE players SET wins = ? WHERE id = ?", [player['wins'] + 1, id]
    )
    await db.commit()
    return {
        "status": "ok"
    }


async def add_loss(db: aiosqlite.Connection, id: int, ) -> Dict[str, Any]:
    player = await fetch_player(db, id)
    await db.execute(
            f"UPDATE players SET losses = ? WHERE id = ?", [player['losses'] + 1, id])
    await db.commit()
    return {
        "status": "ok"
    }


async def add_draw(db: aiosqlite.Connection, id_1: int, id_2: int) -> Dict[str, Any]:
    player1 = await fetch_player(db, id_1)
    player2 = await fetch_player(db, id_2)
    await db.executescript(
            f"""UPDATE players SET draws = {player1['draws'] + 1} WHERE id = {id_1};
            UPDATE players SET draws = {player2['draws'] + 1} WHERE id = {id_2};
        """
    )
    await db.commit()
    return {
        "status": "ok"
    }


async def setup_game(db: aiosqlite.Connection, white: int, black: int, board: int, round: int, tournament: int) -> \
        Dict[str, Any]:
    id = generate_id(3)
    await db.execute(
        "INSERT INTO games (id, board, white, black, round, tournament_id) VALUES (?, ?, ?, ?, ?, ?)",
        [id, board, white, black, round, tournament]
    )
    await db.commit()
    return {
        "id": id,
        "tournament": (await fetch_tournament_light(db, tournament)),
        "board": board,
        "round": round,
        "white": (await fetch_player_light(db, white)),
        "black": (await fetch_player_light(db, black)),
        "official": None,
        "result": None
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
    tournament = info['tournament']
    white = info['white']
    black = info['black']
    board = info['board']
    round = info['round']
    db = request.config_dict['DB']
    game = await setup_game(db, white, black, board, round, tournament)
    return web.json_response(game)


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
        await db.commit()
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
        await db.commit()
    if result:
        if result == game["white"]["id"]:
            await add_win(db, result)
            await add_loss(db, game['black']['id'])
        if result == game["black"]['id']:
            await add_win(db, result)
            await add_loss(db, game['white']['id'])
        if result == "draw":
            await add_draw(db, game['white']['id'], game['black']['id'])
    new_game = await fetch_game(db, game_id)
    return web.json_response(new_game)


@router.delete("/games/{id}")
@handle_json_error
async def delete_game(request: web.Request) -> web.json_response():
    game_id = request.match_info['id']
    db = request.config_dict['DB']
    async with db.execute("DELETE FROM games WHERE id = ? CASCADE", [game_id]) as cursor:
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
    boards = info['boards']
    rounds = info['rounds']
    db = request.config_dict['DB']
    official_obj = await fetch_official(db, official)
    await db.execute(
        "INSERT INTO tournaments (id, name, date, official, location, boards, rounds) VALUES(?, ?, ?, ?, ?, ?, ?)",
        [id, name, date, official, location, boards, rounds]
    )
    await db.commit()
    return web.json_response(
        {
            "id": id,
            "type": "tournament",
            "name": name,
            "date": date,
            "rounds": rounds,
            "boards": boards,
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


@router.get("/tournaments/{id}/standings/{player_id}")
@handle_json_error
async def get_player_standings_t(request: web.Request) -> web.json_response():
    tournament_id = request.match_info['id']
    player_id = request.match_info['player_id']
    db = request.config_dict['DB']
    results = await fetch_player_standings(db, player_id, tournament_id)
    return web.json_response(results)


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
    if "rounds" in tournament:
        fields['rounds'] = tournament['rounds']
    if "boards" in tournament:
        fields['boards'] = tournament['boards']
    if fields:
        field_names = ", ".join(f"{name} = ?" for name in fields)
        field_values = list(fields.values())
        await db.execute(
            f"UPDATE tournaments SET {field_names} WHERE id = ?", field_values + [tournament_id]
        )
    new_tournament = await fetch_tournament(db, tournament_id)
    return web.json_response(new_tournament)


@router.post("/tournaments/{id}/enroll/mass")
@handle_json_error
async def enroll_mass(request: web.Request) -> web.json_response():
    info = await request.json()
    tournament_id = request.match_info['id']
    db = request.config_dict['DB']
    enroll_list = info['list']
    output = []
    for player in enroll_list:
        id = generate_id(4)
        player_id = player['player']
        team_id = player['team']
        await db.execute(
            "INSERT INTO enrollment (id, player_id, tournament_id, team_id) VALUES (?, ?, ?, ?)",
            [id, player_id, tournament_id, team_id]
        )
        await db.commit()
        enrollment = await fetch_enrollment(db, id)
        output.append(enrollment)
    return web.json_response(output)


@router.post("/tournaments/{id}/enroll")
@handle_json_error
async def enroll_individual(request: web.Request) -> web.json_response():
    info = await request.json()
    tournament_id = request.match_info['id']
    db = request.config_dict['DB']
    player = info['player']
    team = info['team']
    id = generate_id(4)
    await db.execute(
        "INSERT INTO enrollment (id, player_id, tournament_id, team_id) VALUES (?, ?, ?, ?)",
        [id, player, tournament_id, team]
    )
    await db.commit()
    enrollment = await fetch_enrollment(db, id)
    return web.json_response(enrollment)


@router.post("/tournaments/{id}/organize/{round}")
async def organize_tournament(request: web.Request) -> web.json_response():
    tournament_id = request.match_info['id']
    round = request.match_info['round']
    db = request.config_dict['DB']
    players_enrolled = []
    async with db.execute(
            "SELECT * FROM enrollment WHERE tournament_id = ?", [tournament_id]
    ) as cursor:
        enrollment = await cursor.fetchall()
        for card in enrollment:
            players_enrolled.append(await fetch_player_standings(db, card['player_id'], tournament_id))
    print(players_enrolled)
    tournament = await fetch_tournament(db, tournament_id)
    players_enrolled.sort(reverse=True, key=sort_by_wins)
    i = 0
    e = 0
    games = []
    while e < tournament['boards']:
        try:
            games.append({"white": players_enrolled[i]['id'], "black": players_enrolled[i + 1]['id'], "round": round,
                          "board": e})
            i += 2
            e += 1
        except IndexError:
            games.append({"round": round, "board": e, "bye": players_enrolled[i]})
            break
    print(games)
    created_games = []
    for game in games:
        try:
            created = await setup_game(db, white=game['white'], black=game['black'], board=game['board'], round=round,
                                       tournament=tournament_id)
            print(f"creating game {game}")
            created_games.append(created)
        except KeyError:
            await add_win(db, game['bye']['id'])
            print(f"created bye {game}")
            created_games.append({"bye": game['bye']['id'], "round": game['round']})
    print(created_games)
    return web.json_response({"list": created_games})


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
            "losses": 0,
            "draws": 0
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


@router.get("/teams/{id}/leaderboard")
@handle_json_error
async def get_team_lb(request: web.Request) -> web.json_response():
    team_id = request.match_info['id']
    db = request.config_dict['DB']
    team = await fetch_team_leaderboard(db, team_id)
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
async def ping() -> web.json_response():
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
    app = web.Application(middlewares=[custom_auth])
    app.add_routes(router)
    app.cleanup_ctx.append(init_db)
    return app


def try_make_db() -> None:
    sqlite_db = get_db_path()
    if sqlite_db.exists():
        return

    limigrations.migrate("db.sqlite3", "migrations")


try_make_db()

web.run_app(init_app())
