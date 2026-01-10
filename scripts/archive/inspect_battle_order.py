from poke_env.player.battle_order import BattleOrder, SingleBattleOrder
import inspect

try:
    print("SingleBattleOrder MRO:", SingleBattleOrder.mro())
    print("SingleBattleOrder init sig:", inspect.signature(SingleBattleOrder.__init__))
except Exception as e:
    print("SingleBattleOrder check failed:", e)
