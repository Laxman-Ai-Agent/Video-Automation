from SYSTEM.core.request_memo import memo, scoped

calls = []


@memo
def digest(*parts):
    calls.append(parts)
    return {"d": parts}


@scoped
def view():
    a, b, c = digest("x", 1), digest("x", 1), digest(["unhashable"])
    b["d"] = "changed"                                  # a caller changing its copy must not change the cached answer
    return a, digest("x", 1), c


def test_computes_once_per_scope_and_always_outside():
    calls.clear()
    a, again, _ = view()
    assert a == again == {"d": ("x", 1)} and calls.count(("x", 1)) == 1
    digest("x", 1), digest("x", 1)
    assert calls.count(("x", 1)) == 3                   # outside a scope every call computes: a stage never re-checks against an old answer
    view()
    assert calls.count(("x", 1)) == 4                   # a new scope starts empty
