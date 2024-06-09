import asyncio
import getpass
import random
import sys
import tomllib
from collections import Counter

import tomli_w
from nio import (
    AsyncClient,
    JoinedMembersResponse,
    LoginResponse,
    RoomPutStateResponse,
    SpaceGetHierarchyResponse,
)

CONFIG_FILE = "config.toml"

with open(CONFIG_FILE, "rb") as f:
    config_toml = tomllib.load(f)


async def update_via(client: AsyncClient):
    config = config_toml["main"]

    space_id = config["space_id"]

    # Get all rooms
    rooms_resp = await client.space_get_hierarchy(space_id=space_id)
    if not isinstance(rooms_resp, SpaceGetHierarchyResponse):
        raise ErrorGettingSpace(rooms_resp)
    rooms = rooms_resp.rooms

    # Use only root space
    space = rooms[0]

    # Update each room
    for room in space["children_state"]:
        if room["type"] != "m.space.child":
            continue

        room_id = room["state_key"]

        if not room_id:
            continue

        # Get room members
        members_resp = await client.joined_members(room_id)
        if not isinstance(members_resp, JoinedMembersResponse):
            if config["ignore_errors"]:
                print(f"Skipping room {room_id}: {members_resp}")
            else:
                raise members_resp
            continue
        members = members_resp.members

        # Get a list of unique servers
        all_servers = [get_user_homeserver(member.user_id) for member in members]
        common_servers = most_common_servers(
            all_servers, config["most_common_servers"], config["min_users_per_server"]
        )

        # Get power levels
        levels_response = await client.room_get_state_event(
            room_id, "m.room.power_levels", ""
        )
        power_levels = levels_response.content

        # Get highest level users
        member_levels = {
            member.user_id: power_levels.get("users", {}).get(
                member.user_id, power_levels.get("users_default", 0)
            )
            for member in members
        }
        highest_level_members = get_highest_level_members(member_levels)

        # Make via server list
        highest_level_servers = [
            get_user_homeserver(user_id) for user_id in highest_level_members
        ]

        valid_additional_servers = [
            server for server in config["additional_servers"] if server in all_servers
        ]

        servers = list(
            set(valid_additional_servers + common_servers + highest_level_servers)
        )

        if (
            len(servers) < config["optimal_via_servers"]
            and config["ignore_requirementrs_to_reach_optimum"]
        ):
            server_count = max(
                config["most_common_servers"], config["optimal_via_servers"]
            )
            common_servers = most_common_servers(
                all_servers,
                server_count,
                1,
            )
            servers = list(set(common_servers + list(servers)))

        # Ignore room if 'via' already matches
        if set(room["content"]["via"]) == set(servers):
            print(f"Skipping room {room_id}, 'via' servers already match.")
            continue

        if config["shuffle_order"]:
            random.shuffle(servers)

        content = {"suggested": room["content"]["suggested"], "via": servers}

        if not config["dry_run"]:
            resp = await client.room_put_state(
                room_id=space_id,
                event_type="m.space.child",
                content=content,
                state_key=room_id,
            )
            if isinstance(resp, RoomPutStateResponse):
                print(f"Updated room {room_id}")
            else:
                if config["ignore_errors"]:
                    print(f"Could not update room {room_id}, skipping: {resp}")
                else:
                    raise ErrorUpdatingState(resp)
        else:
            print(f"DRY RUN: Would have updated room {room_id}")
        print(f"Before: {', '.join(room["content"]["via"])}")
        print(f"After: {', '.join(servers)}")


def get_highest_level_members(member_levels, threshold=50):
    highest_value = max(member_levels.values())

    if highest_value <= threshold:
        return []

    items_with_highest_value = [
        key for key, value in member_levels.items() if value == highest_value
    ]

    return items_with_highest_value


def get_user_homeserver(user_id: str):
    return user_id.split(":")[1]


def most_common_servers(lst, n, min_occurrences=2):
    counter = Counter(lst)
    filtered_items = {
        item: count for item, count in counter.items() if count >= min_occurrences
    }
    sorted_items = sorted(filtered_items.items(), key=lambda x: x[1], reverse=True)
    top_n_items = [item for item, count in sorted_items[:n]]
    return top_n_items


def write_details_to_disk(resp: LoginResponse, homeserver) -> None:
    """Writes the required login details to disk so we can log in later without
    using a password.

    Arguments:
        resp {LoginResponse} -- the successful client login response.
        homeserver -- URL of homeserver, e.g. "https://matrix.example.org"
    """

    config_toml["credentials"] = {
        "homeserver": homeserver,  # e.g. "https://matrix.example.org"
        "user_id": resp.user_id,  # e.g. "@user:example.org"
        "device_id": resp.device_id,  # device ID, 10 uppercase letters
        "access_token": resp.access_token,  # cryptogr. access token
    }

    with open(CONFIG_FILE, "r+b") as fp:
        tomli_w.dump(config_toml, fp)


async def main() -> None:
    # check if 'credentials' exists in the config file and all fields are non-empty
    if (not "credentials" in config_toml
        or any([not option for option in config_toml["credentials"].values()])):

        print(
            "First time use. Did not find credential information. Asking for "
            "homeserver, user, and password to create credential file."
        )

        homeserver = "https://matrix.example.org"
        homeserver = input(f"Enter your homeserver URL: [{homeserver}] ") or homeserver

        if not (homeserver.startswith("https://") or homeserver.startswith("http://")):
            homeserver = "https://" + homeserver

        user_id = "@user:example.org"
        user_id = input(f"Enter your full user ID: [{user_id}] ") or user_id

        device_name = "matrix-nio"
        device_name = (
            input(f"Choose a name for this device: [{device_name}] ") or device_name
        )

        client = AsyncClient(homeserver, user_id)
        pw = getpass.getpass()
        resp = await client.login(pw, device_name=device_name)

        # check that we logged in successfully
        if isinstance(resp, LoginResponse):
            write_details_to_disk(resp, homeserver)
        else:
            print(f'homeserver = "{homeserver}"; user = "{user_id}"')
            print(f"Failed to log in: {resp}")
            sys.exit(1)

        print(
            "Logged in using a password. Credentials were stored.",
            "Try running the script again to login with credentials.",
        )
    else:
        credentials = config_toml["credentials"]
        client = AsyncClient(credentials["homeserver"])
        client.access_token = credentials["access_token"]
        client.user_id = credentials["user_id"]
        client.device_id = credentials["device_id"]

        print("Logged in using stored credentials.")

    # Either way we're logged in here, too
    await update_via(client)

    await client.close()


class ErrorUpdatingState(Exception):
    pass


class ErrorGettingSpace(Exception):
    pass


asyncio.run(main())
