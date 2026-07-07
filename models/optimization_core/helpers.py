def require_parent_sets(block):
    """Validate parent model has timepoints, periods, delta_t. Return them."""
    m = block.model()
    for attr in ('timepoints', 'periods', 'delta_t'):
        if not hasattr(m, attr):
            raise AttributeError(f"Parent model missing '{attr}'")
    return m.timepoints, m.periods, m.delta_t
