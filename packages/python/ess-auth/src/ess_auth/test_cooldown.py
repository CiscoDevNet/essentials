"""Tests for the failure cooldown's escalation behaviour.

A fixed window is weak during a sustained outage. An identity platform that
refuses a cluster's shared egress address for 90 minutes straight will, at a
flat 60s window, still admit roughly 90 attempts per event loop, each one
feeding the rate limiter doing the refusing. Doubling towards an hourly cap
cuts the same period to single figures.
"""

from __future__ import annotations

from ess_auth.cooldown import _JITTER_FRACTION, FailureCooldown


def _cooldown(**kwargs: float) -> FailureCooldown:
    return FailureCooldown(cooldown_secs=60.0, max_cooldown_secs=3600.0, **kwargs)


class TestEscalation:
    def test_window_doubles_on_consecutive_failures(self) -> None:
        cooldown = _cooldown()
        windows = [cooldown.start() for _ in range(5)]

        # Jitter only ever extends a window, so each sits in [raw, raw * 1.2].
        for attempt, window in enumerate(windows, start=1):
            raw = 60.0 * (2 ** (attempt - 1))
            assert raw <= window <= raw * (1 + _JITTER_FRACTION), (
                f"attempt {attempt}: {window} outside [{raw}, {raw * 1.2}]"
            )

    def test_window_is_capped(self) -> None:
        """Without a ceiling, doubling would eventually park the breaker shut."""
        cooldown = _cooldown()
        for _ in range(20):
            window = cooldown.start()

        assert window <= 3600.0 * (1 + _JITTER_FRACTION)

    def test_success_resets_escalation(self) -> None:
        """A blip must not leave the breaker on a long window afterwards."""
        failures_before_success = 4
        cooldown = _cooldown()
        for _ in range(failures_before_success):
            cooldown.start()
        assert cooldown.consecutive_failures == failures_before_success

        cooldown.clear()
        assert cooldown.consecutive_failures == 0
        assert cooldown.remaining() == 0.0

        first_window_again = cooldown.start()
        assert first_window_again <= 60.0 * (1 + _JITTER_FRACTION)

    def test_escalation_beats_a_flat_window_over_a_long_outage(self) -> None:
        """The property that motivated escalation, stated as a test.

        Ninety minutes of continuous refusal should cost single-figure
        attempts, not ~90.
        """
        outage_secs = 90 * 60
        cooldown = _cooldown()

        elapsed = 0.0
        attempts = 0
        while elapsed < outage_secs:
            elapsed += cooldown.start()
            attempts += 1

        flat_window_attempts = outage_secs / 60
        single_figures = 10
        worthwhile_reduction = 5
        assert attempts < single_figures
        assert attempts < flat_window_attempts / worthwhile_reduction


class TestHold:
    def test_hold_suppresses_without_counting_a_failure(self) -> None:
        """An upstream-requested wait is not evidence the endpoint is broken."""
        cooldown = _cooldown()

        cooldown.hold(30.0)

        assert cooldown.remaining() > 0
        assert cooldown.consecutive_failures == 0

    def test_hold_never_shortens_an_open_window(self) -> None:
        cooldown = _cooldown()
        window = cooldown.start()

        cooldown.hold(1.0)

        assert cooldown.remaining() > window - 1.0

    def test_non_positive_hold_is_ignored(self) -> None:
        cooldown = _cooldown()

        cooldown.hold(0.0)

        assert cooldown.remaining() == 0.0


class TestJitter:
    def test_jitter_desynchronises_a_fleet(self) -> None:
        """Pods that start together must not probe in lockstep."""
        windows = {_cooldown().start() for _ in range(50)}

        assert len(windows) > 1
