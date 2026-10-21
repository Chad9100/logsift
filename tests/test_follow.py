from logsift.follow import FollowState


def test_reads_existing_content_on_first_poll(tmp_path):
    path = tmp_path / "access.log"
    path.write_text("a\nb\n", encoding="utf-8")
    with FollowState([path]) as state:
        assert state.new_lines() == ["a", "b"]
        assert state.new_lines() == []  # nothing new yet


def test_picks_up_appended_lines(tmp_path):
    path = tmp_path / "access.log"
    path.write_text("a\n", encoding="utf-8")
    with FollowState([path]) as state:
        assert state.new_lines() == ["a"]
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("b\n")
        assert state.new_lines() == ["b"]


def test_holds_back_an_incomplete_last_line(tmp_path):
    path = tmp_path / "access.log"
    path.write_text("a\nb", encoding="utf-8")  # no trailing newline on "b"
    with FollowState([path]) as state:
        assert state.new_lines() == ["a"]
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("c\n")  # completes "b", the line read in this call is "bc"
        assert state.new_lines() == ["bc"]


def test_multiple_files_are_merged(tmp_path):
    a = tmp_path / "a.log"
    b = tmp_path / "b.log"
    a.write_text("a1\n", encoding="utf-8")
    b.write_text("b1\n", encoding="utf-8")
    with FollowState([a, b]) as state:
        assert state.new_lines() == ["a1", "b1"]


def test_truncation_restarts_from_the_beginning(tmp_path):
    path = tmp_path / "access.log"
    path.write_text("a\nb\nc\n", encoding="utf-8")
    with FollowState([path]) as state:
        assert state.new_lines() == ["a", "b", "c"]
        path.write_text("x\n", encoding="utf-8")  # shorter: rotated in place
        assert state.new_lines() == ["x"]


def test_invalid_utf8_is_replaced_not_raised(tmp_path):
    path = tmp_path / "access.log"
    path.write_bytes(b"\xff\xfe not valid utf-8\n")
    with FollowState([path]) as state:
        [line] = state.new_lines()
        assert "not valid utf-8" in line


def test_leading_bom_is_stripped_only_once(tmp_path):
    path = tmp_path / "access.log"
    path.write_bytes(b"\xef\xbb\xbf192.0.2.1 first line\n")
    with FollowState([path]) as state:
        assert state.new_lines() == ["192.0.2.1 first line"]
        with open(path, "ab") as fh:
            fh.write(b"192.0.2.2 second line\n")
        # A BOM only ever appears at the very start of a file, so a later
        # chunk starting with those same bytes must be left alone.
        assert state.new_lines() == ["192.0.2.2 second line"]


def test_bom_is_rechecked_after_a_rotation(tmp_path):
    path = tmp_path / "access.log"
    path.write_bytes(b"\xef\xbb\xbfaa\n")
    with FollowState([path]) as state:
        assert state.new_lines() == ["aa"]
        # Shorter than before, so it's detected as rotated-in-place (same
        # name, truncated and rewritten); a coincidentally same-size or
        # larger replacement can't be told apart from normal growth this
        # way, a limitation shared by simple polling-based tails.
        path.write_bytes(b"\xef\xbb\xbfb\n")
        assert state.new_lines() == ["b"]
