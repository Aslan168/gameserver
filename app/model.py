import json
import uuid
from enum import Enum, IntEnum
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


class SafeUser(BaseModel):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int

    class Config:
        orm_mode = True


# Enum
class LiveDifficulty(Enum):
    normal = 1
    hard = 2


class JoinRoomResult(Enum):
    Ok = 1
    RoomFull = 2
    Disbanned = 3
    OtherError = 4


class WaitRoomStatus(Enum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


# 構造体
class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int


# user関連
def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id) VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        # print(result)
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    # TODO: 実装
    result = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token`=:token"),
        dict(token=token),
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return SafeUser.from_orm(row)


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    # このコードを実装してもらう
    with engine.begin() as conn:
        # TODO: 実装
        conn.execute(
            text(
                "UPDATE `user` SET name = :name, leader_card_id = :leader_card_id WHERE token = :token"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
    return None


def create_room(token: str, live_id: int, select_difficulty: LiveDifficulty) -> int:
    with engine.begin() as conn:
        res = conn.execute(
            text("INSERT INTO `room` (live_id) VALUES (:live_id)"),
            {"live_id": live_id},
        )
        room_id = res.lastrowid
        User = get_user_by_token(token)
        res = conn.execute(
            text(
                "REPLACE INTO `room_member` (user_id, room_id, name, leader_card_id, select_difficulty, is_me, is_host)\
                 VALUES (:user_id, :room_id, :name, :leader_card_id, :select_difficulty, :is_me, :is_host)"
            ),
            {
                "user_id": User.id,
                "room_id": room_id,
                "name": User.name,
                "leader_card_id": User.leader_card_id,
                "select_difficulty": select_difficulty.value,
                "is_me": True,
                "is_host": True,
            },
        )

        return room_id


def get_room_list(token: str, live_id: int):
    with engine.begin() as conn:
        if live_id == 0:
            res = conn.execute(
                text(
                    "SELECT room_id, live_id, joined_user_count, max_user_count FROM room"
                ),
            )
        else:
            res = conn.execute(
                text(
                    "SELECT room_id, live_id, joined_user_count, max_user_count FROM room WHERE live_id= :live_id"
                ),
                {"live_id": live_id},
            )
        return res.all()


def join_room(token: str, room_id: int, select_difficulty: LiveDifficulty):
    with engine.begin() as conn:
        res = conn.execute(
            text(
                "SELECT joined_user_count, max_user_count FROM room WHERE room_id=:room_id"
            ),
            {"room_id": room_id},
        )
        try:
            joined_user_count, max_user_count = res.one()
            User = get_user_by_token(token)
            if joined_user_count < max_user_count:  # 定員より少なければ
                res = conn.execute(
                    text(
                        "UPDATE room SET joined_user_count=:joined_user_count WHERE room_id=:room_id"
                    ),
                    {"joined_user_count": joined_user_count + 1, "room_id": room_id},
                    # TODO
                    # room_memberを検索してその人数にした方が安全かも(1人で複数回joinした時の対応)
                )
                res = conn.execute(
                    text(
                        "REPLACE INTO `room_member` (user_id, room_id, name, leader_card_id, select_difficulty, is_me, is_host)\
                        VALUES (:user_id, :room_id, :name, :leader_card_id, :select_difficulty, :is_me, :is_host)"
                    ),
                    {
                        "user_id": User.id,
                        "room_id": room_id,
                        "name": User.name,
                        "leader_card_id": User.leader_card_id,
                        "select_difficulty": select_difficulty.value,
                        "is_me": True,
                        "is_host": False,
                    },
                )
                return JoinRoomResult(1)
            else:
                return JoinRoomResult(2)
        except:
            return JoinRoomResult(4)


def wait_room(token: str, room_id: int):
    with engine.begin() as conn:
        res = conn.execute(
            text("SELECT room_status FROM room WHERE room_id=:room_id"),
            {"room_id": room_id},
        )
        status = res.one()[0]
        res = conn.execute(
            text(
                "SELECT user_id, name, leader_card_id, select_difficulty, is_me, is_host\
                 FROM room_member WHERE room_id=:room_id"
            ),
            {"room_id": room_id},
        )
        room_user_list = res.all()
    return (status, room_user_list)


"""

from sqlalchemy import *
from app.model import engine
conn = engine.connect()
from app.model import get_user_by_token
from app.model import update_user

res = get_user_by_token("xxxx")
"""

# flake8: noqa
