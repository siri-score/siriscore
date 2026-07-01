def is_silent_payment_address(address: str) -> bool:
    """Return True if address is a BIP-352 silent payment address (any network)."""
    return address.startswith(("sp1q", "tsp1q"))  # mainnet / testnet + regtest
