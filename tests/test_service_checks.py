import unittest

from app.services.service_checks import (
    HttpTarget,
    TcpTarget,
    _safe_url,
    get_timeout_seconds,
    load_targets,
)


class ServiceCheckConfigurationTests(unittest.TestCase):
    def test_loads_explicit_http_and_tcp_targets(self) -> None:
        targets = load_targets(
            '[{"name":"NOC Agent Health","type":"http",'
            '"url":"http://127.0.0.1:8000/health"},'
            '{"name":"Local SSH","type":"tcp",'
            '"host":"127.0.0.1","port":22}]'
        )

        self.assertEqual(
            targets,
            [
                HttpTarget(
                    name="NOC Agent Health",
                    url="http://127.0.0.1:8000/health",
                    type="http",
                ),
                TcpTarget(name="Local SSH", host="127.0.0.1", port=22),
            ],
        )

    def test_rejects_credentials_in_http_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not contain credentials"):
            load_targets(
                '[{"name":"Private","type":"https",'
                '"url":"https://user:password@example.test/health"}]'
            )

    def test_rejects_invalid_tcp_port(self) -> None:
        with self.assertRaisesRegex(ValueError, "port from 1 to 65535"):
            load_targets('[{"name":"Bad","type":"tcp","host":"localhost","port":0}]')

    def test_sanitizes_query_and_fragment_from_url(self) -> None:
        self.assertEqual(
            _safe_url("https://example.test:8443/health?token=secret#details"),
            "https://example.test:8443/health",
        )

    def test_timeout_is_bounded(self) -> None:
        self.assertEqual(get_timeout_seconds("2.5"), 2.5)
        for value in ("0", "30.1", "not-a-number"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                get_timeout_seconds(value)


if __name__ == "__main__":
    unittest.main()
