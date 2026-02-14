"""Command retry mixin for HeishaMon entities."""
from __future__ import annotations
import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

_LOGGER = logging.getLogger(__name__)


@dataclass
class PendingCommand:
    """Represents a command awaiting confirmation."""
    expected_value: Any
    sent_at: float
    retry_count: int
    retry_callback: Callable
    tolerance: Optional[float] = None


class CommandRetryMixin:
    """Mixin to add command retry capability to HeishaMon entities.

    This mixin provides automatic retry logic for commands that may be dropped
    by HeishaMon when it's busy communicating with the heat pump.

    Usage:
    1. Inherit from this mixin in your entity class
    2. Call register_command() after sending a command via MQTT
    3. Call verify_command_confirmation() when receiving state updates
    4. The mixin handles retries automatically if confirmation not received
    """

    # Constants
    RETRY_TIMEOUT = 10.0  # seconds (base timeout)
    RETRY_JITTER = 2.0    # seconds (total jitter range: ±1 second)
    MAX_RETRIES = 3

    def __init__(self, *args, **kwargs):
        """Initialize the retry mixin."""
        super().__init__(*args, **kwargs)
        self._pending_command: Optional[PendingCommand] = None
        self._retry_task: Optional[asyncio.Task] = None
        self._total_retries: int = 0
        self._failed_commands: int = 0
        self._last_retry_time: Optional[datetime] = None

    async def register_command(
        self,
        expected_value: Any,
        retry_callback: Callable,
        tolerance: Optional[float] = None,
    ) -> None:
        """Register a command that needs confirmation.

        Args:
            expected_value: The value we expect to see in the state update
            retry_callback: Async function to call if retry is needed
            tolerance: Optional tolerance for numeric comparisons (e.g., 0.1 for temperature)
        """
        # Cancel any existing pending command
        if self._pending_command is not None:
            _LOGGER.debug(
                f"{self.name}: Superseding pending command (expected: {self._pending_command.expected_value}) "
                f"with new command (expected: {expected_value})"
            )
            self._cancel_pending_command()

        # Create new pending command
        self._pending_command = PendingCommand(
            expected_value=expected_value,
            sent_at=asyncio.get_event_loop().time(),
            retry_count=0,
            retry_callback=retry_callback,
            tolerance=tolerance,
        )

        _LOGGER.debug(
            f"{self.name}: Registered command expecting value: {expected_value}"
        )

        # Schedule retry with jitter
        await self._schedule_retry()

    def verify_command_confirmation(self, received_value: Any) -> None:
        """Verify if received state update confirms our pending command.

        Args:
            received_value: The value received in the state update
        """
        if self._pending_command is None:
            return

        # Check if values match (with tolerance for numeric values)
        if self._values_match(received_value, self._pending_command.expected_value, self._pending_command.tolerance):
            _LOGGER.debug(
                f"{self.name}: Command confirmed (expected: {self._pending_command.expected_value}, "
                f"received: {received_value}, retries: {self._pending_command.retry_count})"
            )
            self._cancel_pending_command()
        else:
            _LOGGER.debug(
                f"{self.name}: Received value {received_value} does not match expected {self._pending_command.expected_value}, "
                f"waiting for confirmation or retry"
            )

    def _values_match(self, value1: Any, value2: Any, tolerance: Optional[float]) -> bool:
        """Check if two values match, with optional tolerance for numeric values.

        Args:
            value1: First value to compare
            value2: Second value to compare
            tolerance: Optional tolerance for numeric comparisons

        Returns:
            True if values match (within tolerance if specified)
        """
        if tolerance is not None and isinstance(value1, (int, float)) and isinstance(value2, (int, float)):
            return abs(float(value1) - float(value2)) <= tolerance
        return value1 == value2

    async def _schedule_retry(self) -> None:
        """Schedule a retry after timeout with jitter."""
        if self._retry_task is not None:
            self._retry_task.cancel()

        delay = self._calculate_retry_delay()
        self._retry_task = asyncio.create_task(self._execute_retry(delay))

    def _calculate_retry_delay(self) -> float:
        """Calculate retry delay with random jitter.

        Returns:
            Delay in seconds with jitter applied
        """
        # Add random jitter: RETRY_TIMEOUT ± (RETRY_JITTER / 2)
        jitter = random.uniform(-self.RETRY_JITTER / 2, self.RETRY_JITTER / 2)
        return self.RETRY_TIMEOUT + jitter

    async def _execute_retry(self, delay: float) -> None:
        """Execute retry after delay.

        Args:
            delay: Seconds to wait before retrying
        """
        try:
            await asyncio.sleep(delay)

            if self._pending_command is None:
                return

            # Check if we've exceeded max retries
            if self._pending_command.retry_count >= self.MAX_RETRIES:
                _LOGGER.warning(
                    f"{self.name}: Command failed after {self.MAX_RETRIES} retries "
                    f"(expected value: {self._pending_command.expected_value})"
                )
                self._failed_commands += 1
                self._cancel_pending_command()
                return

            # Execute retry
            self._pending_command.retry_count += 1
            self._total_retries += 1
            self._last_retry_time = datetime.now()

            _LOGGER.info(
                f"{self.name}: Retrying command (attempt {self._pending_command.retry_count}/{self.MAX_RETRIES}, "
                f"expected value: {self._pending_command.expected_value})"
            )

            # Call the retry callback
            await self._pending_command.retry_callback()

            # Schedule next retry
            await self._schedule_retry()

        except asyncio.CancelledError:
            # Task was cancelled, this is expected
            pass
        except Exception as e:
            _LOGGER.error(
                f"{self.name}: Error during retry execution: {e}",
                exc_info=True
            )

    def _cancel_pending_command(self) -> None:
        """Cancel pending command and associated retry task."""
        self._pending_command = None

        if self._retry_task is not None:
            self._retry_task.cancel()
            self._retry_task = None

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        self._cancel_pending_command()
        await super().async_will_remove_from_hass()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic attributes for monitoring retry behavior."""
        # Get base attributes from parent class if they exist
        base_attrs = {}
        if hasattr(super(), 'extra_state_attributes'):
            parent_attrs = super().extra_state_attributes
            if parent_attrs is not None:
                base_attrs = parent_attrs

        retry_attrs = {
            "retry_total_retries": self._total_retries,
            "retry_failed_commands": self._failed_commands,
            "retry_pending_command": self._pending_command is not None,
        }

        if self._last_retry_time is not None:
            retry_attrs["retry_last_retry_time"] = self._last_retry_time.isoformat()

        if self._pending_command is not None:
            retry_attrs["retry_pending_value"] = str(self._pending_command.expected_value)
            retry_attrs["retry_pending_attempts"] = self._pending_command.retry_count

        return {**base_attrs, **retry_attrs}
