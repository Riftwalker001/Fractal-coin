# Fractal PoW Coin (FRAC)
## An Anti-ASIC, Old-PC Friendly Proof-of-Work Cryptocurrency with Embedded Real-Yield Staking and Golden Block Rollover Jackpot on Base Mainnet

**Version 1.0 — October 2026**  
**Protocol Repository:** [https://github.com/blackbirdpi/FractalPoWToken](https://basescan.org/token/0x8F92de279E8f942Cb4E37F3A207A221CB5566C04)  
**Smart Contract (Base Mainnet, Chain ID 8453):** [`0x8F92de279E8f942Cb4E37F3A207A221CB5566C04`](https://basescan.org/token/0x8F92de279E8f942Cb4E37F3A207A221CB5566C04)  
**Decentralized Verification:** [Sourcify Verified (Match ID: 56651837)](https://sourcify.dev/#/lookup/0x8F92de279E8f942Cb4E37F3A207A221CB5566C04)

---

## Abstract

Fractal PoW Coin (`FRAC`) is an immutable, mathematically capped (21,000,000 max supply) Proof-of-Work (PoW) cryptocurrency engineered natively on Base Mainnet (Ethereum Layer 2). `FRAC` revives Satoshi Nakamoto’s original *"one CPU, one vote"* egalitarian mining ethos by implementing a 64-step sequential Keccak-256 sponge hash chain coupled with a deterministic 5-minute per-address anti-monopoly cooldown. This computational architecture neutralizes massive parallelization advantages traditionally exploited by high-end GPUs and ASIC warehouses, allowing commodity CPUs, older laptops, and single-board computers (such as Raspberry Pis) to participate in fair mining on an equal footing. 

Simultaneously, `FRAC` resolves the historical divergence between miners and holders by embedding a non-custodial **3.5% Real-Yield Staking Loyalty Pool** directly into the block issuance logic, providing continuous, liquid yield on every block solved globally with zero lockup penalty. Furthermore, each block undergoes a Bernoulli trial with a $1/64$ ($1.5625\%$) probability of triggering a **Fractal Golden Block**, disbursing $80\%$ of an on-chain jackpot pot (seeded with over 10,000 `FRAC`) with a $20\%$ permanent rollover floor. With 0% transfer taxes, pure OpenZeppelin ERC-20 transfer mechanics, and complete immutability, `FRAC` establishes a secure, transparent, and accessible proof-of-work standard for the Layer-2 decentralized economy.

---

## 1. Introduction & Background

### 1.1 The Centralization Dilemma of Modern Proof-of-Work
Proof-of-Work remains the most robust and time-tested mechanism for achieving decentralized consensus and permissionless distribution. However, modern Proof-of-Work networks (such as Bitcoin) have suffered severe industrial centralization. The emergence of Application-Specific Integrated Circuits (ASICs) and multi-gigawatt industrial mining facilities has effectively disenfranchised individual miners operating commodity hardware.

Attempts to counter this dynamic via memory-hard algorithms (e.g., Ethash, RandomX) have faced limitations when deployed on high-cost Layer 1 blockchains, where gas fees make smart-contract verification computationally prohibitive.

### 1.2 The Layer-2 Landscape & The Pitfall of Insider Tokens
The emergence of Ethereum Layer 2 rollups (specifically Base) has reduced transaction settlement fees to fractions of a cent while inheriting Ethereum’s Layer 1 security guarantees. Despite this infrastructure, the token ecosystem on Base is dominated by two primary classes:
1. **Insider/Venture Tokens:** Featuring large pre-mines, multi-year investor vestings, and centralized governance override vectors.
2. **Meme Tokens:** Characterized by unbacked liquidity, hidden transfer fees ("taxes"), honeypot code, and predatory developer dumping.

### 1.3 The Fractal PoW Proposition
`FRAC` is deployed to unite the security and fair-launch heritage of Bitcoin with the composability and low transaction costs of Base Layer 2. By executing Proof-of-Work verification directly inside the Ethereum Virtual Machine (EVM), `FRAC` operates permissionlessly without requiring off-chain validators or specialized bridges.

```
+-------------------------------------------------------------------------+
|                        FRACTAL POW ARCHITECTURE                         |
+-------------------------------------------------------------------------+
|                                                                         |
|   +-------------------+        Solves Sequential-64       +-----------+ |
|   |  Commodity CPU    | --------------------------------> | Winning   | |
|   |  (Old PC / Pi)    |   Keccak-256 Math Puzzle          | Nonce     | |
|   +-------------------+                                   +-----------+ |
|             |                                                   |       |
|             | Submits Transaction (~$0.001 Gas)                 |       |
|             v                                                   v       |
|   +-------------------------------------------------------------------+ |
|   |            FractalPoWToken Smart Contract (Base L2)               | |
|   |             0x8F92de279E8f942Cb4E37F3A207A221CB5566C04            | |
|   +-------------------------------------------------------------------+ |
|         |                     |                    |             |      |
|         v                     v                    v             v      |
|     93.0% Miner           3.5% Stakers         1.5% Jackpot   2.0% Dev  |
|     (46.50 FRAC)          (1.75 FRAC)          (0.75 FRAC)    (1.00 FRAC|
+-------------------------------------------------------------------------+
```

---

## 2. The Cryptographic Proof-of-Work Engine

### 2.1 Sequential-64 Sponge Chaining (Anti-ASIC / Anti-GPU)
Traditional Proof-of-Work functions compute a single hash per nonce:
$$\text{Hash} = \text{SHA256}(\text{SHA256}(\text{BlockHeader} \mathbin{\Vert} \text{Nonce}))$$
Because each nonce trial is independent, massive parallel hardware (thousands of GPU cores or dedicated ASIC circuits) achieves an overwhelming linear scaling advantage over single-threaded CPUs.

To neutralize this advantage, `FRAC` mandates a **64-step sequential sponge chain**. Each nonce trial requires 64 sequential invocations of Keccak-256, where step $i$ strictly depends on the output of step $i-1$:

$$\text{Digest}_0 = \text{Keccak-256}(\text{Challenge} \mathbin{\Vert} \text{MinerAddress}_{20} \mathbin{\Vert} \text{Nonce}_{32})$$

$$\text{Digest}_i = \text{Keccak-256}(\text{Digest}_{i-1} \mathbin{\Vert} \text{Challenge} \mathbin{\Vert} \text{StepIndex}_{32}) \quad \forall \; i \in [1, 63]$$

$$\text{FinalDigest} = \text{Digest}_{63}$$

#### Architectural Implications:
1. **Instruction-Level Serialization:** A core cannot begin computation of step $i$ until step $i-1$ is complete. High-frequency CPU cores execute sequential instruction pipelines with extremely low latency, whereas massively parallel GPU architectures are bottlenecked by thread context switching and memory latency.
2. **Miner-Specific Challenge Binding:** By binding `MinerAddress` directly into the seed $\text{Digest}_0$, nonces cannot be intercepted, front-run, or stolen by MEV (Maximal Extractable Value) searchers in the public mempool.

### 2.2 Proof-of-Work Verification Condition
A nonce is valid if and only if the numerical interpretation of the final digest satisfies the current network target:

$$\text{uint256}(\text{FinalDigest}) \le \text{EffectiveTarget}$$

```solidity
function _computeFractalHash(
    bytes32 challenge,
    address miner,
    uint256 nonce
) internal pure returns (bytes32 digest) {
    digest = keccak256(abi.encodePacked(challenge, miner, nonce));
    for (uint256 i = 1; i < SEQUENTIAL_STEPS; i++) {
        digest = keccak256(abi.encodePacked(digest, challenge, i));
    }
}
```

### 2.3 The 5-Minute Anti-Monopoly Fairness Cooldown
To prevent high-performance nodes from sweeping consecutive epochs, `FRAC` enforces an on-chain cooldown interval of 300 seconds (5 minutes) for consecutive block solves by the same mining address:

$$\text{block.timestamp} \ge \text{lastEpochTime} + \text{TARGET\_EPOCH\_TIME} \quad \text{if } \text{msg.sender} == \text{lastMiner}$$

This ensures that once a miner successfully mines a block, they are locked out from claiming the immediate subsequent block for 5 minutes. This creates a dedicated window of opportunity for slower nodes (such as low-power home PCs, Raspberry Pis, or laptops) to find and submit valid solutions without being outpaced by high-clock-rate systems.

### 2.4 Dynamic Difficulty Retargeting & Emergency Decay
- **Nominal Target Epoch Time:** 300 seconds (5 minutes per block).
- **Adjustment Cadence:** Retargeting occurs every $N = 16$ epochs.
- **Bounding Ratio:** Retarget adjustments are clamped within a factor of $[0.5 \times, 2.0 \times]$ to avoid abrupt volatility in mining difficulty:

$$\text{NewTarget} = \text{OldTarget} \times \frac{\text{ActualTimeElapsed}}{\text{ExpectedTimeElapsed}}$$

- **Emergency Linear Decay:** To guarantee that the protocol can never permanently freeze if network hashrate drops drastically, the contract computes an `effectiveTarget()`: if the elapsed time since the last epoch exceeds $2 \times \text{TARGET\_EPOCH\_TIME}$ (10 minutes), the target begins expanding automatically every second:

$$\text{EffectiveTarget} = \text{Target} + \left( \text{Target} \times \frac{\text{Elapsed} - 2 \times \text{Window}}{4 \times \text{Window}} \right)$$

---

## 3. Macroeconomic Architecture & Tokenomics

### 3.1 Hard Supply Cap & Halving Schedule
In alignment with classic sound-money principles, `FRAC` enforces a strict mathematical maximum supply:
$$\text{Max Supply} = 21,000,000 \text{ FRAC}$$

Token distribution is partitioned into discrete **Eras** of 210,000 epochs each:

| Era | Epoch Range | Block Reward | Total FRAC Minted in Era | Cumulative Supply |
|:---:|:---:|:---:|:---:|:---:|
| **Era 1** | 0 – 209,999 | 50.00 FRAC | 10,500,000 FRAC | 11,500,000 FRAC |
| **Era 2** | 210,000 – 419,999 | 25.00 FRAC | 5,250,000 FRAC | 16,750,000 FRAC |
| **Era 3** | 420,000 – 629,999 | 12.50 FRAC | 2,625,000 FRAC | 19,375,000 FRAC |
| **Era 4** | 630,000 – 839,999 | 6.25 FRAC | 1,312,500 FRAC | 20,687,500 FRAC |
| ... | ... | ... | ... | **21,000,000 FRAC** |

### 3.2 Genesis Allocation vs. Mineable Reserve
- **Genesis Allocation:** 1,000,000 `FRAC` ($4.76\%$ of total supply) minted at deployment.
  - **90,000 FRAC** deposited into the Uniswap V2 `FRAC/WETH` liquidity pool paired with ETH.
  - **10,000 FRAC** permanently locked to seed the Golden Block Jackpot Pot.
  - Remaining genesis balance held in the Dev Treasury for ecosystem growth, exchange listings, and infrastructure hosting.
- **Pure Proof-of-Work Mining Reserve:** 20,000,000 `FRAC` ($95.24\%$ of total supply) can only be minted via verified computational work.

### 3.3 Epoch Reward Allocation (Era 1 Breakdown)
Each mined block of 50.00 `FRAC` is divided across four economic channels:

$$\begin{aligned}
\text{Miner Direct Payout} &= 93.00\% \quad (46.50 \text{ FRAC}) \\
\text{Staking Loyalty Pool} &= 3.50\% \quad (1.75 \text{ FRAC}) \\
\text{Golden Jackpot Pot} &= 1.50\% \quad (0.75 \text{ FRAC}) \\
\text{Protocol Dev Treasury} &= 2.00\% \quad (1.00 \text{ FRAC})
\end{aligned}$$

```
+-----------------------------------------------------------------+
|               ERA 1 BLOCK REWARD: 50.00 FRAC                    |
+-----------------------------------------------------------------+
| [=======================================================] 93.0% | Miner (46.50)
| [==] 3.5%                                                       | Stakers (1.75)
| [=] 1.5%                                                        | Jackpot (0.75)
| [=] 2.0%                                                        | Dev (1.00)
+-----------------------------------------------------------------+
```

---

## 4. The 1-in-64 Golden Block & 80/20 Rollover Jackpot

### 4.1 Game-Theoretic Incentive
Pure Proof-of-Work systems with constant rewards often struggle with hashrate churn when market prices fluctuate. To introduce gamified upside for small miners, `FRAC` incorporates an on-chain lottery mechanism embedded directly in the hash verification logic.

### 4.2 Bernoulli Verification Trial
When verifying the 64th step digest, the contract inspects the least significant 6 bits:
$$\text{IsGolden} = (\text{uint8}(\text{FinalDigest}[31]) \ \& \ \texttt{0x3F}) == \texttt{0x3F}$$

Because each bit in Keccak-256 has uniform entropy:
$$P(\text{Golden Block}) = \left(\frac{1}{2}\right)^6 = \frac{1}{64} \approx 0.015625 \quad (1.5625\%)$$

On average, one out of every 64 mined blocks satisfies this condition.

### 4.3 80/20 Rollover Distribution Mechanics
When a Golden Block is triggered:
1. **Winner Disbursement:** The winning miner receives **80% of the entire accumulated jackpot pot** in addition to their standard 46.50 `FRAC` block reward.
2. **Rollover Floor:** The remaining **20% remains in the pot**, ensuring that the jackpot never resets to zero and maintaining high incentive for the subsequent epoch.

$$\text{JackpotPayout} = \text{jackpotPot} \times 80\%$$
$$\text{NewJackpotPot} = \text{jackpotPot} - \text{JackpotPayout} + \text{EpochJackpotContribution}$$

*(The jackpot was seeded at inception with 10,001.50 `FRAC`, providing immediate high-yield potential from Day 1).*

---

## 5. Non-Custodial Real-Yield Staking Pool

### 5.1 Aligning Speculators and Infrastructure Providers
In traditional PoW systems, non-mining token holders suffer continuous dilution from miner sell pressure. In `FRAC`, token holders participate directly in block production rewards without running computational hardware.

### 5.2 Algorithmic $O(1)$ Reward Distribution
The contract implements a gas-efficient $O(1)$ reward distribution accumulator (inspired by Synthetix staking models) that updates on every block solve:

$$\Delta \text{AccReward} = \frac{\text{BlockStakingFee} \times 10^{18}}{\text{TotalStaked}}$$

$$\text{RewardPerTokenStored} = \text{RewardPerTokenStored} + \Delta \text{AccReward}$$

When an individual user stakes $S_{\text{user}}$, their earned dividends accumulate continuously:

$$\text{Earned} = \left( S_{\text{user}} \times (\text{RewardPerTokenStored} - \text{UserRewardPerTokenPaid}) \right) + \text{UnclaimedRewards}$$

### 5.3 Zero-Lockup Liquidity
- Tokens deposited into the Loyalty Pool are **never locked**.
- Users can invoke `stake(uint256)`, `unstake(uint256)`, or `claimRewards()` at any second without penalties or cooldown delays.
- Miners can utilize the convenience function `mineAndStake(uint256)` to automatically route their 46.50 `FRAC` mining reward directly into the staking pool in a single atomic transaction, saving gas and compounding yield instantly.

---

## 6. Smart Contract Architecture & Security Model

### 6.1 Scanner-Clean ERC-20 Foundation
To guarantee zero false positives across major institutional wallet scanners (MetaMask, Blockaid, Coinbase Wallet, GoPlus), `FractalPoWToken.sol` strictly preserves standard OpenZeppelin ERC-20 transfer invariants:
- **0% Buy Tax / 0% Sell Tax:** Transfers invoke unmodified OpenZeppelin `_update` logic.
- **Zero Blacklists:** No ability for the deployer to freeze, blacklist, or seize user balances.
- **Zero Hidden Honeypot Logic:** Transfers are unconditional.

### 6.2 Immutable Dev Wallet Designation
The developer treasury address is defined as an `immutable` state variable established at construction time:
```solidity
address public immutable devWallet;
```
It cannot be altered, transferred, or redirected after deployment, preventing administrative key compromise risks.

### 6.3 Open-Source Decentralized Verification
The complete contract bytecode is permanently matched and verified on **Sourcify** (Decentralized Ethereum Foundation tooling) under Match ID `56651837`. Any client can independently recompile the Solidity source code (`0.8.24` + EVM Cancun) to verify byte-for-byte fidelity.

---

## 7. Comparative Technical Specifications

| Feature | Bitcoin (`BTC`) | Traditional ERC-20 | Fractal PoW (`FRAC`) |
|:---|:---:|:---:|:---:|
| **Consensus / Issuance** | SHA-256d PoW | 100% Pre-mine | Sequential-64 Keccak-256 PoW |
| **Max Supply Cap** | 21,000,000 | Variable / Uncapped | 21,000,000 |
| **Halving Schedule** | Every 210,000 Blocks | None | Every 210,000 Epochs |
| **Hardware Accessibility** | ASIC Only ($10,000+) | N/A | Older PCs, Laptops, Raspberry Pi |
| **Anti-Monopoly Protection**| None (Mining Pools) | N/A | 5-Minute Address Cooldown |
| **Passive Staking Yield** | 0% | Inflationary Minting | 3.5% Real-Yield from Mined Blocks |
| **Jackpot Rollover Pot** | None | None | 1-in-64 Golden Block (80/20) |
| **Settlement Speed** | ~10 – 60 Minutes | ~2 Seconds | ~2 Seconds (Base L2) |
| **Transaction Fee** | $1.00 – $50.00+ | $0.001 – $0.05 | < $0.001 (Base L2) |
| **Transfer Taxes** | 0% | Often 5% – 10% (Taxes) | **0% (Pure OpenZeppelin)** |

---

## 8. Network References & Official Deployments

- **Underlying Blockchain:** Base Mainnet (Chain ID `8453`)
- **Official Contract Address:** [`0x8F92de279E8f942Cb4E37F3A207A221CB5566C04`](https://basescan.org/token/0x8F92de279E8f942Cb4E37F3A207A221CB5566C04)
- **Uniswap V2 Liquidity Pool:** [`0x7EEc5ad1D6ca2CE83B6BD8C774737726245C3F87`](https://basescan.org/address/0x7EEc5ad1D6ca2CE83B6BD8C774737726245C3F87)
- **DexScreener Market Analytics:** [https://dexscreener.com/base/0x7EEc5ad1D6ca2CE83B6BD8C774737726245C3F87](https://dexscreener.com/base/0x7EEc5ad1D6ca2CE83B6BD8C774737726245C3F87)
- **Sourcify Verification Certificate:** [Lookup Contract `0x8F92de279E8f942Cb4E37F3A207A221CB5566C04`](https://sourcify.dev/#/lookup/0x8F92de279E8f942Cb4E37F3A207A221CB5566C04)
- **Standalone CPU Miner:** [`frac_miner.py`](file:///home/blackbirdpi/Desktop/Claude's%20Stuff/LearnToken/miner.py) (Zero external dependencies; compatible with Linux, macOS, Windows, and ARM/Raspberry Pi).

---

## 9. Conclusion

Fractal PoW Coin (`FRAC`) proves that the principles of decentralized, permissionless Proof-of-Work can thrive within the high-throughput, low-fee ecosystem of modern Ethereum Layer 2 rollups. By combining sequential sponge chaining, strict anti-monopoly cooldown intervals, algorithmic real-yield staking, and on-chain gamification, `FRAC` establishes a sustainable and fair macroeconomic model accessible to anyone with a computer.

---
*© 2026 Fractal PoW Contributors. Released under the MIT Open Source License.*
