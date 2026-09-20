import hashlib

def resolve_seed(seed: int, lot_id: str, mass_id: str, feature_id: str, purpose: str) -> int:
    """Generate a stable, deterministic integer seed independent of Python sessions."""
    key = f"{seed}_{lot_id}_{mass_id}_{feature_id}_{purpose}".encode('utf-8')
    # Use SHA-256 and truncate to standard 32-bit integer for numpy/random compatibility
    return int(hashlib.sha256(key).hexdigest()[:8], 16)
