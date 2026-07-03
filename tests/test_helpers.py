from datetime import date

import pytest

from easycore import (
    format_track_date,
    parse_track_date,
    slugify_author,
    track_artwork_path,
)
from models import Artist, Track


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Maya Vale", "maya-vale"),
        ("  Ren! Kline?? ", "ren-kline"),
        ("Beyonce Knowles", "beyonce-knowles"),
        ("", ""),
        (None, ""),
    ],
)
def test_slugify_author(name, expected):
    assert slugify_author(name) == expected


def test_parse_track_date_defaults_to_today_for_blank_value():
    assert parse_track_date("") == date.today()


def test_parse_track_date_rejects_invalid_format():
    with pytest.raises(ValueError, match="track_date"):
        parse_track_date("07/03/2026")


def test_format_track_date_uses_readable_month_name():
    assert format_track_date(date(2026, 7, 3)) == "July 03, 2026"


def test_track_artwork_prefers_track_background_over_artist_avatar():
    track = Track(
        original_filepath="song.mp3",
        stored_filepath="song.mp3",
        background_image_path="covers/song.jpg",
    )
    artist = Artist(name="Maya Vale", avatar_path="avatars/maya.jpg")

    assert track_artwork_path(track, [artist]) == "covers/song.jpg"


def test_track_artwork_falls_back_to_first_artist_avatar():
    track = Track(original_filepath="song.mp3", stored_filepath="song.mp3")
    artist = Artist(name="Maya Vale", avatar_path="avatars/maya.jpg")

    assert track_artwork_path(track, [artist]) == "avatars/maya.jpg"
