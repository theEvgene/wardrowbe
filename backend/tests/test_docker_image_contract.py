from pathlib import Path


def test_rembg_models_are_cached_in_runtime_visible_location() -> None:
    dockerfile = (Path(__file__).parents[1] / "Dockerfile").read_text(encoding="utf-8")

    env_position = dockerfile.index("ENV U2NET_HOME=/opt/rembg")
    download_position = dockerfile.index("new_session('u2net_cloth_seg')")
    permissions_position = dockerfile.index('chmod -R a+rX "$U2NET_HOME"')

    assert env_position < download_position < permissions_position
    assert "for attempt in 1 2 3 4 5" in dockerfile
    assert 'test "$attempt" -eq 5 && exit 1' in dockerfile
