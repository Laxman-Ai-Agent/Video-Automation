"""Per-request memo for pure, repeatable lookups (input digests). Inside `scoped` a function wrapped with `memo` computes once per argument tuple; outside a scope it
always computes, so a stage that runs and then re-checks its inputs never sees an old answer. Used by the pipeline view, which asks the same freshness questions
dozens of times per request."""
import contextvars
import copy
import functools

_cache: contextvars.ContextVar = contextvars.ContextVar("request_memo", default=None)


def scoped(fn):
    @functools.wraps(fn)
    def run(*a, **kw):
        token = _cache.set({})
        try:
            return fn(*a, **kw)
        finally:
            _cache.reset(token)
    return run


def memo(fn):
    @functools.wraps(fn)
    def run(*a):
        cache = _cache.get()
        if cache is None:
            return fn(*a)
        key = (fn.__module__, fn.__qualname__, a)
        try:
            hash(key)
        except TypeError:                                                      # an unhashable argument: nothing to key on, so compute
            return fn(*a)
        if key not in cache:
            cache[key] = fn(*a)
        return copy.copy(cache[key])
    return run
