"""Illicit operations (P0.3: ransomware core; P1.4 adds the full catalogue).

Ransomware script: victims pay fresh addresses → consolidation → a bot-regular peel chain whose peels land
at the operator's exchange deposit addresses → the remainder is cashed out at the exchange.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sutradhar_gen.agents import ExchangeState, deposit_address
from sutradhar_gen.config import RansomwareCfg
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
