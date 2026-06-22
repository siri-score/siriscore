"""Bitcoin Core JSON-RPC backend — wraps getrawtransaction and gettxout only.

No wallet RPCs are called. H3 is skipped when this backend is active because
Bitcoin Core exposes no non-wallet address-history index.
"""
import logging

import requests

logger = logging.getLogger("siriscore.rpc")

REQUEST_TIMEOUT = (5, 30)


class RPCError(Exception):
    pass


class RPCBackend:
    # Sentinel read by _build_checks to mark H3 as unavailable.
    HAS_ADDRESS_INDEX = False

    def __init__(self, url: str, user: str = "", password: str = ""):
        self._url = url.rstrip("/")
        self._auth = (user, password)
        self._id = 0
        self._tx_cache: dict[str, dict] = {}

    def _call(self, method: str, params: list):
        self._id += 1
        payload = {
            "jsonrpc": "1.1",
            "id": self._id,
            "method": method,
            "params": params,
        }
        try:
            resp = requests.post(
                self._url,
                json=payload,
                auth=self._auth,
                timeout=REQUEST_TIMEOUT,
                headers={"Content-Type": "application/json"},
            )
        except requests.RequestException as exc:
            raise RPCError(f"RPC connection failed: {exc}") from exc

        if resp.status_code == 401:
            raise RPCError("RPC authentication failed — check rpc_user/rpc_password")
        if resp.status_code == 403:
            raise RPCError("RPC access denied — check Bitcoin Core rpcallowip config")

        try:
            data = resp.json()
        except ValueError as exc:
            raise RPCError(f"Invalid JSON from RPC: {exc}") from exc

        if data.get("error"):
            err = data["error"]
            raise RPCError(f"RPC error {err.get('code', '')}: {err.get('message', err)}")

        return data["result"]

    def getrawtransaction(self, txid: str) -> dict:
        """getrawtransaction txid True — requires txindex=1 on the node."""
        if txid in self._tx_cache:
            return self._tx_cache[txid]
        result = self._call("getrawtransaction", [txid, True])
        self._tx_cache[txid] = result
        return result

    def gettxout(self, txid: str, vout: int, include_mempool: bool = True) -> dict | None:
        """gettxout — returns None if the UTXO is already spent."""
        return self._call("gettxout", [txid, vout, include_mempool])

    def get_utxo_block_height(self, txid: str) -> int | None:
        """Block height for txid via getrawtransaction (Bitcoin Core ≥ 22 field)."""
        try:
            tx = self.getrawtransaction(txid)
        except RPCError as exc:
            logger.warning("rpc.get_utxo_block_height txid=%s error=%s", txid, exc)
            return None
        return tx.get("blockheight")

    def get_address_txs(self, address: str) -> list:
        """Non-wallet RPC has no address index — H3 is skipped with this backend."""
        logger.debug("rpc.get_address_txs address=%s skipped (no non-wallet address index)", address)
        return []
