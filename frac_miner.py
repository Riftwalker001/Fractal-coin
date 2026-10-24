#!/usr/bin/env python3
"""
FractalPoWToken (FRAC) — Old-PC Friendly Single-Thread CPU Miner
Supports:
  - Sequential-64 Keccak-256 PoW (zero external pip dependencies)
  - --auto-stake (calls mineAndStake(uint256) to auto-compound rewards in 1 tx)
  - Fractal Golden Block detection (1-in-64 Jackpot Pot indicator)
  - Automatic cooldown window sleep & --throttle-ms thermal control
"""

import argparse
import json
import os
import subprocess
import time
import urllib.request

_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]
_ROT = [
    [0, 36, 3, 41, 18],
    [1, 44, 10, 45, 2],
    [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56],
    [27, 20, 39, 8, 14],
]
_MASK64 = 0xFFFFFFFFFFFFFFFF


def _rol64(val: int, shift: int) -> int:
    return ((val << shift) | (val >> (64 - shift))) & _MASK64


def _keccak_f1600(state: list[int]) -> None:
    for rc in _RC:
        c = [state[x] ^ state[x + 5] ^ state[x + 10] ^ state[x + 15] ^ state[x + 20] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rol64(c[(x + 1) % 5], 1) for x in range(5)]
        for i in range(25):
            state[i] ^= d[i % 5]

        b = [0] * 25
        for x in range(5):
            for y in range(5):
                b[y + 5 * ((2 * x + 3 * y) % 5)] = _rol64(state[x + 5 * y], _ROT[x][y])

        for y in range(0, 25, 5):
            for x in range(5):
                state[y + x] = b[y + x] ^ ((~b[y + (x + 1) % 5]) & b[y + (x + 2) % 5])

        state[0] ^= rc


def _pure_keccak256(data: bytes) -> bytes:
    rate = 136
    state = [0] * 25
    padded = bytearray(data)
    padded.append(0x01)
    while len(padded) % rate != 0:
        padded.append(0x00)
    padded[-1] |= 0x80

    for offset in range(0, len(padded), rate):
        block = padded[offset : offset + rate]
        for i in range(17):
            lane = int.from_bytes(block[i * 8 : (i + 1) * 8], "little")
            state[i] ^= lane
        _keccak_f1600(state)

    out = bytearray()
    for i in range(4):
        out.extend(state[i].to_bytes(8, "little"))
    return bytes(out)


try:
    from Crypto.Hash import keccak as _c_keccak

    def keccak256(data: bytes) -> bytes:
        h = _c_keccak.new(digest_bits=256)
        h.update(data)
        return h.digest()
except ImportError:
    keccak256 = _pure_keccak256


SEQUENTIAL_STEPS = 64
STEP_BYTES = [i.to_bytes(32, "big") for i in range(SEQUENTIAL_STEPS)]


def compute_sequential_digest(challenge_bytes: bytes, miner_bytes20: bytes, nonce: int) -> bytes:
    nonce_bytes = nonce.to_bytes(32, "big")
    digest = keccak256(challenge_bytes + miner_bytes20 + nonce_bytes)
    for i in range(1, SEQUENTIAL_STEPS):
        digest = keccak256(digest + challenge_bytes + STEP_BYTES[i])
    return digest


def cast_call(rpc_url: str, contract: str, sig: str, *args: str) -> str:
    env = os.environ.copy()
    env["PATH"] = f"{os.path.expanduser('~/.foundry/bin')}:{env.get('PATH', '')}"
    cmd = ["cast", "call", "--rpc-url", rpc_url, contract, sig, *args]
    res = subprocess.run(cmd, capture_output=True, text=True, env=env, check=True)
    return res.stdout.strip().split()[0]


def cast_send(rpc_url: str, private_key: str, contract: str, sig: str, *args: str) -> str:
    env = os.environ.copy()
    env["PATH"] = f"{os.path.expanduser('~/.foundry/bin')}:{env.get('PATH', '')}"
    cmd = [
        "cast", "send",
        "--rpc-url", rpc_url,
        "--private-key", private_key,
        contract, sig, *args,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, env=env, check=True)
    return res.stdout.strip()


