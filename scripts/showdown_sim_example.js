/**
 * Pokemon Showdown のシミュレータを直接使用するサンプルスクリプト
 *
 * 使い方:
 *   cd pokemon-showdown
 *   node ../scripts/showdown_sim_example.js
 */

'use strict';

// Showdownのシミュレータをロード
const Sim = require('../pokemon-showdown/dist/sim');

console.log('Pokemon Showdown Simulator テスト\n');
console.log('=================================\n');

// バトルを作成
const battle = new Sim.Battle({
  formatid: 'gen9vgc2024regh',
});

console.log('✓ Battle オブジェクトを作成しました');
console.log(`  Format: ${battle.format.id}`);
console.log(`  Generation: ${battle.gen}\n`);

// プレイヤー1のチーム（例: カイリュー）
const team1 = `
Dragonite @ Choice Band
Ability: Multiscale
Level: 50
EVs: 252 Atk / 4 SpD / 252 Spe
Adamant Nature
- Extreme Speed
- Earthquake
- Fire Punch
- Ice Punch
`.trim();

// プレイヤー2のチーム（例: イーユイ）
const team2 = `
Chi-Yu @ Focus Sash
Ability: Beads of Ruin
Level: 50
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
IVs: 0 Atk
- Heat Wave
- Dark Pulse
- Overheat
- Protect
`.trim();

try {
  // プレイヤーを参加させる
  battle.setPlayer('p1', {
    name: 'Player 1',
    avatar: 'brendan',
    team: team1,
  });

  battle.setPlayer('p2', {
    name: 'Player 2',
    avatar: 'may',
    team: team2,
  });

  console.log('✓ チームを読み込みました');
  console.log('✓ バトルは自動的に開始されます\n'); // アクティブなポケモンを表示
  console.log('アクティブなポケモン:');
  for (const side of battle.sides) {
    for (const pokemon of side.active) {
      if (pokemon) {
        console.log(`  ${side.name}: ${pokemon.name} (HP: ${pokemon.hp}/${pokemon.maxhp})`);
      }
    }
  }
  console.log();

  // 利用可能な技を表示
  console.log('Player 1 の利用可能な技:');
  const p1pokemon = battle.sides[0].active[0];
  if (p1pokemon) {
    for (const move of p1pokemon.moves) {
      const moveData = battle.dex.moves.get(move);
      console.log(`  - ${moveData.name} (威力: ${moveData.basePower}, タイプ: ${moveData.type})`);
    }
  }
  console.log();

  // サンプル: ターン1の行動を選択（神速を使用）
  console.log('ターン1を実行...');
  battle.choose('p1', 'move extremespeed');
  battle.choose('p2', 'move protect');

  console.log();
  console.log('バトルログ:');
  console.log(battle.log.join('\n'));
} catch (error) {
  console.error('エラーが発生しました:', error.message);
  console.error(error.stack);
}

console.log('\n=================================');
console.log('テスト完了');
