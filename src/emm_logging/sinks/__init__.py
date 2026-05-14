"""Public sink builders for emm_logging.

Each sink module exposes a ``build_<name>_sink(settings)`` function returning a
``(handler_or_flag, warnings)`` tuple. Sinks degrade gracefully when their
optional dependency is missing; the warnings list communicates the degradation
so callers can surface it to operators.
"""
