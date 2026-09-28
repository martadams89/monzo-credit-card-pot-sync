def test_home_get_contains_jumbotron(test_client):
    response = test_client.get("/")
    assert response.status_code == 200
    assert b"Simplify Your Spend" in response.data


def test_home_post_invalid_method(test_client):
    response = test_client.post("/")
    assert response.status_code == 405


def test_stylesheet_url_is_versioned_by_content(test_client):
    import re

    html = test_client.get("/").data.decode()
    match = re.search(r'href="/static/css/dist/output\.css\?v=([^"]+)"', html)
    assert match
    # A 12 character content hash, or "dev" when the stylesheet has not been built.
    assert re.fullmatch(r"[0-9a-f]{12}|dev", match.group(1))


def test_static_version_changes_with_stylesheet_content(tmp_path):
    from types import SimpleNamespace

    from app import _static_version

    css = tmp_path / "css" / "dist" / "output.css"
    app = SimpleNamespace(static_folder=str(tmp_path))
    assert _static_version(app) == "dev"  # not built yet

    css.parent.mkdir(parents=True)
    css.write_text(".w-11{width:2.75rem}")
    first = _static_version(app)
    css.write_text(".w-11{width:2.75rem}.h-6{height:1.5rem}")
    assert _static_version(app) != first


def test_flash_messages_are_styled_and_dismissable(test_client, seed_data):
    response = test_client.post(
        "/accounts/pending_credits", data={"account_type": "American Express"}, follow_redirects=True
    )
    html = response.data.decode()
    assert 'role="status"' in html
    assert "text-green-800" in html
    assert 'aria-label="Dismiss"' in html
    assert "no longer counted for American Express" in html

    response = test_client.post("/accounts/pending_credits", data={"account_type": "Nope"}, follow_redirects=True)
    html = response.data.decode()
    assert 'role="alert"' in html
    assert "text-red-800" in html
