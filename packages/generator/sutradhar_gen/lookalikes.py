"""Legitimate look-alikes: actors whose shapes resemble illicit behaviour, so detectors and the ranker are tested on
hard negatives instead of an economy where only criminals do anything unusual.

merchant  many small incoming sales, periodic sweeps of the till (consolidation), supplier payouts (small fan-out)
payroll   one employer pays many employees in a single batched transaction (a big fan-out)
trader    a bot that pays out small amounts every half hour or so from one big coin: consecutive 1-in/2-out
          transactions with a large remainder, the same shape as a peeling chain
pool      periodic block-reward deposits (coinbase-like inflow), then a batched payout to many miners —
          proportional to hashrate, so amounts vary; a fan-out that repeats on a fixed cadence forever
gambling  a stream of small deposits (bets) from many users, and a stream of payouts to winners; always-on,
          both directions dense, unlike a merchant's daytime-only sales pattern
"""

from __future__ import annotations

import numpy as np

from sutradhar_gen.config import LookalikeCfg
from sutradhar_gen.economy import DUST_SATS, InsufficientFundsError
from sutradhar_gen.world import US_PER_DAY, US_PER_H, Agent, World

US_PER_MIN = 60_000_000


def setup_lookalikes(world: World, cfg: LookalikeCfg, users: list[Agent]) -> None:
    rng = world.rng["lookalike"]
    for i in range(cfg.merchants):
        m = world.add_agent(Agent(f"merchant{i:03d}", "merchant"))
        till = world.new_wallet(m, "till")
        world.ledger.coinbase(world.ledger.new_address(till), world.btc(2.5), world.t0, kind="genesis")
        t = world.t0 + int(rng.exponential(US_PER_DAY / cfg.merchant_sales_per_day))
        while t < world.t_end:
            world.schedule(t, _sale, world, m, users)
            t += int(rng.exponential(US_PER_DAY / cfg.merchant_sales_per_day))
        t = world.t0 + int(rng.uniform(0.3, 1.0) * cfg.merchant_sweep_every_h * US_PER_H)
        while t < world.t_end:
            world.schedule(t, _sweep_till, world, m)
            t += int(cfg.merchant_sweep_every_h * US_PER_H)
        t = world.t0 + int(rng.uniform(0.5, 1.0) * US_PER_DAY)
        while t < world.t_end:
            world.schedule(t, _supplier_payout, world, m, users)
            t += US_PER_DAY
    for i in range(cfg.payroll_employers):
        e = world.add_agent(Agent(f"employer{i:03d}", "payroll"))
        wallet = world.new_wallet(e, "payroll")
        world.ledger.coinbase(world.ledger.new_address(wallet), world.btc(25.0), world.t0, kind="genesis")
        order = rng.permutation(len(users))
        staff = [users[int(j)] for j in order[: cfg.payroll_employees]]
        t = world.t0 + int(rng.uniform(0.3, 1.0) * cfg.payroll_every_h * US_PER_H)
        while t < world.t_end:
            world.schedule(t, _payroll, world, e, staff)
            t += int(cfg.payroll_every_h * US_PER_H)
    for i in range(cfg.traders):
        b = world.add_agent(Agent(f"trader{i:03d}", "trader"))
        wallet = world.new_wallet(b, "bot")
        world.ledger.coinbase(world.ledger.new_address(wallet), world.btc(6.0), world.t0, kind="genesis")
        t = world.t0 + int(rng.uniform(0.2, 1.5) * US_PER_DAY)
        while t < world.t_end:
            world.schedule(t, _trade, world, b, users)
            t += int(world.draw_range(rng, cfg.trader_interval_min) * US_PER_MIN)
    for i in range(cfg.pools):
        p = world.add_agent(Agent(f"pool{i:03d}", "pool"))
        wallet = world.new_wallet(p, "pool")
        order = rng.permutation(len(users))
        miners = [users[int(j)] for j in order[: cfg.pool_miners]]
        t = world.t0 + int(rng.uniform(0.1, 1.0) * cfg.pool_block_every_h * US_PER_H)
        while t < world.t_end:
            world.schedule(t, _pool_block, world, p)
            t += int(cfg.pool_block_every_h * US_PER_H)
        t = world.t0 + int(rng.uniform(0.5, 1.0) * cfg.pool_payout_every_h * US_PER_H)
        while t < world.t_end:
            world.schedule(t, _pool_payout, world, p, miners)
            t += int(cfg.pool_payout_every_h * US_PER_H)
    for i in range(cfg.gambling_sites):
        g = world.add_agent(Agent(f"gambling{i:03d}", "gambling"))
        bank = world.new_wallet(g, "bank")
        world.ledger.coinbase(world.ledger.new_address(bank), world.btc(8.0), world.t0, kind="genesis")
        t = world.t0 + int(rng.exponential(US_PER_DAY / cfg.gambling_bets_per_day))
        while t < world.t_end:
            world.schedule(t, _bet, world, g, users, cfg.gambling_house_edge)
            t += int(rng.exponential(US_PER_DAY / cfg.gambling_bets_per_day))


def _sale(world: World, merchant: Agent, users: list[Agent]) -> None:
    rng = world.rng["lookalike"]
    customer = users[int(rng.integers(len(users)))]
    wallet = world.ledger.wallets[customer.wallet_ids[0]]
    amount = min(world.btc(float(rng.lognormal(-5.2, 0.7))), int(wallet.balance * 0.2))
    if amount <= DUST_SATS * 10:
        return
    till = world.ledger.wallets[merchant.wallet_ids[0]]
    try:
        world.ledger.pay(
            wallet,
            [(world.ledger.new_address(till, allow_reuse=False), amount)],
            world.now,
            world.feerate(world.now),
            kind="merchant_sale",
            origin_node=customer.node_id,
        )
    except InsufficientFundsError:
        return


