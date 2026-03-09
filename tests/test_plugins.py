"""Tests for the plugin auto-discovery system."""

from lifescript.plugins import get_functions, get_descriptions, get_allowed_names


class TestPluginDiscovery:
    def test_all_functions_registered(self):
        funcs = get_functions()
        assert "fetch_time_now" in funcs
        assert "fetch_time_today" in funcs
        assert "notify_line" in funcs
        assert "fetch_weather" in funcs

    def test_functions_are_callable(self):
        for name, func in get_functions().items():
            assert callable(func), f"{name} is not callable"

    def test_descriptions_have_required_keys(self):
        for name, desc in get_descriptions().items():
            assert "signature" in desc, f"{name} missing 'signature'"
            assert "description" in desc, f"{name} missing 'description'"

    def test_allowed_names_match_functions(self):
        assert get_allowed_names() == set(get_functions().keys())


class TestTimePlugin:
    def test_fetch_time_now_returns_string(self):
        from lifescript.plugins.time_plugin import fetch_time_now

        result = fetch_time_now()
        assert isinstance(result, str)
        assert ":" in result  # HH:MM format

    def test_fetch_time_today_returns_dict(self):
        from lifescript.plugins.time_plugin import fetch_time_today

        result = fetch_time_today()
        assert isinstance(result, dict)
        assert "weekday" in result
        assert "date" in result
