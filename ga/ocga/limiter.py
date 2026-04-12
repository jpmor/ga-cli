"""Adaptive concurrency limiter for the OCGA fetcher."""

import threading


class AdaptiveLimiter:
    def __init__(self, initial: int = 2):
        self._limit = initial
        self._active = 0
        self._successes = 0
        self._cv = threading.Condition(threading.Lock())

    def set_initial(self, n: int):
        with self._cv:
            self._limit = max(1, n)
            self._cv.notify_all()

    def acquire(self):
        with self._cv:
            while self._active >= self._limit:
                self._cv.wait()
            self._active += 1

    def release(self):
        with self._cv:
            self._active -= 1
            self._cv.notify_all()

    def on_success(self):
        with self._cv:
            self._successes += 1
            if self._successes >= 100 and self._limit < 6:
                self._limit += 1
                self._successes = 0
                print(f"  [concurrency → {self._limit}]", flush=True)
                self._cv.notify_all()

    def on_rate_limit(self):
        with self._cv:
            self._successes = 0
            if self._limit > 1:
                self._limit = 1
                print(f"  [concurrency → 1]", flush=True)
