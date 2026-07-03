import logging
import time

import requests

BASES = [
    "https://blockstream.info/api",
    "https://mempool.space/api",
]
REQUEST_TIMEOUT = (1, 8)
_cache = {}
_hex_cache = {}
_address_cache = {}
logger = logging.getLogger("siriscore.lookup")


def get_tx(txid: str) -> dict:
    if txid in _cache:
        logger.info("lookup.cache_hit kind=tx txid=%s", txid)
        return _cache[txid]
    _cache[txid] = _get_json(f"/tx/{txid}")
    return _cache[txid]


def get_tx_hex(txid: str) -> str:
    if txid in _hex_cache:
        logger.info("lookup.cache_hit kind=hex txid=%s", txid)
        return _hex_cache[txid]

    tx = get_tx(txid)
    if "hex" in tx:
        _hex_cache[txid] = tx["hex"]
        return _hex_cache[txid]

    _hex_cache[txid] = _get_text(f"/tx/{txid}/hex")
    return _hex_cache[txid]


def get_address_txs(address: str) -> list:
    if address in _address_cache:
        logger.info("lookup.cache_hit kind=address address=%s", address)
        return _address_cache[address]
    _address_cache[address] = _get_json(f"/address/{address}/txs")
    return _address_cache[address]


def get_utxo_block_height(txid: str) -> int | None:
    tx = get_tx(txid)
    return tx.get("status", {}).get("block_height")


def _get_json(path: str):
    return _request_with_fallback(path).json()


def _get_text(path: str) -> str:
    return _request_with_fallback(path).text.strip()


def _request_with_fallback(path: str):
    last_error = None
    for index, base in enumerate(BASES):
        provider = _provider_name(base)
        started = time.perf_counter()
        try:
            if index > 0:
                logger.warning("lookup.fallback provider=%s path=%s", provider, path)
            else:
                logger.info("lookup.request provider=%s path=%s", provider, path)
            response = requests.get(f"{base}{path}", timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            elapsed_ms = (time.perf_counter() - started) * 1000
            log_success = logger.warning if index > 0 else logger.info
            log_success(
                "lookup.success provider=%s path=%s status=%s elapsed_ms=%.1f",
                provider,
                path,
                response.status_code,
                elapsed_ms,
            )
            return response
        except requests.RequestException as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.warning(
                "lookup.fail provider=%s path=%s elapsed_ms=%.1f error=%s",
                provider,
                path,
                elapsed_ms,
                exc,
            )
            last_error = exc

    raise last_error


def _provider_name(base: str) -> str:
    if "mempool.space" in base:
        return "mempool"
    if "blockstream.info" in base:
        return "blockstream"
    return base
