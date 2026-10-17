"""Initial design priors, not measured demographic or architectural statistics.

Profiles do not supply evidence and never override explicit intent. They become
inputs to future planners; phase 0 only defines and validates the vocabulary.
"""
PROFILES = {
    'barranco_residential': dict(use='residential', construction='masonry', finish='complete', evolution='unitary', maintenance='intermediate', occupancy='medium'),
    'barranco_incremental': dict(use='residential', construction='mixed', finish='partial', evolution='incremental', maintenance='intermediate', occupancy='high'),
    'barranco_casona': dict(use='residential', construction='mixed', finish='complete', evolution='adapted', maintenance='intermediate', occupancy='medium'),
    'barranco_mixed_use': dict(use='mixed', construction='masonry', finish='complete', evolution='adapted', maintenance='intermediate', occupancy='high'),
}

COMPLETION = dict(enabled=True, interiors=True, roof_objects=True,
                  evidence_required=False, mixed_styles=True)


def profile_for(name='barranco_residential'):
    return {**PROFILES[name], **COMPLETION}
