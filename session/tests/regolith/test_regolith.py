"""Regolith profile: extension point. Each placeholder names the Task that fills it.

Run with: run.sh --profile regolith --packages "<regolith packages>" --repo copr:@regolith/regolith-unstable
When a Task fills a test, it also overrides the `session_config` fixture in a
conftest.py next to this file (e.g. the installed Regolith sway session config).
"""
import pytest


@pytest.mark.skip(reason="03-02: sway-regolith reads trawl resources (set_from_resource) and falls back to defaults")
def test_trawl_resource_read(session):
    pass


@pytest.mark.skip(reason="06-02: launcher (ilia) opens from its keybinding")
def test_launcher(session):
    pass


@pytest.mark.skip(reason="06-02: bar is present and shows i3status-rust content")
def test_bar(session):
    pass


@pytest.mark.skip(reason="06-02: notifications daemon owns org.freedesktop.Notifications and shows a notification")
def test_notifications(session):
    pass


@pytest.mark.skip(reason="06-02: lock screen starts and locks the session")
def test_lock_screen(session):
    pass


@pytest.mark.skip(reason="06-02: look switch changes the bar and window colours")
def test_look_switch(session):
    pass


@pytest.mark.skip(reason="06-02: settings app (regolith-control-center) opens")
def test_settings_app(session):
    pass
