"""
This script manipulates the SCUM database for the single player mode to
increase the level of all skills and attributes to max (or the value of
your choice).

Edit the constants below to change the target values for the skills and
attributes. Default is maxed out.

Tested with Python 3.11 on August 5th, 2023 with SCUM Build 0.9.101.72873
"""


from dataclasses import dataclass
import datetime as dt
import os
from pathlib import Path
import shutil
import sqlite3
import struct
import traceback
from typing import Literal

#### Configuration ####

## Main attributes ##
SET_ATTRIBUTES = {
    "BaseStrength": 8.0,  # 1.0 to 8.0
    "BaseConstitution": 5.0,  # 1.0 to 5.0
    "BaseDexterity": 5.0,  # 1.0 to 5.0
    "BaseIntelligence": 5.0,  # 1.0 to 5.0
}

## Skills ##
"""
You can remove skills from the list below and they will not be changed.
If a new skill is added to the game, you can add it to the list below.

The first number in each line is the skill level (0 - 3)
The second number is the skill experience (0 - 10000000)
"""

SET_SKILLS = {
    "BoxingSkill": (3, 10000000),
    "AwarenessSkill": (3, 10000000),
    "RiflesSkill": (3, 10000000),
    "SnipingSkill": (3, 10000000),
    "CamouflageSkill": (3, 10000000),
    "SurvivalSkill": (3, 10000000),
    "MeleeWeaponsSkill": (3, 10000000),
    "HandgunSkill": (3, 10000000),
    "RunningSkill": (3, 10000000),
    "EnduranceSkill": (3, 10000000),
    "TacticsSkill": (3, 10000000),
    "CookingSkill": (3, 10000000),
    "ThieverySkill": (3, 10000000),
    "ArcherySkill": (3, 10000000),
    "DrivingSkill": (3, 10000000),
    "EngineeringSkill": (3, 10000000),
    "DemolitionSkill": (3, 10000000),
    "MedicalSkill": (3, 10000000),
    "MotorcycleSkill": (3, 10000000),
    "StealthSkill": (3, 10000000),
    "AviationSkill": (3, 10000000),
    "ResistanceSkill": (3, 10000000),
    "FarmingSkill": (3, 10000000),
}

# Other constants
USER = os.getlogin()
DB_PATH = Path(f"C:/Users/{USER}/AppData/Local/SCUM/Saved/SaveFiles/SCUM.db")

BODY_SIM_KEY_PADDING = 5
BODY_SIM_VALUE_PADDING = 10


@dataclass
class PropertyType:
    """Just a small class to define property types as they occur in the body simulation blob."""

    name: bytes
    width: int  # in bytes
    # Used for converting with Python types
    struct_type: Literal["<d", "<f", "<?"]


DoubleProperty = PropertyType(name=b"DoubleProperty", width=8, struct_type="<d")
FloatProperty = PropertyType(name=b"FloatProperty", width=4, struct_type="<f")
BoolProperty = PropertyType(name=b"BoolProperty", width=1, struct_type="<?")


def load_prisoner(con: sqlite3.Connection, id: int):
    """Load prisoner from database."""
    cur = con.execute("SELECT * FROM prisoner WHERE id = ?", (id,))
    result = {desc[0]: val for desc, val in zip(cur.description, cur.fetchone())}
    return result


def save_prisoner(con: sqlite3.Connection, prisoner: dict):
    """Updates prisoner in database. Currently only sets body_simulation."""
    return con.execute(
        "UPDATE prisoner SET body_simulation = ? WHERE id = ?",
        (prisoner["body_simulation"], prisoner["id"]),
    )


def update_body_sim(body_sim: bytearray, key: bytes, value: float, property_type: PropertyType):
    # Find the key in the body simulation blob
    key_offset = body_sim.index(key)

    # Make sure we are using the correct property type
    assert (
        body_sim[
            key_offset
            + len(key)
            + BODY_SIM_KEY_PADDING : key_offset
            + len(key)
            + BODY_SIM_KEY_PADDING
            + len(property_type.name)
        ]
        == property_type.name
    )

    # Calculate offset of actual value
    value_offset = (
        key_offset
        + len(key)
        + BODY_SIM_KEY_PADDING
        + len(property_type.name)
        + BODY_SIM_VALUE_PADDING
    )

    # Convert value to bytes
    value_bytes = struct.pack(property_type.struct_type, value)

    # Update value in body sim blob
    body_sim[value_offset : value_offset + property_type.width] = value_bytes


def update_skills(con: sqlite3.Connection, prisoner: dict):
    """Sets all skills to max level in the database."""

    for (name,) in con.execute(
        "SELECT name FROM prisoner_skill WHERE prisoner_id = ?", (prisoner["id"],)
    ):
        if name not in SET_SKILLS:
            continue

        new_level, new_experience = SET_SKILLS[name]

        # Finally, update the XML and other fields in the database
        con.execute(
            "UPDATE prisoner_skill SET level = ?, experience = ? WHERE prisoner_id = ? AND name = ?",
            (new_level, new_experience, prisoner["id"], name),
        )


def choose_prisoner(con: sqlite3.Connection):
    """Choose prisoner to update."""
    cur = con.execute(
        "SELECT prisoner.id, user_profile.name FROM prisoner LEFT JOIN user_profile ON prisoner.user_profile_id = user_profile.id WHERE user_profile.authority_name is ?",
        (None,),
    )
    print("\nFound prisoners in local single player:\n")
    for id, name in cur:
        print(f'"{name}" with ID {id}')
    return int(input("\nEnter prisoner ID: "))


def main():
    print("Backing up database... ")
    filename_safe_iso = dt.datetime.now().isoformat().replace(":", "-")
    backup_path = DB_PATH.with_name(f"SCUM-bak-{filename_safe_iso}.db")
    shutil.copy(DB_PATH, backup_path)
    print(f"Backed up to: {backup_path}")

    print("\nConnecting to database...")
    con = sqlite3.connect(DB_PATH)

    # Choose prisoner interactively
    prisoner_id = choose_prisoner(con)

    print(f"Loading prisoner with ID {prisoner_id}...")
    prisoner = load_prisoner(con, prisoner_id)

    print("\nUpdating attributes... ", end="")
    body_sim = bytearray(prisoner["body_simulation"])

    for attribute, value in SET_ATTRIBUTES.items():
        update_body_sim(
            body_sim,
            attribute.encode("ascii"),
            value,
            DoubleProperty,
        )

    prisoner["body_simulation"] = bytes(body_sim)

    save_prisoner(con, prisoner)
    print("Success!")

    print("Updating skills... ", end="")
    update_skills(con, prisoner)
    print("Success!")

    con.commit()
    input("\nAll done! Press enter to exit.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception:
        print("\n\nSomething went wrong...\n\n")
        traceback.print_exc()
        input("\n\nPress enter to exit.")
