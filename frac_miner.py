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
import sys
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


def get_eth_balance(rpc_url: str, addr: str) -> float:
    env = os.environ.copy()
    env["PATH"] = f"{os.path.expanduser('~/.foundry/bin')}:{env.get('PATH', '')}"
    try:
        res = subprocess.run(
            ["cast", "balance", "--rpc-url", rpc_url, addr],
            capture_output=True, text=True, env=env, check=True,
        )
        return int(res.stdout.strip().split()[0]) / 1e18
    except Exception:
        return 0.0


def get_wallet_balances(rpc_url: str, contract: str, addr: str) -> dict:
    bal_wei = int(cast_call(rpc_url, contract, "balanceOf(address)(uint256)", addr))
    staked_wei = int(cast_call(rpc_url, contract, "stakedBalance(address)(uint256)", addr))
    pending_wei = int(cast_call(rpc_url, contract, "pendingRewards(address)(uint256)", addr))
    eth_bal = get_eth_balance(rpc_url, addr)
    return {
        "address": addr,
        "eth": eth_bal,
        "liquid_frac": bal_wei / 1e18,
        "staked_frac": staked_wei / 1e18,
        "pending_frac": pending_wei / 1e18,
    }


def print_wallet_status(rpc_url: str, contract: str, addr: str) -> dict:
    b = get_wallet_balances(rpc_url, contract, addr)
    print("\033[96m" + "=" * 68)
    print("  FRACTAL COIN (FRAC) — MINER WALLET & STAKING STATUS")
    print("=" * 68 + "\033[0m")
    print(f"  Miner Address    : {b['address']}")
    print(f"  Base ETH (Gas)   : {b['eth']:.6f} ETH")
    print(f"  Liquid FRAC      : {b['liquid_frac']:,.2f} FRAC (Ready to transfer/trade)")
    print(f"  Staked FRAC      : {b['staked_frac']:,.2f} FRAC (Earning 3.5% block yield)")
    print(f"  Pending Rewards  : {b['pending_frac']:,.4f} FRAC (Claimable dividends)")
    print("\033[96m" + "-" * 68 + "\033[0m\n")
    return b


def do_claim_rewards(rpc_url: str, contract: str, private_key: str) -> None:
    miner_addr = get_address_from_key(private_key)
    b = get_wallet_balances(rpc_url, contract, miner_addr)
    if b["pending_frac"] <= 0:
        print(f"  [!] No pending rewards to claim for {miner_addr}.")
        return
    print(f"  [+] Claiming {b['pending_frac']:,.4f} FRAC in rewards to {miner_addr}...")
    tx_hash = cast_send(rpc_url, private_key, contract, "claimRewards()")
    print(f"  [✓] Rewards claimed successfully! Tx: {tx_hash[:18]}...\n")
    print_wallet_status(rpc_url, contract, miner_addr)


def do_unstake(rpc_url: str, contract: str, private_key: str, amount_frac: float = 0.0) -> None:
    miner_addr = get_address_from_key(private_key)
    b = get_wallet_balances(rpc_url, contract, miner_addr)
    if b["staked_frac"] <= 0:
        print(f"  [!] No staked FRAC found for {miner_addr}.")
        return
    if amount_frac <= 0 or amount_frac >= b["staked_frac"]:
        target_amount = b["staked_frac"]
    else:
        target_amount = amount_frac

    amt_wei = str(int(target_amount * 1e18))
    print(f"  [+] Unstaking {target_amount:,.2f} FRAC back to liquid wallet {miner_addr}...")
    tx_hash = cast_send(rpc_url, private_key, contract, "unstake(uint256)", amt_wei)
    print(f"  [✓] Unstaked successfully! Tx: {tx_hash[:18]}...\n")
    print_wallet_status(rpc_url, contract, miner_addr)


def do_withdraw_to(rpc_url: str, contract: str, private_key: str, recipient: str, amount_frac: float = 0.0) -> None:
    miner_addr = get_address_from_key(private_key)
    if not recipient.startswith("0x") or len(recipient) != 42:
        print(f"  [!] Error: Invalid recipient address '{recipient}'. Must be 42-char 0x... address.")
        return
    b = get_wallet_balances(rpc_url, contract, miner_addr)
    if b["liquid_frac"] <= 0:
        print(f"  [!] Error: No liquid FRAC available in {miner_addr} to withdraw. (Unstake or claim rewards first).")
        return
    if amount_frac <= 0 or amount_frac >= b["liquid_frac"]:
        target_amount = b["liquid_frac"]
    else:
        target_amount = amount_frac

    amt_wei = str(int(target_amount * 1e18))
    print(f"  [+] Sending {target_amount:,.2f} FRAC from miner {miner_addr} -> {recipient}...")
    tx_hash = cast_send(rpc_url, private_key, contract, "transfer(address,uint256)", recipient, amt_wei)
    print(f"  [✓] Withdrawn successfully! Tx: {tx_hash[:18]}...\n")
    print_wallet_status(rpc_url, contract, miner_addr)


