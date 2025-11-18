#!/usr/bin/env node
/**
 * @smogon/calc Bridge Server
 *
 * StdinでJSON入力を受け取り、@smogon/calcでダメージ計算を行い、
 * StdoutにJSON結果を返すシンプルなブリッジサーバー
 */

import { Generations, Pokemon, Move, Field, calculate } from '@smogon/calc';
import * as readline from 'readline';

const gen = Generations.get(9); // Gen 9 (Scarlet/Violet)

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false,
});

console.error('[SmogonCalc Bridge] Ready. Waiting for input...');

rl.on('line', (line) => {
  try {
    const input = JSON.parse(line);

    // 入力形式:
    // {
    //   "attacker": {
    //     "name": "Gholdengo",
    //     "nature": "Modest",
    //     "evs": {"hp": 4, "spa": 252, "spe": 252},
    //     "ivs": {"hp": 31, "atk": 31, ...},
    //     "item": "Choice Specs",
    //     "ability": "Good as Gold",
    //     "level": 50,
    //     "teraType": null
    //   },
    //   "defender": {
    //     "name": "Dragonite",
    //     "nature": "Jolly",
    //     "evs": {"hp": 4, "atk": 252, "spe": 252},
    //     "ivs": {},
    //     "item": "Choice Band",
    //     "ability": "Multiscale",
    //     "level": 50,
    //     "teraType": null
    //   },
    //   "move": "Make It Rain",
    //   "field": {
    //     "weather": null,
    //     "terrain": null,
    //     "isCrit": false,
    //     "attackerSide": {"isReflect": false, "isLightScreen": false},
    //     "defenderSide": {"isReflect": false, "isLightScreen": false}
    //   }
    // }

    const result = performCalculation(input);
    console.log(JSON.stringify(result));
  } catch (error) {
    const errorResult = {
      success: false,
      error: error.message,
      stack: error.stack,
    };
    console.log(JSON.stringify(errorResult));
  }
});

function performCalculation(input) {
  const { attacker: atkData, defender: defData, move: moveName, field } = input;

  // Pokemonオブジェクトを構築
  const attacker = buildPokemon(atkData);
  const defender = buildPokemon(defData);

  // Moveオブジェクトを構築
  const move = new Move(gen, moveName);

  // Fieldオブジェクトを構築
  const fieldObj = buildField(field);

  // ダメージ計算実行
  const result = calculate(gen, attacker, defender, move, fieldObj);

  // 結果を整形
  return {
    success: true,
    damage: result.damage,
    damageRange: result.range(),
    description: result.fullDesc(),
    kochance: result.kochance(),
    minPercent: (Math.min(...result.damage) / defender.maxHP()) * 100,
    maxPercent: (Math.max(...result.damage) / defender.maxHP()) * 100,
    defender: {
      maxHP: defender.maxHP(),
    },
  };
}

function buildPokemon(data) {
  const { name, nature, evs, ivs, item, ability, level, teraType } = data;

  // EVs/IVsのデフォルト値
  const fullEVs = { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0, ...evs };
  const fullIVs = { hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31, ...ivs };

  const pokemon = new Pokemon(gen, name, {
    level: level || 50,
    nature: nature || 'Serious',
    evs: fullEVs,
    ivs: fullIVs,
    item: item || undefined,
    ability: ability || undefined,
    teraType: teraType || undefined,
  });

  return pokemon;
}

function buildField(fieldData) {
  if (!fieldData) {
    return new Field();
  }

  const field = new Field({
    weather: fieldData.weather || undefined,
    terrain: fieldData.terrain || undefined,
    isCrit: fieldData.isCrit || false,
    attackerSide: fieldData.attackerSide || {},
    defenderSide: fieldData.defenderSide || {},
  });

  return field;
}

process.on('SIGINT', () => {
  console.error('[SmogonCalc Bridge] Shutting down...');
  process.exit(0);
});
