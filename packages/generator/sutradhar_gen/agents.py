"""Benign agents: users and exchanges (P0.3 core; P1.2 adds merchants, pools, gambling, payroll)."""

from __future__ import annotations

from dataclasses import dataclass, field

from sutradhar_gen.economy import DUST_SATS, InsufficientFundsError, Wallet
from sutradhar_gen.world import US_PER_DAY, US_PER_H, Agent, World
from sutradhar_schemas.enums import ScriptType


@dataclass(slots=True)
class ExchangeState:
    agent: Agent
    hot: Wallet
    deposits: Wallet
    customer_deposit: dict[str, str] = field(default_factory=dict)  # customer agent_id -> deposit address
    withdrawal_queue: list[tuple[str, int, str]] = field(default_factory=list)  # (address, sats, customer)


def setup_exchanges(world: World) -> list[ExchangeState]:
    states = []
    for i in range(world.cfg.economy.exchanges):
        agent = world.add_agent(Agent(f"ex{chr(ord('a') + i)}", "exchange"))
        hot = world.new_wallet(agent, "hot", ScriptType.P2WPKH, reuse=0.0)
        deposits = world.new_wallet(agent, "deposits", ScriptType.P2WPKH, reuse=0.0)
        state = ExchangeState(agent, hot, deposits)
        agent.attrs["state"] = state
        for _ in range(4):  # the hot wallet starts with several coins, like a real exchange
            addr = world.ledger.new_address(hot, allow_reuse=False)
            share = world.btc(world.cfg.economy.exchange_start_btc / 4)
            world.ledger.coinbase(addr, share, world.t0, kind="genesis")
        states.append(state)
        _schedule_exchange(world, state)
    return states


def deposit_address(world: World, exchange: ExchangeState, customer_id: str) -> str:
    """Static per-customer deposit address (exchange-owned; the customer is recorded for ground truth)."""
    if customer_id not in exchange.customer_deposit:
        exchange.customer_deposit[customer_id] = world.ledger.new_address(
            exchange.deposits, allow_reuse=False
        )
    return exchange.customer_deposit[customer_id]


def _schedule_exchange(world: World, exchange: ExchangeState) -> None:
    econ = world.cfg.economy
    rng = world.rng["agents"]
    sweep_every = int(econ.sweep_every_h * US_PER_H)
    batch_every = int(econ.withdrawal_batch_every_h * US_PER_H)
    t = world.t0 + int(rng.uniform(0.2, 1.0) * sweep_every)
    while t < world.t_end:
        world.schedule(t, _sweep, world, exchange)
        t += sweep_every
    t = world.t0 + int(rng.uniform(0.2, 1.0) * batch_every)
    while t < world.t_end:
        world.schedule(t, _withdrawal_batch, world, exchange)
        t += batch_every


def _sweep(world: World, exchange: ExchangeState) -> None:
    utxos = [u for u in exchange.deposits.utxos.values() if u.created_us < world.now]
    if len(utxos) < 2:
        return
    to = world.ledger.new_address(exchange.hot, allow_reuse=False)
    world.ledger.sweep(
        utxos,
        to,
        world.now,
        world.feerate(world.now),
        kind="exchange_sweep",
        agent_id=exchange.agent.agent_id,
        wallet_id=exchange.deposits.wallet_id,
        origin_node=exchange.agent.node_id,
    )


def _withdrawal_batch(world: World, exchange: ExchangeState) -> None:
    if not exchange.withdrawal_queue:
        return
    queue, exchange.withdrawal_queue = exchange.withdrawal_queue, []
    payments = [(addr, sats) for addr, sats, _ in queue]
    try:
        world.ledger.pay(
            exchange.hot,
            payments,
            world.now,
            world.feerate(world.now),
            kind="exchange_withdrawal_batch",
            agent_id=exchange.agent.agent_id,
            origin_node=exchange.agent.node_id,
            customers=[c for _, _, c in queue],
        )
    except InsufficientFundsError:
        exchange.withdrawal_queue = queue  # retry at the next batch


def setup_users(world: World, exchanges: list[ExchangeState]) -> list[Agent]:
    econ = world.cfg.economy
    rng = world.rng["agents"]
    users = []
    for i in range(econ.users):
        agent = world.add_agent(Agent(f"u{i:05d}", "user"))
        wallet = world.new_wallet(agent, "main")
        agent.attrs["exchange"] = exchanges[i % len(exchanges)]
        start = world.btc(world.draw_range(rng, econ.user_start_btc, log=True))
        for part in (0.6, 0.4):  # two starting coins so users can make several payments
            world.ledger.coinbase(
                world.ledger.new_address(wallet),
                max(DUST_SATS * 4, int(start * part)),
                world.t0,
                kind="genesis",
            )
        users.append(agent)
        rate = econ.user_tx_per_day
        if rate > 0:
            t = world.t0 + int(rng.exponential(US_PER_DAY / rate))
            while t < world.t_end:
                world.schedule(t, _user_action, world, agent, users)
                t += int(rng.exponential(US_PER_DAY / rate))
    return users


def _user_action(world: World, agent: Agent, users: list[Agent]) -> None:
    if agent.attrs.get("frozen"):
        return
    rng = world.rng["agents"]
    wallet = world.ledger.wallets[agent.wallet_ids[0]]
    exchange: ExchangeState = agent.attrs["exchange"]
    balance = wallet.balance
    roll = rng.random()
    feerate = world.feerate(world.now)
    try:
        if roll < 0.15 or balance < 50_000:
            # Buy from the exchange: request a withdrawal to a fresh address of ours.
            amount = world.btc(float(rng.lognormal(-5.0, 1.0)))
            if amount > DUST_SATS * 10:
                exchange.withdrawal_queue.append((world.ledger.new_address(wallet), amount, agent.agent_id))
            return
        amount = int(balance * rng.uniform(0.02, 0.25))
        if amount <= DUST_SATS * 4:
            return
        if roll < 0.40:
            to = deposit_address(world, exchange, agent.agent_id)
            kind = "user_deposit"
        else:
            peer = users[int(rng.integers(len(users)))]
            if peer is agent:
                return
            to = world.ledger.new_address(world.ledger.wallets[peer.wallet_ids[0]])
            kind = "user_payment"
        world.ledger.pay(wallet, [(to, amount)], world.now, feerate, kind=kind, origin_node=agent.node_id)
    except InsufficientFundsError:
        return
