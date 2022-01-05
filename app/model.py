#TODO
#roomの人数が0の時、非表示にする（返さない？）

#FIXED
#人数更新ができるようになった


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
                "SELECT joined_user_count, max_user_count, room_status FROM room WHERE room_id=:room_id"
            ),
            {"room_id": room_id},
        )
        try:
            joined_user_count, max_user_count, room_status = res.one()
            #ゲーム中/解散済みを確認
            if room_status == 2:
                return 4
            elif room_status == 3:
                return 3
            
            User = get_user_by_token(token)
            if joined_user_count < max_user_count:  # 定員より少なければ
                res = conn.execute(
                    text("UPDATE room\
                        SET joined_user_count = :joined_user_count \
                        WHERE room_id = :room_id"),
                    {
                        "joined_user_count": joined_user_count,
                        "room_id": room_id
                    },
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


def start_room(token: str, room_id: int):
    # TODO
    # オーナーかどうかのチェック
    with engine.begin() as conn:
        res = conn.execute(
            text("UPDATE room SET room_status = 2 WHERE room_id=:room_id"),
            {"room_id": room_id},
        )
        return


def end_room(token: str, room_id: int, judge_count_list: list[int], score: int):
    with engine.begin() as conn:
        User = get_user_by_token(token)
        res = conn.execute(
            text(
                "UPDATE room_member \
                SET score = :score, \
                score_perfect= :score_perfect, \
                score_great= :score_great, \
                score_good= :score_good, \
                score_bad= :score_bad, \
                score_miss= :score_miss \
                WHERE user_id=:user_id"
            ),
            {
                "user_id": User.id,
                "score": score,
                "score_perfect": judge_count_list[0],
                "score_great": judge_count_list[1],
                "score_good": judge_count_list[2],
                "score_bad": judge_count_list[3],
                "score_miss": judge_count_list[4],
            },
        )
        return


def result_room(token: str, room_id: int):
    # TODO
    with engine.begin() as conn:
        User = get_user_by_token(token)
        res = conn.execute(
            text(
                "SELECT user_id, score_perfect, score_great, score_good, score_bad, score_miss, score\
                FROM room_member WHERE room_id = :room_id"
            ),
            {"room_id": room_id},
        )
        result_user_list_nonarranged = res.all()
        result_user_list = []
        can_return_result = True  # スコアを返却できるか

        for score_list in result_user_list_nonarranged:
            if None in score_list:  # スコアが未送信の人がいないかチェック
                can_return_result = False
                break
            result_user_list.append(
                ResultUser(
                    user_id=score_list[0],
                    judge_count_list=score_list[1:6],
                    score=score_list[6],
                )
            )
        
        res = conn.execute(
            text(
                "UPDATE room SET room_status = 3 WHERE room_id = :room_id"
            ),
            {"room_id": room_id},
        )
        if can_return_result:
            return result_user_list
        else:
            return []


def leave_room(token: str, room_id: int):
    # TODO
    with engine.begin() as conn:
        User = get_user_by_token(token)
        res = conn.execute(
            text("DELETE from room_member WHERE user_id=:user_id AND room_id=:room_id"),
            {"user_id": User.id, "room_id": room_id},
        )
        res = conn.execute(
            text("SELECT count(user_id) from room_member WHERE room_id = :room_id"),
            {"room_id": room_id},
        )
        joined_user_count = res.one()[0]
        if joined_user_count == 0:
            res = conn.execute(
                #text("UPDATE room\
                #    SET joined_user_count = :joined_user_count, \
                #        room_status = 3\
                #    WHERE room_id = :room_id"),
                text("DELETE from room WHERE room_id = :room_id"),
                {
                    "joined_user_count": joined_user_count,
                    "room_id": room_id
                },
            )
        else:
            res = conn.execute(
                text("UPDATE room\
                    SET joined_user_count = :joined_user_count \
                    WHERE room_id = :room_id"),
                {
                    "joined_user_count": joined_user_count,
                    "room_id": room_id
                },
            )
        return


"""

from sqlalchemy import *
from app.model import engine
conn = engine.connect()
from app.model import get_user_by_token
from app.model import update_user

res = get_user_by_token("xxxx")
"""

# flake8: noqa