def get_address_from_key(private_key: str) -> str:
    env = os.environ.copy()
    env["PATH"] = f"{os.path.expanduser('~/.foundry/bin')}:{env.get('PATH', '')}"
    res = subprocess.run(
        ["cast", "wallet", "address", "--private-key", private_key],
        capture_output=True, text=True, env=env, check=True,
    )
    return res.stdout.strip()


def get_chain_timestamp(rpc_url: str) -> int:
    env = os.environ.copy()
    env["PATH"] = f"{os.path.expanduser('~/.foundry/bin')}:{env.get('PATH', '')}"
    res = subprocess.run(
        ["cast", "block", "latest", "--field", "timestamp", "--rpc-url", rpc_url],
        capture_output=True, text=True, env=env, check=True,
    )
    return int(res.stdout.strip().split()[0])


def mine_loop(
    rpc_url: str,
    contract: str,
    private_key: str,
    max_epochs: int = 0,
    throttle_ms: float = 0.0,
    auto_stake: bool = False,
    start_nonce: int = 0,
) -> None:
    miner_addr = get_address_from_key(private_key)
    miner_bytes20 = bytes.fromhex(miner_addr[2:].lower())
    fn_sig = "mineAndStake(uint256)" if auto_stake else "mine(uint256)"
    mode_label = "AUTO-STAKE (Compound to Staking Pool)" if auto_stake else "DIRECT WALLET PAYOUT"

    print("\033[92m" + "=" * 68)
    print("  FRACTAL PoW COIN (FRAC) // OLD-PC SEQUENTIAL-64 CPU MINER")
    print("=" * 68 + "\033[0m")
    print(f"  Miner Address : {miner_addr}")
    print(f"  Contract      : {contract}")
    print(f"  RPC URL       : {rpc_url}")
    print(f"  Payout Mode   : {mode_label}\n")

    mined_count = 0
    while True:
        try:
            challenge_hex = cast_call(rpc_url, contract, "challengeNumber()(bytes32)")
            target_int = int(cast_call(rpc_url, contract, "effectiveTarget()(uint256)"))
            epoch_int = int(cast_call(rpc_url, contract, "epochCount()(uint256)"))
            jackpot_wei = int(cast_call(rpc_url, contract, "jackpotPot()(uint256)"))
            last_miner = cast_call(rpc_url, contract, "lastMiner()(address)")
            last_time = int(cast_call(rpc_url, contract, "lastEpochTime()(uint256)"))
            target_window = int(cast_call(rpc_url, contract, "TARGET_EPOCH_TIME()(uint256)"))
            chain_now = get_chain_timestamp(rpc_url)

            if epoch_int > 0 and last_miner.lower() == miner_addr.lower() and chain_now < last_time + target_window:
                wait_secs = (last_time + target_window) - chain_now
                print(
                    f"[Epoch #{epoch_int + 1}] Cooldown active (Old-PC fairness window). "
                    f"Sleeping {wait_secs}s...",
                    flush=True,
                )
                time.sleep(min(wait_secs + 2, 30))
                continue

            challenge_bytes = bytes.fromhex(challenge_hex[2:])
            print(
                f"[Epoch #{epoch_int + 1}] Challenge: {challenge_hex[:18]}... | "
                f"Golden Jackpot Pot: {jackpot_wei / 1e18:,.2f} FRAC",
                flush=True,
            )

            nonce = start_nonce
            t0 = time.time()
            while True:
                digest = compute_sequential_digest(challenge_bytes, miner_bytes20, nonce)
                digest_int = int.from_bytes(digest, "big")
                if digest_int <= target_int:
                    elapsed = max(time.time() - t0, 0.001)
                    rate = (nonce - start_nonce + 1) / elapsed
                    is_golden = (digest[-1] & 0x3F) == 0x3F
                    golden_tag = " \033[93m*** FRACTAL GOLDEN BLOCK HIT! (JACKPOT WON!) ***\033[0m" if is_golden else ""
                    print(
                        f"  [+] Valid PoW found! Nonce={nonce} | Attempts={nonce - start_nonce + 1} "
                        f"({elapsed:.2f}s, {rate:.0f} seq-chains/s){golden_tag}",
                        flush=True,
                    )
                    print(f"  [+] Submitting transaction {fn_sig} with nonce={nonce}...", flush=True)
                    cast_send(rpc_url, private_key, contract, fn_sig, str(nonce))
                    bal_wei = int(cast_call(rpc_url, contract, "balanceOf(address)(uint256)", miner_addr))
                    staked_wei = int(cast_call(rpc_url, contract, "stakedBalance(address)(uint256)", miner_addr))
                    pending_wei = int(cast_call(rpc_url, contract, "pendingRewards(address)(uint256)", miner_addr))
                    print(
                        f"  [*] Epoch #{epoch_int + 1} Mined! Wallet: {bal_wei / 1e18:,.2f} FRAC | "
                        f"Staked: {staked_wei / 1e18:,.2f} FRAC | Pending Rewards: {pending_wei / 1e18:,.4f} FRAC\n",
                        flush=True,
                    )
                    mined_count += 1
                    break

                nonce += 1
                if throttle_ms > 0 and (nonce % 50 == 0):
                    time.sleep(throttle_ms / 1000.0)
                if nonce % 2000 == 0:
                    latest_challenge = cast_call(rpc_url, contract, "challengeNumber()(bytes32)")
                    if latest_challenge.lower() != challenge_hex.lower():
                        print("  [!] Another miner solved this epoch. Fetching new challenge...", flush=True)
                        break

            if max_epochs > 0 and mined_count >= max_epochs:
                print(f"Completed target of {max_epochs} mined epoch(s). Exiting.", flush=True)
                break
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"  [!] Transient RPC/tx warning ({exc}); retrying in 5s...", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FractalPoWToken (FRAC) Old-PC CPU Miner (Base Mainnet)")
    parser.add_argument("--rpc-url", default="https://mainnet.base.org", help="Base Mainnet JSON-RPC URL")
    parser.add_argument(
        "--contract",
        default="your miner address",
        help="Official FractalPoWToken (FRAC) contract address on Base Mainnet",
    )
    parser.add_argument("--private-key", default="", help="Miner wallet private key (or set FRAC_PRIVATE_KEY env var)")
    parser.add_argument("--epochs", type=int, default=0, help="Number of epochs to mine (0 = continuous 24/7 mining)")
    parser.add_argument("--throttle-ms", type=float, default=0.0, help="Sleep ms every 50 nonces to keep old CPUs cool")
    parser.add_argument("--auto-stake", action="store_true", help="Call mineAndStake() to auto-compound rewards")
    args = parser.parse_args()

    priv_key = args.private_key.strip() or os.environ.get("FRAC_PRIVATE_KEY", "").strip()
    auto_stake = args.auto_stake
    if not priv_key:
        print("\033[92m=== FRAC STANDALONE OLD-PC CPU MINER SETUP (BASE MAINNET) ===\033[0m")
        priv_key = input("Enter your Miner Wallet Private Key (0x...): ").strip()
        if not priv_key:
            raise SystemExit("Error: A valid Base Mainnet wallet private key (with ~$0.05 ETH for gas) is required.")
        if not auto_stake:
            ans = input("Auto-stake mined FRAC into the 3.5% Loyalty Pool? [Y/n]: ").strip().lower()
            auto_stake = ans in ("", "y", "yes")

    mine_loop(
        rpc_url=args.rpc_url,
        contract=args.contract,
        private_key=priv_key,
        max_epochs=args.epochs,
        throttle_ms=args.throttle_ms,
        auto_stake=auto_stake,
    )