def _sweep_till(world: World, merchant: Agent) -> None:
    till = world.ledger.wallets[merchant.wallet_ids[0]]
    utxos = [u for u in till.utxos.values() if u.created_us < world.now]
    if len(utxos) < 4:
        return
    world.ledger.sweep(
        utxos,
        world.ledger.new_address(till, allow_reuse=False),
        world.now,
        world.feerate(world.now),
        kind="merchant_sweep",
        agent_id=merchant.agent_id,
        wallet_id=till.wallet_id,
        origin_node=merchant.node_id,
    )


def _supplier_payout(world: World, merchant: Agent, users: list[Agent]) -> None:
    rng = world.rng["lookalike"]
    till = world.ledger.wallets[merchant.wallet_ids[0]]
    pay = []
    for j in rng.permutation(len(users))[:3]:
        target = world.ledger.wallets[users[int(j)].wallet_ids[0]]
        pay.append((world.ledger.new_address(target), world.btc(float(rng.uniform(0.02, 0.09)))))
    try:
        world.ledger.pay(
            till,
            pay,
            world.now,
            world.feerate(world.now),
            kind="merchant_payout",
            origin_node=merchant.node_id,
        )
    except InsufficientFundsError:
        return


def _payroll(world: World, employer: Agent, staff: list[Agent]) -> None:
    rng = world.rng["lookalike"]
    wallet = world.ledger.wallets[employer.wallet_ids[0]]
    pay = [
        (
            world.ledger.new_address(world.ledger.wallets[s.wallet_ids[0]]),
            world.btc(float(rng.uniform(0.015, 0.05))),
        )
        for s in staff
    ]
    try:
        world.ledger.pay(
            wallet, pay, world.now, world.feerate(world.now), kind="payroll", origin_node=employer.node_id
        )
    except InsufficientFundsError:
        return


def _trade(world: World, bot: Agent, users: list[Agent]) -> None:
    rng = world.rng["lookalike"]
    wallet = world.ledger.wallets[bot.wallet_ids[0]]
    peer = users[int(rng.integers(len(users)))]
    target = world.ledger.wallets[peer.wallet_ids[0]]
    amount = world.btc(float(rng.uniform(0.01, 0.06)))
    try:
        world.ledger.pay(
            wallet,
            [(world.ledger.new_address(target), amount)],
            world.now,
            world.feerate(world.now),
            kind="trader_payment",
            origin_node=bot.node_id,
        )
    except InsufficientFundsError:
        return


def _pool_block(world: World, pool: Agent) -> None:
    """A mined block's reward lands in the pool's wallet — a coinbase-shaped inflow, no sender."""
    wallet = world.ledger.wallets[pool.wallet_ids[0]]
    world.ledger.coinbase(
        world.ledger.new_address(wallet, allow_reuse=False), world.btc(6.25), world.now, kind="pool_block"
    )


def _pool_payout(world: World, pool: Agent, miners: list[Agent]) -> None:
    """Proportional payout to every miner on this round, a wide fan-out that repeats on a fixed cadence."""
    rng = world.rng["lookalike"]
    wallet = world.ledger.wallets[pool.wallet_ids[0]]
    weights = rng.dirichlet(np.ones(len(miners)))
    available = int(wallet.balance * 0.85)
    if available <= DUST_SATS * len(miners):
        return
    pay = [
        (world.ledger.new_address(world.ledger.wallets[m.wallet_ids[0]]), int(available * w))
        for m, w in zip(miners, weights, strict=True)
    ]
    pay = [(addr, amt) for addr, amt in pay if amt > DUST_SATS]
    if not pay:
        return
    try:
        world.ledger.pay(
            wallet, pay, world.now, world.feerate(world.now), kind="pool_payout", origin_node=pool.node_id
        )
    except InsufficientFundsError:
        return


def _bet(world: World, site: Agent, users: list[Agent], house_edge: float) -> None:
    """A deposit (the bet) followed, most of the time, by a payout to the same or a different winner —
    both directions run continuously, unlike a merchant's daytime sales."""
    rng = world.rng["lookalike"]
    bettor = users[int(rng.integers(len(users)))]
    wallet = world.ledger.wallets[bettor.wallet_ids[0]]
    stake = min(world.btc(float(rng.lognormal(-6.0, 0.8))), int(wallet.balance * 0.15))
    if stake <= DUST_SATS * 10:
        return
    bank = world.ledger.wallets[site.wallet_ids[0]]
    try:
        world.ledger.pay(
            wallet,
            [(world.ledger.new_address(bank, allow_reuse=False), stake)],
            world.now,
            world.feerate(world.now),
            kind="gambling_bet",
            origin_node=bettor.node_id,
        )
    except InsufficientFundsError:
        return
    if rng.random() < (1 - house_edge) * 0.5:
        winner = users[int(rng.integers(len(users)))]
        target = world.ledger.wallets[winner.wallet_ids[0]]
        payout = int(stake * rng.uniform(1.5, 3.0))
        payout = min(payout, int(bank.balance * 0.3))
        if payout <= DUST_SATS:
            return
        try:
            world.ledger.pay(
                bank,
                [(world.ledger.new_address(target), payout)],
                world.now,
                world.feerate(world.now),
                kind="gambling_payout",
                origin_node=site.node_id,
            )
        except InsufficientFundsError:
            return