def do_stake(rpc_url: str, contract: str, private_key: str, amount_frac: float = 0.0) -> None:
    miner_addr = get_address_from_key(private_key)
    b = get_wallet_balances(rpc_url, contract, miner_addr)
    if b["liquid_frac"] <= 0:
        print(f"  [!] Error: No liquid FRAC available in {miner_addr} to stake.")
        return
    if amount_frac <= 0 or amount_frac >= b["liquid_frac"]:
        target_amount = b["liquid_frac"]
    else:
        target_amount = amount_frac

    amt_wei = str(int(target_amount * 1e18))
    print(f"  [+] Staking {target_amount:,.2f} FRAC from {miner_addr} into Loyalty Pool...")
    tx_hash = cast_send(rpc_url, private_key, contract, "stake(uint256)", amt_wei)
    print(f"  [✓] Staked successfully! Tx: {tx_hash[:18]}...\n")
    print_wallet_status(rpc_url, contract, miner_addr)


def interactive_menu(rpc_url: str, contract: str, private_key: str) -> None:
    miner_addr = get_address_from_key(private_key)
    while True:
        b = print_wallet_status(rpc_url, contract, miner_addr)
        print("  Select an action:")
        print("  \033[92m[1]\033[0m ⛏  Start 24/7 Mining (Auto-Stake to Loyalty Pool)")
        print("  \033[93m[2]\033[0m ⚡ Start 24/7 Mining (Direct Liquid Wallet Payout)")
        print("  \033[93m[3]\033[0m 💰 Claim Pending Staking Rewards to Wallet")
        print("  \033[92m[4]\033[0m 📥 Stake Liquid FRAC into Loyalty Pool (Custom Amount or ALL)")
        print("  \033[96m[5]\033[0m 🔓 Unstake FRAC from Loyalty Pool to Wallet (Custom Amount or ALL)")
        print("  \033[95m[6]\033[0m 🚀 Withdraw / Send Liquid FRAC to Another Wallet (MetaMask / Cold Storage)")
        print("  \033[94m[7]\033[0m 🔄 Refresh Balances")
        print("  \033[90m[0]\033[0m ❌ Exit")
        print("\033[96m" + "-" * 68 + "\033[0m")
        try:
            choice = input("  Enter choice [0-7]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if choice == "1":
            mine_loop(rpc_url, contract, private_key, max_epochs=0, auto_stake=True)
        elif choice == "2":
            mine_loop(rpc_url, contract, private_key, max_epochs=0, auto_stake=False)
        elif choice == "3":
            do_claim_rewards(rpc_url, contract, private_key)
            input("\nPress Enter to continue...")
        elif choice == "4":
            print(f"  Current liquid balance: {b['liquid_frac']:,.2f} FRAC")
            amt_in = input("  Enter amount of FRAC to stake [Press Enter for ALL]: ").strip().lower()
            amt_val = 0.0 if amt_in in ("", "all") else float(amt_in)
            do_stake(rpc_url, contract, private_key, amt_val)
            input("\nPress Enter to continue...")
        elif choice == "5":
            print(f"  Current staked balance: {b['staked_frac']:,.2f} FRAC")
            amt_in = input("  Enter amount of FRAC to unstake [Press Enter for ALL]: ").strip().lower()
            amt_val = 0.0 if amt_in in ("", "all") else float(amt_in)
            do_unstake(rpc_url, contract, private_key, amt_val)
            input("\nPress Enter to continue...")
        elif choice == "6":
            print(f"  Current liquid balance: {b['liquid_frac']:,.2f} FRAC")
            recipient = input("  Enter destination wallet address (0x...): ").strip()
            if recipient:
                amt_in = input("  Enter amount of FRAC to send [Press Enter for ALL]: ").strip().lower()
                amt_val = 0.0 if amt_in in ("", "all") else float(amt_in)
                do_withdraw_to(rpc_url, contract, private_key, recipient, amt_val)
            input("\nPress Enter to continue...")
        elif choice == "7":
            continue
        elif choice in ("0", "q", "quit", "exit"):
            print("Exiting.")
            break


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
                    golden_tag = " \033[93m*** FRACTAL GOLDEN BLOCK HIT! (JACKPOT WON LUCKY FUCKER!!!) ***\033[0m" if is_golden else ""
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
    parser = argparse.ArgumentParser(description="FractalPoWToken (FRAC) Old-PC CPU Miner & Wallet Manager (Base Mainnet)")
    parser.add_argument("--rpc-url", default="https://mainnet.base.org", help="Base Mainnet JSON-RPC URL")
    parser.add_argument(
        "--contract",
        default="0x8F92de279E8f942Cb4E37F3A207A221CB5566C04",
        help="Official FractalPoWToken (FRAC) contract address on Base Mainnet",
    )
    parser.add_argument("--private-key", default="", help="Miner wallet private key (or set FRAC_PRIVATE_KEY env var)")
    parser.add_argument("--epochs", type=int, default=-1, help="Number of epochs to mine (0 = infinite 24/7, -1 = interactive menu)")
    parser.add_argument("--throttle-ms", type=float, default=0.0, help="Sleep ms every 50 nonces to keep old CPUs cool")
    parser.add_argument("--auto-stake", action="store_true", help="Call mineAndStake() to auto-compound rewards")
    parser.add_argument("--status", action="store_true", help="Display miner wallet balances & rewards and exit")
    parser.add_argument("--claim-rewards", action="store_true", help="Claim all pending staking rewards to miner wallet")
    parser.add_argument("--stake", nargs="?", const="all", default=None, help="Stake liquid FRAC into loyalty pool (e.g. --stake 50 or --stake all)")
    parser.add_argument("--unstake", nargs="?", const="all", default=None, help="Unstake FRAC from loyalty pool (e.g. --unstake 50 or --unstake all)")
    parser.add_argument("--withdraw-to", default="", help="Destination wallet address to send liquid FRAC to (e.g. --withdraw-to 0x...)")
    parser.add_argument("--amount", default="all", help="Amount of FRAC to withdraw (default: all)")
    parser.add_argument("--menu", action="store_true", help="Launch interactive control menu")
    args = parser.parse_args()

    priv_key = args.private_key.strip() or os.environ.get("FRAC_PRIVATE_KEY", "").strip()
    if not priv_key:
        print("\033[92m=== FRAC STANDALONE OLD-PC CPU MINER & WALLET MANAGER ===\033[0m")
        priv_key = input("Enter your Miner Wallet Private Key (0x...): ").strip()
        if not priv_key:
            raise SystemExit("Error: A valid Base Mainnet wallet private key (with ~$0.05 ETH for gas) is required.")

    miner_addr = get_address_from_key(priv_key)

    if args.status:
        print_wallet_status(args.rpc_url, args.contract, miner_addr)
        sys.exit(0)

    if args.claim_rewards:
        do_claim_rewards(args.rpc_url, args.contract, priv_key)
        sys.exit(0)

    if args.stake is not None:
        amt_str = args.stake.strip().lower()
        amt_val = 0.0 if amt_str in ("", "all") else float(amt_str)
        do_stake(args.rpc_url, args.contract, priv_key, amt_val)
        sys.exit(0)

    if args.unstake is not None:
        amt_str = args.unstake.strip().lower()
        amt_val = 0.0 if amt_str in ("", "all") else float(amt_str)
        do_unstake(args.rpc_url, args.contract, priv_key, amt_val)
        sys.exit(0)

    if args.withdraw_to:
        amt_str = args.amount.strip().lower()
        amt_val = 0.0 if amt_str in ("", "all") else float(amt_str)
        do_withdraw_to(args.rpc_url, args.contract, priv_key, args.withdraw_to.strip(), amt_val)
        sys.exit(0)

    if args.menu or (args.epochs == -1 and not args.auto_stake):
        interactive_menu(args.rpc_url, args.contract, priv_key)
    else:
        epochs = max(args.epochs, 0)
        mine_loop(
            rpc_url=args.rpc_url,
            contract=args.contract,
            private_key=priv_key,
            max_epochs=epochs,
            throttle_ms=args.throttle_ms,
            auto_stake=args.auto_stake,
        )

