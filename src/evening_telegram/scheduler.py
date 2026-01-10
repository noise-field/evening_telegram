"""Scheduler for managing subscription schedules."""

import asyncio
from datetime import datetime, time, timedelta, timezone
from typing import Callable, Optional

import structlog

from .config.models import ScheduleConfig

logger = structlog.get_logger()


class SubscriptionScheduler:
    """Manages scheduling for a single subscription."""

    def __init__(
        self,
        subscription_id: str,
        subscription_name: str,
        schedule: ScheduleConfig,
        callback: Callable,
    ):
        """
        Initialize the scheduler.

        Args:
            subscription_id: Unique ID for the subscription
            subscription_name: Human-readable name
            schedule: Schedule configuration
            callback: Async function to call when schedule triggers
        """
        self.subscription_id = subscription_id
        self.subscription_name = subscription_name
        self.schedule = schedule
        self.callback = callback
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def get_next_run_time(self, current_time: Optional[datetime] = None) -> datetime:
        """
        Calculate the next run time based on the schedule.

        Args:
            current_time: Current time (defaults to now)

        Returns:
            Next scheduled run time
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # Weekly schedule
        if self.schedule.day_of_week is not None and self.schedule.time:
            target_time = time.fromisoformat(self.schedule.time)
            target_weekday = self.schedule.day_of_week

            # Calculate days until target weekday
            current_weekday = current_time.weekday()
            days_ahead = target_weekday - current_weekday

            if days_ahead < 0:  # Target day already happened this week
                days_ahead += 7
            elif days_ahead == 0:  # Today is the target day
                # Check if the time has passed
                current_time_only = current_time.time()
                if current_time_only >= target_time:
                    # Time has passed, schedule for next week
                    days_ahead = 7

            next_run = current_time.replace(
                hour=target_time.hour,
                minute=target_time.minute,
                second=0,
                microsecond=0,
            ) + timedelta(days=days_ahead)

            return next_run

        # Daily or multiple times per day schedule
        elif self.schedule.times:
            times = [time.fromisoformat(t) for t in self.schedule.times]
            current_time_only = current_time.time()

            # Find the next time today
            for target_time in sorted(times):
                if target_time > current_time_only:
                    # Found a time later today
                    next_run = current_time.replace(
                        hour=target_time.hour,
                        minute=target_time.minute,
                        second=0,
                        microsecond=0,
                    )
                    return next_run

            # No time remaining today, use first time tomorrow
            target_time = sorted(times)[0]
            next_run = (current_time + timedelta(days=1)).replace(
                hour=target_time.hour,
                minute=target_time.minute,
                second=0,
                microsecond=0,
            )
            return next_run

        # Fallback: run every hour (shouldn't happen with valid config)
        else:
            logger.warning(
                "No valid schedule configuration, defaulting to hourly",
                subscription=self.subscription_name,
            )
            return current_time + timedelta(hours=1)

    def get_next_n_run_times(self, n: int = 5) -> list[datetime]:
        """
        Get the next N scheduled run times.

        Args:
            n: Number of run times to calculate

        Returns:
            List of next N run times
        """
        run_times = []
        current = datetime.now(timezone.utc)

        for _ in range(n):
            next_run = self.get_next_run_time(current)
            run_times.append(next_run)
            current = next_run + timedelta(seconds=1)  # Move past this run time

        return run_times

    async def run(self) -> None:
        """Run the scheduler loop."""
        logger.info(
            "Starting scheduler",
            subscription=self.subscription_name,
            subscription_id=self.subscription_id,
        )

        while not self._stop_event.is_set():
            try:
                # Calculate next run time
                next_run = self.get_next_run_time()
                now = datetime.now(timezone.utc)
                sleep_seconds = (next_run - now).total_seconds()

                logger.info(
                    "Next run scheduled",
                    subscription=self.subscription_name,
                    next_run=next_run.isoformat(),
                    sleep_seconds=int(sleep_seconds),
                )

                # Wait until the next run time or stop event
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=sleep_seconds
                    )
                    # Stop event was set, exit the loop
                    break
                except asyncio.TimeoutError:
                    # Timeout reached, time to run the callback
                    pass

                # Execute the callback
                logger.info(
                    "Executing scheduled run",
                    subscription=self.subscription_name,
                    subscription_id=self.subscription_id,
                )

                try:
                    await self.callback()
                    logger.info(
                        "Scheduled run completed",
                        subscription=self.subscription_name,
                    )
                except Exception as e:
                    logger.error(
                        "Error in scheduled run",
                        subscription=self.subscription_name,
                        error=str(e),
                        exc_info=True,
                    )

            except Exception as e:
                logger.error(
                    "Error in scheduler loop",
                    subscription=self.subscription_name,
                    error=str(e),
                    exc_info=True,
                )
                # Wait a bit before retrying
                await asyncio.sleep(60)

        logger.info(
            "Scheduler stopped",
            subscription=self.subscription_name,
            subscription_id=self.subscription_id,
        )

    def start(self) -> None:
        """Start the scheduler as a background task."""
        if self._task is None or self._task.done():
            self._stop_event.clear()
            self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        """Stop the scheduler."""
        if self._task and not self._task.done():
            self._stop_event.set()
            await self._task
