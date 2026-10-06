# Mock Redis cache for replay prevention
_used_hashes = set()

async def mark_hash_used(tx_hash: str) -> bool:
    """
    Marks a hash as used. Returns False if already used.
    """
    if tx_hash in _used_hashes:
        return False
    _used_hashes.add(tx_hash)
    return True
