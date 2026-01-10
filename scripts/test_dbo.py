from poke_env.player.battle_order import DoubleBattleOrder, BattleOrder
# from poke_env.environment.move import Move

# Mock Move and Pokemon
class MockMove:
    def __init__(self, id):
        self.id = id

class MockPokemon:
    def __init__(self, species):
        self.species = species

move = MockMove("tackle")
pokemon = MockPokemon("pikachu")

order1 = BattleOrder(move)
order2 = BattleOrder(pokemon)

print("--- DoubleBattleOrder tests ---")
try:
    dbo = DoubleBattleOrder(order1, order2)
    print(f"Order(Move, Switch): {dbo!s}")
except Exception as e:
    print(f"Order(Move, Switch) failed: {e}")

try:
    dbo = DoubleBattleOrder(order2, None)
    print(f"Order(Switch, None): {dbo!s}")
except Exception as e:
    print(f"Order(Switch, None) failed: {e}")

try:
    dbo = DoubleBattleOrder(order2)
    print(f"Order(Switch): {dbo!s}") # Should require 2 args?
except Exception as e:
    print(f"Order(Switch) failed: {e}")

try:
    dbo = DoubleBattleOrder(order2, BattleOrder(None)) # forcing None?
    print(f"Order(Switch, BattleOrder(None)): {dbo!s}")
except Exception as e:
    print(f"Order(Switch, BattleOrder(None)) failed: {e}")
