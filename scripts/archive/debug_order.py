from poke_env.player.battle_order import BattleOrder, SingleBattleOrder, DoubleBattleOrder
from poke_env.player.player import Player
import inspect

# Check the message property
print("=== SingleBattleOrder.message property ===")
try:
    # Get the property getter
    prop = type.__getattribute__(SingleBattleOrder, 'message')
    if hasattr(prop, 'fget'):
        src = inspect.getsource(prop.fget)
        print(src)
    else:
        print(f"message is not a property: {prop}")
except Exception as e:
    print(f"Error: {e}")

# Also check if it's inherited
print("\n=== BattleOrder.message property ===")
try:
    prop = type.__getattribute__(BattleOrder, 'message')
    if hasattr(prop, 'fget'):
        src = inspect.getsource(prop.fget)
        print(src)
    else:
        print(f"message is not a property: {prop}")
except Exception as e:
    print(f"Error: {e}")
