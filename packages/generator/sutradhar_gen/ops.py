"""Illicit operations (P0.3: ransomware core; P1.4 adds the full catalogue).

Ransomware script: victims pay fresh addresses → consolidation → a bot-regular peel chain whose peels land
at the operator's exchange deposit addresses → the remainder is cashed out at the exchange.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sutradhar_gen.agents import ExchangeState, deposit_address
from sutradhar_gen.config import CoinJoinCfg, DarknetCfg, RansomwareCfg
from sutradhar_gen.economy import DUST_SATS, InsufficientFundsError, Utxo
from sutradhar_gen.world import US_PER_DAY, US_PER_H, Agent, World
from sutradhar_schemas.enums import ScriptType

US_PER_MIN = 60_000_000


@dataclass(slots=True)
class RansomwareState:
    cfg: RansomwareCfg
    agent: Agent
    victims: list[Agent] = field(default_factory=list)
    ransom_utxos: list[Utxo] = field(default_factory=list)
    chain_utxo: Utxo | None = None
    hop: int = 0


def setup_ransomware(
    world: World, cfg: RansomwareCfg, users: list[Agent], exchanges: list[ExchangeState]
) -> RansomwareState:
    rng = world.rng["ops"]
    agent = world.add_agent(Agent(f"op:{cfg.op_id}", "ransomware", illicit=True, op_id=cfg.op_id))
    world.new_wallet(agent, "ransom", ScriptType.P2WPKH, reuse=0.0)
    world.new_wallet(agent, "chain", ScriptType.P2WPKH, reuse=0.0)
    state = RansomwareState(cfg, agent)
    agent.attrs["state"] = state
    agent.attrs["exchange"] = exchanges[0]
    order = rng.permutation(len(users))
    state.victims = [users[int(i)] for i in order[: cfg.victims]]
    pay_start = world.t0 + int(cfg.pay_day * US_PER_DAY)
    for victim in state.victims:
        victim.attrs["victim_of"] = cfg.op_id
        t = pay_start + int(rng.uniform(0, 12) * US_PER_H)
        world.schedule(t, _victim_pays, world, state, victim)
    consolidate_at = pay_start + int((12 + cfg.consolidate_after_h) * US_PER_H)
    world.schedule(consolidate_at, _consolidate, world, state)
    return state


def _victim_pays(world: World, state: RansomwareState, victim: Agent) -> None:
    rng = world.rng["ops"]
    wallet = world.ledger.wallets[victim.wallet_ids[0]]
    ransom = world.btc(world.draw_range(rng, state.cfg.ransom_btc))
    amount = min(ransom, int(wallet.balance * 0.8))
    if amount <= DUST_SATS * 10:
        return
    ransom_wallet = world.ledger.wallets[state.agent.wallet_ids[0]]
    address = world.ledger.new_address(ransom_wallet, allow_reuse=False)
    try:
        tx = world.ledger.pay(
            wallet,
            [(address, amount)],
            world.now,
            world.feerate(world.now),
            kind="ransom_payment",
            origin_node=victim.node_id,
            op_id=state.cfg.op_id,
            victim=victim.agent_id,
        )
    except InsufficientFundsError:
        return
    state.ransom_utxos.append(next(u for u in ransom_wallet.utxos.values() if u.txid == tx.txid))


def _consolidate(world: World, state: RansomwareState) -> None:
    ransom_wallet = world.ledger.wallets[state.agent.wallet_ids[0]]
    chain_wallet = world.ledger.wallets[state.agent.wallet_ids[1]]
    utxos = list(ransom_wallet.utxos.values())
    if not utxos:
        return
    to = world.ledger.new_address(chain_wallet, allow_reuse=False)
    tx = world.ledger.sweep(
        utxos,
        to,
        world.now,
        world.feerate(world.now),
        kind="consolidation",
        agent_id=state.agent.agent_id,
        wallet_id=ransom_wallet.wallet_id,
        origin_node=state.agent.node_id,
        op_id=state.cfg.op_id,
    )
    if tx is None:
        return
    state.chain_utxo = chain_wallet.utxos[(tx.txid, 0)]
    world.schedule(world.now + US_PER_H, _peel_hop, world, state)


def _peel_hop(world: World, state: RansomwareState) -> None:
    rng = world.rng["ops"]
    utxo = state.chain_utxo
    if utxo is None:
        return
    exchange: ExchangeState = state.agent.attrs["exchange"]
    chain_wallet = world.ledger.wallets[state.agent.wallet_ids[1]]
    feerate = world.feerate(world.now)
    if state.hop >= state.cfg.peel_hops:
        # Cash out what is left at the exchange.
        deposit = deposit_address(world, exchange, state.agent.agent_id)
        world.ledger.sweep(
            [utxo],
            deposit,
            world.now,
            feerate,
            kind="cashout",
            agent_id=state.agent.agent_id,
            wallet_id=chain_wallet.wallet_id,
            origin_node=state.agent.node_id,
            op_id=state.cfg.op_id,
        )
        state.chain_utxo = None
        return
    peel = int(utxo.sats * world.draw_range(rng, state.cfg.peel_fraction))
    deposit = deposit_address(world, exchange, f"{state.agent.agent_id}#{state.hop % 3}")
    try:
        tx = world.ledger.pay(
            chain_wallet,
            [(deposit, peel)],
            world.now,
            feerate,
            kind="peel_hop",
            origin_node=state.agent.node_id,
            op_id=state.cfg.op_id,
            inputs=[utxo],
            peel_chain_id=f"{state.cfg.op_id}:chain0",
            peel_hop=state.hop,
        )
    except (InsufficientFundsError, ValueError):
        state.chain_utxo = None
        return
    change = next((o for o in tx.outputs if o.is_change), None)
    state.hop += 1
    if change is None:
        state.chain_utxo = None
        return
    vout = tx.outputs.index(change)
    state.chain_utxo = chain_wallet.utxos[(tx.txid, vout)]
    interval = world.draw_range(rng, state.cfg.hop_interval_min)
    world.schedule(world.now + int(interval * US_PER_MIN), _peel_hop, world, state)


# ── CoinJoin coordinator (P1.3) ────────────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class CoinJoinState:
    cfg: CoinJoinCfg
    agent: Agent
    users: list[Agent]
    round: int = 0


def setup_coinjoin(world: World, cfg: CoinJoinCfg, users: list[Agent]) -> CoinJoinState:
    agent = world.add_agent(Agent(f"op:{cfg.op_id}", "coinjoin_coordinator", illicit=False, op_id=cfg.op_id))
    state = CoinJoinState(cfg, agent, users)
    world.schedule(world.t0 + int(cfg.first_round_day * US_PER_DAY), _coinjoin_round, world, state)
    return state


def _coinjoin_round(world: World, state: CoinJoinState) -> None:
    cfg, rng = state.cfg, world.rng["coinjoin"]
    denom = world.btc(cfg.denomination_btc)
    needed = int(denom * 1.15)
    pool = []
    for user in state.users:
        wallet = world.ledger.wallets[user.wallet_ids[0]]
        fits = sorted(
            (u for u in wallet.utxos.values() if u.sats >= needed), key=lambda u: (u.sats, u.txid, u.vout)
        )
        if fits:
            pool.append((wallet, fits[0]))
    k = int(rng.integers(cfg.participants_min, cfg.participants_max + 1))
    if len(pool) >= 3:
        chosen = [pool[int(i)] for i in rng.permutation(len(pool))[: min(k, len(pool))]]
        world.ledger.coinjoin(
            chosen,
            denom,
            world.now,
            world.feerate(world.now),
            kind="coinjoin",
            coordinator=state.agent.agent_id,
            origin_node=state.agent.node_id,
            op_id=cfg.op_id,
            coinjoin_round=state.round,
        )
    state.round += 1
    if state.round < cfg.rounds:
        world.schedule(world.now + int(cfg.interval_h * US_PER_H), _coinjoin_round, world, state)


# ── Darknet market (P1.4) ──────────────────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class DarknetState:
    cfg: DarknetCfg
    agent: Agent
    vendors: list[Agent] = field(default_factory=list)
    buyers: list[Agent] = field(default_factory=list)
    escrow_first: str | None = None


def setup_darknet(
    world: World, cfg: DarknetCfg, users: list[Agent], exchanges: list[ExchangeState]
) -> DarknetState:
    rng = world.rng["darknet"]
    market = world.add_agent(Agent(f"op:{cfg.op_id}", "darknet_market", illicit=True, op_id=cfg.op_id))
    world.new_wallet(market, "escrow", ScriptType.P2WPKH, reuse=0.0)
    world.new_wallet(market, "payout", ScriptType.P2WPKH, reuse=0.0)
    state = DarknetState(cfg, market)
    market.attrs["state"], market.attrs["exchange"] = state, exchanges[0]
    for i in range(cfg.vendors):
        vendor = world.add_agent(Agent(f"vendor:{cfg.op_id}:{i}", "vendor", illicit=True, op_id=cfg.op_id))
        world.new_wallet(vendor, "sales", ScriptType.P2WPKH, reuse=0.0)
        vendor.attrs["exchange"] = exchanges[0]
        state.vendors.append(vendor)
    order = rng.permutation(len(users))
    state.buyers = [users[int(i)] for i in order[: cfg.buyers]]
    start = world.t0 + int(cfg.start_day * US_PER_DAY)
    for buyer in state.buyers:
        world.schedule(start + int(rng.uniform(0, 10) * US_PER_H), _buyer_pays, world, state, buyer)
    world.schedule(start + int((10 + cfg.payout_after_h) * US_PER_H), _market_payout, world, state)
    return state


def _buyer_pays(world: World, state: DarknetState, buyer: Agent) -> None:
    rng = world.rng["darknet"]
    wallet = world.ledger.wallets[buyer.wallet_ids[0]]
    amount = min(world.btc(world.draw_range(rng, state.cfg.price_btc)), int(wallet.balance * 0.6))
    if amount <= DUST_SATS * 10:
        return
    escrow = world.ledger.wallets[state.agent.wallet_ids[0]]
    address = world.ledger.new_address(escrow, allow_reuse=False)
    try:
        world.ledger.pay(
            wallet,
            [(address, amount)],
            world.now,
            world.feerate(world.now),
            kind="market_payment",
            origin_node=buyer.node_id,
            op_id=state.cfg.op_id,
            buyer=buyer.agent_id,
        )
    except InsufficientFundsError:
        return
    if state.escrow_first is None:
        state.escrow_first = address


def _market_payout(world: World, state: DarknetState) -> None:
    """Consolidate escrow, then pay every vendor in one batched transaction; vendors cash out later."""
    escrow = world.ledger.wallets[state.agent.wallet_ids[0]]
    payout = world.ledger.wallets[state.agent.wallet_ids[1]]
    utxos = list(escrow.utxos.values())
    if not utxos:
        return
    to = world.ledger.new_address(payout, allow_reuse=False)
    swept = world.ledger.sweep(
        utxos,
        to,
        world.now,
        world.feerate(world.now),
        kind="market_consolidation",
        agent_id=state.agent.agent_id,
        wallet_id=escrow.wallet_id,
        origin_node=state.agent.node_id,
        op_id=state.cfg.op_id,
    )
    if swept is None:
        return
    share = int(payout.balance * 0.9) // len(state.vendors)
    if share <= DUST_SATS * 10:
        return
    payments = [
        (world.ledger.new_address(world.ledger.wallets[v.wallet_ids[0]], allow_reuse=False), share)
        for v in state.vendors
    ]
    try:
        world.ledger.pay(
            payout,
            payments,
            world.now + US_PER_MIN * 20,
            world.feerate(world.now),
            kind="market_payout",
            origin_node=state.agent.node_id,
            op_id=state.cfg.op_id,
        )
    except InsufficientFundsError:
        return
    for vendor in state.vendors:
        world.schedule(
            world.now + int(state.cfg.cashout_after_h * US_PER_H), _vendor_cashout, world, state, vendor
        )


def _vendor_cashout(world: World, state: DarknetState, vendor: Agent) -> None:
    wallet = world.ledger.wallets[vendor.wallet_ids[0]]
    utxos = list(wallet.utxos.values())
    if not utxos:
        return
    exchange: ExchangeState = vendor.attrs["exchange"]
    world.ledger.sweep(
        utxos,
        deposit_address(world, exchange, vendor.agent_id),
        world.now,
        world.feerate(world.now),
        kind="vendor_cashout",
        agent_id=vendor.agent_id,
        wallet_id=wallet.wallet_id,
        origin_node=vendor.node_id,
        op_id=state.cfg.op_id,
    )
