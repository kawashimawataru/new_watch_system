import { useEffect, useMemo, useState } from 'react'
import './App.css'
import { buildSpriteUrl } from './assets/pokemon-sprites'
import movesData from './data/moves.json'
import pokemonNamesData from './data/pokemon-names.json'

const DEFAULT_ENDPOINT = import.meta.env.VITE_PREDICTOR_URL ?? 'http://localhost:8000/evaluate-position'

type ActionScore = {
  move: string
  target: string | null
  score: number
}

type PokemonRecommendation = {
  name: string
  suggestedMoves: ActionScore[]
}

type PlayerEvaluation = {
  winRate: number
  active: PokemonRecommendation[]
}

type PredictorResponse = {
  playerA: PlayerEvaluation
  playerB: PlayerEvaluation
}

type MoveMetadata = {
  name: string
  type: string
  basePower: number
  category: string
  shortDesc: string
  target?: string
  statusEffects?: string[]
}

type BattlePreviewAction = {
  move: string
  target: string | null
  tags: string[]
  metadata: Record<string, unknown> | undefined
  priority?: number
  moveInfo?: MoveMetadata | null
}

type BattlePreviewPokemon = {
  slotIndex: number
  name: string
  hpText: string | null
  hpRaw: number | null
  hpPercent: number | null
  status: string | null
  moves: string[]
  item: string | null
  teraType: string | null
  availableActions: BattlePreviewAction[]
  isFainted?: boolean
}

type BattlePreviewSide = {
  label: string
  active: BattlePreviewPokemon[]
  reserves: BattlePreviewPokemon[]
}

type BattlePreview = {
  playerA: BattlePreviewSide
  playerB: BattlePreviewSide
}

type BattleHistoryEvent = {
  id: string
  turn: number
  player: 'A' | 'B' | 'unknown'
  pokemonName: string | null
  moveName: string | null
  description: string
  targetPokemon: string | null
  damagePercent: number | null
  defenderStatus: string | null
  moveInfo: MoveMetadata | null
  eventType: string
}

type AggregatedHistoryEvent = BattleHistoryEvent & {
  targets: Array<{
    name: string | null
    damagePercent: number | null
    status: string | null
  }>
}

type MoveDex = Record<string, MoveMetadata>
type PokemonNameMap = Record<string, string>

const moveDex = movesData as MoveDex
const pokemonNameMap = pokemonNamesData as PokemonNameMap

const formatPercentage = (value: number) => `${(value * 100).toFixed(1)}%`
const formatScore = (value: number) => `${Math.round(value * 100)}%`
const formatPower = (power?: number | null) => {
  if (!power || power <= 0) return '---'
  return power.toString()
}

const describeTarget = (
  target?: string | null,
  perspective?: 'playerA' | 'playerB',
  slotNameMap?: Record<string, string>,
) => {
  if (!target) return null
  if (target === 'self') return '自分'
  if (target === 'team') return '味方全体'
  if (target === 'adjacentAllyOrSelf') return '味方か自分'
  if (target === 'adjacentAlly') return '味方'
  if (target === 'any') return '任意の対象'
  if (target === 'allAdjacentFoes') return '相手全体'
  if (target === 'allAdjacent') return '周囲すべて'
  if (target === 'spread') return '相手2体全体'
  const slotMatch = target.match(/^([AB])_slot(\d)$/)
  if (slotMatch) {
    const [, side, slot] = slotMatch
    const slotKey = `${side}_slot${slot}`
    if (slotNameMap && slotNameMap[slotKey]) {
      const localized = formatPokemonDisplayName(slotNameMap[slotKey])
      return `${side === 'A' ? '味方' : '相手'}: ${localized}`
    }
    if (perspective) {
      const isSelf =
        (side === 'A' && perspective === 'playerA') || (side === 'B' && perspective === 'playerB')
      return `${isSelf ? '味方' : '相手'}スロット${slot}`
    }
    return `${side === 'A' ? 'Player A' : 'Player B'} slot${slot}`
  }
  return target.replace(/_/g, ' ')
}

const STATUS_LABELS: Record<string, string> = {
  slp: 'ねむり',
  brn: 'やけど',
  par: 'まひ',
  frz: 'こおり',
  tox: 'もうどく',
  psn: 'どく',
  fnt: 'ひんし',
}

const formatPokemonDisplayName = (name?: string | null) => {
  if (!name) return ''
  const ja = pokemonNameMap[name]
  return ja ? `${name} / ${ja}` : name
}

const ACTION_TAG_LABELS: Record<string, string> = {
  protect: 'まもる系',
  spread: '範囲攻撃',
  speed_control: '素早さ操作',
  pivot: '入れ替え',
  boost: '能力上昇',
  redirection: 'このゆび/怒り粉',
  priority: '先制技',
  status: '状態付与',
  support: 'サポート',
}

const ACTION_METADATA_LABELS: Record<string, string> = {
  is_super_effective: '効果バツグン',
  is_stab: 'タイプ一致',
  is_critical: '急所率アップ',
  hits_substitute: 'みがわり対応',
  accuracy: '命中率',
  damage_multiplier: 'ダメージ倍率',
}

const formatStatus = (status?: string | null) => {
  if (!status) return null
  const normalized = status.toLowerCase()
  return STATUS_LABELS[normalized] ?? status.toUpperCase()
}

const TYPE_COLORS: Record<
  string,
  {
    bg: string
    text: string
  }
> = {
  normal: { bg: '#A8A77A', text: '#0f172a' },
  fire: { bg: '#EE8130', text: '#ffffff' },
  water: { bg: '#6390F0', text: '#ffffff' },
  electric: { bg: '#F7D02C', text: '#0f172a' },
  grass: { bg: '#7AC74C', text: '#0f172a' },
  ice: { bg: '#96D9D6', text: '#0f172a' },
  fighting: { bg: '#C22E28', text: '#ffffff' },
  poison: { bg: '#A33EA1', text: '#ffffff' },
  ground: { bg: '#E2BF65', text: '#0f172a' },
  flying: { bg: '#A98FF3', text: '#0f172a' },
  psychic: { bg: '#F95587', text: '#ffffff' },
  bug: { bg: '#A6B91A', text: '#0f172a' },
  rock: { bg: '#B6A136', text: '#0f172a' },
  ghost: { bg: '#735797', text: '#ffffff' },
  dragon: { bg: '#6F35FC', text: '#ffffff' },
  dark: { bg: '#705746', text: '#ffffff' },
  steel: { bg: '#B7B7CE', text: '#0f172a' },
  fairy: { bg: '#D685AD', text: '#0f172a' },
}

const DEFAULT_TYPE_COLOR = { bg: '#CBD5F5', text: '#0f172a' }

const translateCategory = (category?: string) => {
  if (category === 'Physical') return '物理'
  if (category === 'Special') return '特殊'
  return '変化'
}

const getTypeBadgeStyle = (type?: string) => {
  if (!type) return DEFAULT_TYPE_COLOR
  const key = type.toLowerCase()
  return TYPE_COLORS[key] ?? DEFAULT_TYPE_COLOR
}

const toMoveId = (value: string) => value.toLowerCase().replace(/[^a-z0-9]+/g, '')

const getMoveInfo = (moveName?: string | null): MoveMetadata | null => {
  if (!moveName) return null
  const key = toMoveId(moveName)
  return moveDex[key] ?? null
}

const moveAllowsStatus = (moveInfo: MoveMetadata | null, status: string | null) => {
  if (!moveInfo || !status) return false
  const normalized = status.toLowerCase()
  return (moveInfo.statusEffects ?? []).includes(normalized)
}

const parseHpValue = (value?: string | number | null) => {
  if (value === undefined || value === null) {
    return { hpText: null, hpRaw: null, hpPercent: null }
  }
  if (typeof value === 'string') {
    const percentMatch = value.match(/(-?\d+(\.\d+)?)%/)
    const percentNumber = percentMatch ? Number(percentMatch[1]) : null
    const hpPercent =
      percentNumber !== null && !Number.isNaN(percentNumber)
        ? Math.min(Math.max(percentNumber / 100, 0), 1)
        : null
    return { hpText: value, hpRaw: null, hpPercent }
  }
  if (Number.isNaN(value)) {
    return { hpText: null, hpRaw: null, hpPercent: null }
  }
  const hpRaw = value
  const hpPercent =
    value <= 1 ? Math.min(Math.max(value, 0), 1) : Math.min(Math.max(value / 100, 0), 1)
  return { hpText: null, hpRaw, hpPercent }
}

const translateActionTag = (tag: string) => ACTION_TAG_LABELS[tag] ?? tag
const translateMetadataLabel = (key: string) => ACTION_METADATA_LABELS[key] ?? key
const filterActionTags = (action: BattlePreviewAction) => {
  if (action.target && action.target !== 'spread') {
    return action.tags.filter((tag) => tag !== 'spread')
  }
  return action.tags
}

type BattleLogPokemon = {
  name?: string
  hp?: number | string
  status?: string | null
  moves?: string[]
  item?: string
  teraType?: string
}

type BattleLogSide = {
  name?: string
  active?: BattleLogPokemon[]
}

type BattleLogPayload = {
  state?: {
    A?: BattleLogSide
    B?: BattleLogSide
  }
  legalActions?: {
    A?: BattleLogAction[]
    B?: BattleLogAction[]
  }
  turns?: Array<{
    number?: number
    events?: Array<{
      type?: string
      player?: 'A' | 'B'
      pokemon?: string
      move?: string
      targetPlayer?: 'A' | 'B'
      targetPokemon?: string
      damagePercent?: number
      attackerStatus?: string | null
      defenderStatus?: string | null
      text?: string
    }>
  }>
}

type BattleLogAction = {
  pokemon?: string
  slot?: number
  move?: string
  target?: string | null
  tags?: string[]
  metadata?: Record<string, unknown>
  priority?: number
}

const extractBattlePreviewFromLog = (logText: string): BattlePreview | null => {
  if (!logText.trim()) return null
  try {
    const parsed = JSON.parse(logText) as BattleLogPayload
    if (!parsed?.state) return null
    const convertSide = (sideKey: 'A' | 'B', fallbackLabel: string): BattlePreviewSide => {
      const side = parsed.state?.[sideKey]
      const actions = parsed.legalActions?.[sideKey] ?? []
      const actionMap = new Map<number, BattlePreviewAction[]>()
      actions.forEach((action) => {
        if (!action.move) return
        const slotIdx = typeof action.slot === 'number' ? action.slot : 0
        const current = actionMap.get(slotIdx) ?? []
        current.push({
          move: action.move,
          target: action.target ?? null,
          tags: Array.isArray(action.tags)
            ? action.tags.filter((tag): tag is string => typeof tag === 'string')
            : [],
          metadata: action.metadata,
          priority: action.priority,
          moveInfo: getMoveInfo(action.move),
        })
        actionMap.set(slotIdx, current)
      })
      const active = (side?.active ?? []).map((pokemon, index) => {
        const hpInfo = parseHpValue(pokemon.hp)
        const actionTags = actionMap.get(index) ?? []
        return {
          slotIndex: index,
          name: pokemon.name ?? `${fallbackLabel} slot${index + 1}`,
          hpText: hpInfo.hpText,
          hpRaw: hpInfo.hpRaw,
          hpPercent: hpInfo.hpPercent,
          status: formatStatus(pokemon.status),
          moves: Array.isArray(pokemon.moves)
            ? pokemon.moves.filter((move): move is string => typeof move === 'string').slice(0, 4)
            : [],
          item: pokemon.item ?? null,
          teraType: pokemon.teraType ?? null,
          availableActions: actionTags,
          isFainted: hpInfo.hpPercent !== null && hpInfo.hpPercent <= 0,
        }
      })
      const reserves =
        side?.reserves?.map((reserveName, index) => ({
          slotIndex: index,
          name: reserveName,
          hpText: null,
          hpRaw: null,
          hpPercent: 1,
          status: null,
          moves: [],
          item: null,
          teraType: null,
          availableActions: [],
        })) ?? []
      return {
        label: side?.name ?? fallbackLabel,
        active,
        reserves,
      }
    }
    return {
      playerA: convertSide('A', 'Player A'),
      playerB: convertSide('B', 'Player B'),
    }
  } catch {
    return null
  }
}

const buildPreviewFromResponse = (response: PredictorResponse): BattlePreview => ({
  playerA: {
    label: '自分サイド',
    active: response.playerA.active.map((pokemon) => ({
      slotIndex: 0,
      name: pokemon.name,
      hpText: null,
      hpRaw: null,
      hpPercent: null,
      status: null,
      moves: [],
      item: null,
      teraType: null,
      availableActions: [],
    })),
    reserves: [],
  },
  playerB: {
    label: '相手サイド',
    active: response.playerB.active.map((pokemon) => ({
      slotIndex: 0,
      name: pokemon.name,
      hpText: null,
      hpRaw: null,
      hpPercent: null,
      status: null,
      moves: [],
      item: null,
      teraType: null,
      availableActions: [],
    })),
    reserves: [],
  },
})

const describeHistoryMove = (event: {
  player?: 'A' | 'B'
  pokemon?: string
  move?: string
  targetPokemon?: string
  damagePercent?: number
}) => {
  const actorLabel = event.player === 'B' ? '相手' : '自分'
  const pokemonLabel = event.pokemon ? `の ${event.pokemon}` : ''
  const moveLabel = event.move ? `が「${event.move}」` : 'が行動'
  const target = event.targetPokemon ? ` → ${event.targetPokemon}` : ''
  const damage =
    typeof event.damagePercent === 'number' ? ` (${event.damagePercent}% ダメージ)` : ''
  return `${actorLabel}${pokemonLabel}${moveLabel}${target}${damage}`
}

const extractBattleHistory = (logText: string): BattleHistoryEvent[] => {
  if (!logText.trim()) return []
  try {
    const parsed = JSON.parse(logText) as BattleLogPayload
    const turns = parsed.turns ?? []
    const events: BattleHistoryEvent[] = []
    turns.forEach((turn) => {
      const turnNumber = typeof turn.number === 'number' ? turn.number : events.length + 1
      ;(turn.events ?? []).forEach((event, idx) => {
        let description = ''
        if (event.type === 'move') {
          description = describeHistoryMove(event)
        } else if (event.text) {
          description = event.text
        } else if (event.type) {
          description = `${event.type} イベント`
        } else {
          description = '不明なイベント'
        }
        events.push({
          id: `${turnNumber}-${idx}`,
          turn: turnNumber,
          player: event.player ?? 'unknown',
          pokemonName: event.pokemon ?? null,
          moveName: event.move ?? null,
          description,
          targetPokemon: event.targetPokemon ?? null,
          damagePercent: typeof event.damagePercent === 'number' ? event.damagePercent : null,
          defenderStatus: typeof event.defenderStatus === 'string' ? event.defenderStatus : null,
          moveInfo: getMoveInfo(event.move),
          eventType: event.type ?? 'unknown',
        })
      })
    })
    return events
  } catch {
    return []
  }
}

const findTopRecommendation = (player: PlayerEvaluation) => {
  let bestMove: ActionScore | null = null
  let bestPokemon: string | null = null
  player.active.forEach((pokemon) => {
    pokemon.suggestedMoves.forEach((move) => {
      if (!bestMove || move.score > bestMove.score) {
        bestMove = move
        bestPokemon = pokemon.name
      }
    })
  })
  return { bestMove, bestPokemon }
}

const buildPlayerExplanation = (
  sideKey: 'playerA' | 'playerB',
  label: string,
  player: PlayerEvaluation,
  opponent: PlayerEvaluation,
  slotNameMap?: Record<string, string>,
) => {
  const insight: string[] = []
  const winRateDiff = player.winRate - opponent.winRate
  const diffText =
    Math.abs(winRateDiff) < 0.01
      ? 'ほぼ互角'
      : winRateDiff > 0
      ? `相手より ${(winRateDiff * 100).toFixed(1)}pt リード`
      : `相手に ${(Math.abs(winRateDiff) * 100).toFixed(1)}pt ビハインド`
  insight.push(`${label}の推定勝率は ${formatPercentage(player.winRate)} で、${diffText} の状況です。`)
  if (player.active.length === 0) {
    insight.push('アクティブなポケモンがいないため、盤面を立て直す必要があります。')
    return insight
  }
  const { bestMove, bestPokemon } = findTopRecommendation(player)
  if (bestMove && bestPokemon) {
    const targetLabel = describeTarget(bestMove.target, sideKey, slotNameMap) ?? '対象未指定'
    insight.push(
      `${bestPokemon} の 「${bestMove.move}」 が ${formatScore(bestMove.score)} と最も高評価。対象: ${targetLabel}。`,
    )
  }
  const statusCount = player.active.filter((pokemon) => Boolean(pokemon.status)).length
  if (statusCount > 0) {
    insight.push(`現在 ${statusCount} 体が状態異常で、動きが制限されています。`)
  }
  return insight
}

function App() {
  const [teamA, setTeamA] = useState('')
  const [teamB, setTeamB] = useState('')
  const [battleLog, setBattleLog] = useState('')
  const [estimatedEvs, setEstimatedEvs] = useState('')
  const [algorithm, setAlgorithm] = useState('heuristic')
  const [apiEndpoint, setApiEndpoint] = useState(DEFAULT_ENDPOINT)
  const [response, setResponse] = useState<PredictorResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [historyPage, setHistoryPage] = useState(0)
  const battleLogPreview = useMemo(() => extractBattlePreviewFromLog(battleLog), [battleLog])
  const battlePreview = battleLogPreview ?? (response ? buildPreviewFromResponse(response) : null)
  const battleHistory = useMemo(() => extractBattleHistory(battleLog), [battleLog])
  const slotNameMap = useMemo(() => {
    if (!battlePreview) return {}
    const map: Record<string, string> = {}
    battlePreview.playerA.active.forEach((pokemon, idx) => {
      map[`A_slot${idx + 1}`] = pokemon.name
    })
    battlePreview.playerB.active.forEach((pokemon, idx) => {
      map[`B_slot${idx + 1}`] = pokemon.name
    })
    return map
  }, [battlePreview])
  const pokemonStateMap = useMemo(() => {
    if (!battlePreview) return {}
    const map: Record<string, BattlePreviewPokemon> = {}
    battlePreview.playerA.active.forEach((pokemon) => {
      map[pokemon.name] = pokemon
    })
    battlePreview.playerB.active.forEach((pokemon) => {
      map[pokemon.name] = pokemon
    })
    return map
  }, [battlePreview])
  const aggregateHistoryEvents = (events: BattleHistoryEvent[]): AggregatedHistoryEvent[] => {
    const aggregated: AggregatedHistoryEvent[] = []
    events.forEach((event) => {
      if (event.eventType === 'move' && event.moveName) {
        const targetInfo = {
          name: event.targetPokemon ?? null,
          damagePercent: event.damagePercent,
          status: event.defenderStatus,
        }
        const last = aggregated[aggregated.length - 1]
        if (
          last &&
          last.eventType === 'move' &&
          last.player === event.player &&
          last.pokemonName === event.pokemonName &&
          last.moveName === event.moveName
        ) {
          last.targets.push(targetInfo)
        } else {
          aggregated.push({ ...event, targets: [targetInfo] })
        }
      } else {
        aggregated.push({ ...event, targets: [] })
      }
    })
    return aggregated
  }

  const historyPages = useMemo(() => {
    const grouped = new Map<number, BattleHistoryEvent[]>()
    battleHistory.forEach((event) => {
      if (!grouped.has(event.turn)) grouped.set(event.turn, [])
      grouped.get(event.turn)!.push(event)
    })
    return Array.from(grouped.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([turn, events]) => ({ turn, events, aggregatedEvents: aggregateHistoryEvents(events) }))
  }, [battleHistory])
  useEffect(() => {
    setHistoryPage(historyPages.length ? historyPages.length - 1 : 0)
  }, [historyPages.length])
  const currentHistoryPage = historyPages[historyPage] ?? null
  const explanation =
    response && response.playerA && response.playerB
      ? {
          playerA: buildPlayerExplanation('playerA', '自分サイド', response.playerA, response.playerB, slotNameMap),
          playerB: buildPlayerExplanation('playerB', '相手サイド', response.playerB, response.playerA, slotNameMap),
        }
      : null
  const renderBattleSide = (key: 'playerA' | 'playerB') => {
    if (!battlePreview) return null
    const side = battlePreview[key]
    const spriteDirection = key === 'playerA' ? 'left' : 'right'
    const reservesSpriteDirection = spriteDirection === 'left' ? 'right' : 'left'
    return (
      <div className={`battle-side ${spriteDirection}`} key={key}>
        <p className="battle-side-label">{side.label}</p>
        {side.active.length === 0 ? (
          <p className="hint small">アクティブなポケモンがいません</p>
        ) : (
          side.active.map((pokemon, index) => {
            const spriteUrl = buildSpriteUrl(pokemon.name)
            const slotLabel = index === 0 ? 'スロット1' : 'スロット2'
            const displayName = formatPokemonDisplayName(pokemon.name)
            return (
              <div className="battle-slot" key={`${key}-${pokemon.name}-${index}`}>
                {spriteUrl ? (
                  <img
                    src={spriteUrl}
                    alt={pokemon.name}
                    className="sprite battle-sprite"
                    loading="lazy"
                    width={64}
                    height={64}
                  />
                ) : (
                  <div className="sprite placeholder" />
                )}
                <div>
                  <p className="slot-position">{slotLabel}</p>
                  <h4>{displayName}</h4>
                  <div className="slot-meta">
                    {(pokemon.hpRaw !== null || pokemon.hpPercent !== null || pokemon.hpText) && (
                      <span className="slot-hp">
                        {pokemon.hpRaw !== null ? `${pokemon.hpRaw} HP` : null}
                        {pokemon.hpPercent !== null ? ` (${Math.round(pokemon.hpPercent * 100)}%)` : null}
                        {pokemon.hpText ? ` / ${pokemon.hpText}` : null}
                      </span>
                    )}
                    {pokemon.status ? <span className="slot-status-badge">{pokemon.status}</span> : null}
                  </div>
                  {typeof pokemon.hpPercent === 'number' ? (
                    <div className="slot-hp-bar" aria-hidden="true">
                      <div className="slot-hp-fill" style={{ width: `${pokemon.hpPercent * 100}%` }} />
                    </div>
                  ) : null}
                  {pokemon.item ? <p className="slot-item">持ち物: {pokemon.item}</p> : null}
                  {pokemon.teraType ? <p className="slot-item">テラスタイプ: {pokemon.teraType}</p> : null}
                  {pokemon.moves.length ? (
                    <div className="slot-moves">
                      {pokemon.moves.map((move) => {
                        const moveInfo = getMoveInfo(move)
                        const badgeStyle = getTypeBadgeStyle(moveInfo?.type)
                        return (
                          <div className="slot-move-chip" key={`${pokemon.name}-${move}`}>
                            <div className="slot-move-chip-header">
                              <span className="slot-move-name">{move}</span>
                              {moveInfo?.type ? (
                                <span
                                  className="type-badge"
                                  style={{ backgroundColor: badgeStyle.bg, color: badgeStyle.text }}
                                >
                                  {moveInfo.type}
                                </span>
                              ) : null}
                            </div>
                            {moveInfo ? (
                              <div className="slot-move-details">
                                <span>威力: {formatPower(moveInfo.basePower)}</span>
                                <span>分類: {translateCategory(moveInfo.category)}</span>
                              </div>
                            ) : null}
                          </div>
                        )
                      })}
                    </div>
                  ) : null}
                  {pokemon.availableActions.length ? (
                    <div className="slot-actions">
                      <p className="slot-actions-label">このターンの候補行動</p>
                      <ul>
                        {pokemon.availableActions.map((action) => {
                          const tags = filterActionTags(action)
                          const metadataBadges = action.metadata
                            ? Object.entries(action.metadata).filter(([_, value]) =>
                                typeof value === 'boolean' ? value : Boolean(value),
                              )
                            : []
                          const badgeStyle = getTypeBadgeStyle(action.moveInfo?.type)
                          return (
                            <li key={`${pokemon.name}-${action.move}-${action.target ?? 'none'}`}>
                              <div className="slot-action-header">
                                <div>
                                  <div className="slot-action-title">
                                    <span className="slot-action-name">{action.move}</span>
                                    {action.moveInfo?.type ? (
                                      <span
                                        className="type-badge"
                                        style={{ backgroundColor: badgeStyle.bg, color: badgeStyle.text }}
                                      >
                                        {action.moveInfo.type}
                                      </span>
                                    ) : null}
                                  </div>
                                  <div className="slot-action-meta-line">
                                    <span>威力: {formatPower(action.moveInfo?.basePower)}</span>
                                    <span>分類: {translateCategory(action.moveInfo?.category)}</span>
                                    {describeTarget(action.target, key, slotNameMap) ? (
                                      <span>対象: {describeTarget(action.target, key, slotNameMap)}</span>
                                    ) : null}
                                  </div>
                                </div>
                                {action.priority !== undefined ? (
                                  <span className="slot-action-priority">優先度: {action.priority}</span>
                                ) : null}
                              </div>
                              {action.moveInfo?.shortDesc ? (
                                <p className="slot-action-effect">{action.moveInfo.shortDesc}</p>
                              ) : null}
                              {tags.length || metadataBadges.length ? (
                                <div className="slot-action-tags">
                                  {tags.map((tag) => (
                                    <span className="slot-action-tag" key={tag}>
                                      {translateActionTag(tag)}
                                    </span>
                                  ))}
                                  {metadataBadges.map(([key, value]) => (
                                    <span className="slot-action-meta" key={key}>
                                      {typeof value === 'boolean'
                                        ? translateMetadataLabel(key)
                                        : `${translateMetadataLabel(key)}: ${value}`}
                                    </span>
                                  ))}
                                </div>
                              ) : null}
                            </li>
                          )
                        })}
                      </ul>
                    </div>
                  ) : null}
                </div>
              </div>
            )
          })
        )}
        <div className={`reserve-row ${reservesSpriteDirection}`}>
          {side.reserves.map((reserve) => {
            const reserveSprite = buildSpriteUrl(reserve.name)
            const reserveName = formatPokemonDisplayName(reserve.name)
            return (
              <div className="reserve-pill" key={`${key}-reserve-${reserve.name}`}>
                {reserveSprite ? <img src={reserveSprite} alt={reserve.name ?? ''} width={40} height={40} /> : null}
                <span>{reserveName}</span>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  const parseJson = (label: string, value: string) => {
    try {
      return value ? JSON.parse(value) : undefined
    } catch (err) {
      throw new Error(`${label} が正しいJSONではありません: ${(err as Error).message}`)
    }
  }

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = {
        team_a_pokepaste: teamA,
        team_b_pokepaste: teamB,
        battle_log: parseJson('Battle Log', battleLog),
        estimated_evs: parseJson('Estimated EVs', estimatedEvs),
        algorithm,
      }
      if (!payload.team_a_pokepaste || !payload.team_b_pokepaste || !payload.battle_log) {
        throw new Error('Team / Battle Log の入力が必要です')
      }
      const res = await fetch(apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        throw new Error(`API Error: ${res.status}`)
      }
      const json = (await res.json()) as PredictorResponse
      setResponse(json)
    } catch (err) {
      setResponse(null)
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const loadSample = async () => {
    try {
      const res = await fetch('/sample-data.json')
      const data = await res.json()
      setTeamA(data.teamA)
      setTeamB(data.teamB)
      setBattleLog(JSON.stringify(data.battleLog, null, 2))
      setEstimatedEvs(JSON.stringify(data.estimatedEvs, null, 2))
      setAlgorithm('heuristic')
      setResponse(null)
      setError(null)
    } catch {
      setError('サンプルデータの読み込みに失敗しました')
    }
  }

  return (
    <div className="app-shell">
      <header>
        <h1>VGC Position Evaluator</h1>
        <p>Pokepaste / Showdown ログを入力して勝率と推奨技を取得します。</p>
      </header>
      <section className="workspace-grid">
        <div className="workspace-main">
          <div className="battle-preview-card">
            <h2>バトルフィールド</h2>
            {battlePreview ? (
              <div className="battle-preview-stage">
                {renderBattleSide('playerA')}
                <div className="battle-vs">VS</div>
                {renderBattleSide('playerB')}
              </div>
            ) : (
              <p className="hint">Battle Log JSON を入力すると現在の盤面がここに表示されます。</p>
            )}
          </div>
          <div className="history-pager">
            <div className="history-pager-header">
              <h2>これまでの行動</h2>
              {historyPages.length ? (
                <div className="pager-controls">
                  <button
                    type="button"
                    onClick={() => setHistoryPage((prev) => Math.max(prev - 1, 0))}
                    disabled={historyPage === 0}
                  >
                    ◀ 前のターン
                  </button>
                  <span>
                    Turn {currentHistoryPage?.turn ?? '-'} / {historyPages.length}
                  </span>
                  <button
                    type="button"
                    onClick={() => setHistoryPage((prev) => Math.min(prev + 1, historyPages.length - 1))}
                    disabled={historyPage >= historyPages.length - 1}
                  >
                    次のターン ▶
                  </button>
                </div>
              ) : null}
              {historyPages.length ? (
                <div className="history-jump-grid">
                  {historyPages.map((page, index) => (
                    <button
                      type="button"
                      key={`history-jump-${page.turn}`}
                      className={index === historyPage ? 'active' : ''}
                      onClick={() => setHistoryPage(index)}
                    >
                      Turn {page.turn}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
            {currentHistoryPage ? (
              <div className="history-book-page">
                <p className="history-turn-label">Turn {currentHistoryPage.turn}</p>
            {currentHistoryPage.aggregatedEvents.map((event) => {
              const spriteUrl = event.pokemonName ? buildSpriteUrl(event.pokemonName) : null
              const localizedActor = formatPokemonDisplayName(event.pokemonName ?? '')
              const moveInfo = event.moveInfo
              const badgeStyle = getTypeBadgeStyle(moveInfo?.type)
              return (
                <div
                      className={`history-event-card ${event.player === 'B' ? 'opponent' : event.player === 'A' ? 'self' : ''}`}
                      key={event.id}
                    >
                      <div className="history-event-header">
                        <div className="history-actor">
                          {spriteUrl ? (
                            <img src={spriteUrl} alt={event.pokemonName ?? 'Pokemon'} className="sprite history-sprite" loading="lazy" width={48} height={48} />
                          ) : (
                            <div className="sprite history-placeholder" />
                          )}
                          <div>
                            <p className="history-title">{localizedActor || '未知のポケモン'}</p>
                            {event.moveName ? (
                              <div className="history-move-line">
                                <span>{event.moveName}</span>
                                {moveInfo?.type ? (
                                  <span className="type-badge" style={{ backgroundColor: badgeStyle.bg, color: badgeStyle.text }}>
                                    {moveInfo.type}
                                  </span>
                                ) : null}
                                <span className="history-move-meta">分類: {translateCategory(moveInfo?.category)}</span>
                                <span className="history-move-meta">威力: {formatPower(moveInfo?.basePower)}</span>
                              </div>
                            ) : null}
                          </div>
                        </div>
                        <div className="history-damage">
                          {typeof event.damagePercent === 'number' ? `${event.damagePercent}% ダメージ` : 'ダメージ不明'}
                        </div>
                      </div>
                      <p className="history-description">{event.description}</p>
                  {event.targets.length ? (
                    <div className="history-targets">
                      {event.targets.map((target, idx) => {
                        const targetName = formatPokemonDisplayName(target.name ?? '')
                        const targetState = target.name ? pokemonStateMap[target.name] : undefined
                        const currentHpPercent =
                          typeof targetState?.hpPercent === 'number' ? targetState.hpPercent : null
                        const damagePercent = target.damagePercent ?? 0
                        const showStatus = moveAllowsStatus(moveInfo, target.status)
                        return (
                          <div className="history-target-card" key={`${event.id}-target-${idx}`}>
                            <div className="history-target-header">
                              <span>{targetName || '対象不明'}</span>
                              <span className="history-target-damage">{damagePercent}% ダメージ</span>
                            </div>
                            <div className="history-target-bars">
                              <div className="history-target-hpbar" aria-label="現在HP">
                                <div
                                  className="history-target-hpfill"
                                  style={{ width: `${currentHpPercent !== null ? currentHpPercent * 100 : 0}%` }}
                                />
                              </div>
                              {showStatus && target.status ? (
                                <span className="history-target-status">付与: {formatStatus(target.status)}</span>
                              ) : null}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  ) : null}
                </div>
              )
            })}
              </div>
          ) : (
            <p className="hint">Battle Log JSON を入力すると、ターン履歴がここに表示されます。</p>
          )}
          {historyPages.length ? (
            <div className="history-chronology">
              {historyPages.map((page) => (
                <div className="history-chronology-card" key={`chronology-${page.turn}`}>
                  <h4>Turn {page.turn}</h4>
                  <ul>
                    {page.events.map((event) => (
                      <li key={`chronology-${page.turn}-${event.id}`}>
                        <span className="chronology-actor">{formatPokemonDisplayName(event.pokemonName ?? '')}</span>
                        {event.moveName ? ` が「${event.moveName}」` : ' が行動'}
                        {event.targetPokemon ? ` → ${formatPokemonDisplayName(event.targetPokemon)}` : ''}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          ) : null}
        </div>
        </div>
        <aside className="workspace-sidebar">
          <div className="sidebar-panel">
            <h3>Pokepaste</h3>
            <div className="input-grid">
              <label>
                自分サイド
                <textarea value={teamA} onChange={(e) => setTeamA(e.target.value)} rows={10} />
              </label>
              <label>
                相手サイド
                <textarea value={teamB} onChange={(e) => setTeamB(e.target.value)} rows={10} />
              </label>
            </div>
          </div>
          <div className="sidebar-panel">
            <h3>ログ & EV</h3>
            <div className="input-grid">
              <label>
                Battle Log JSON
                <textarea value={battleLog} onChange={(e) => setBattleLog(e.target.value)} rows={8} />
              </label>
              <label>
                Estimated EV JSON (任意)
                <textarea value={estimatedEvs} onChange={(e) => setEstimatedEvs(e.target.value)} rows={8} />
              </label>
            </div>
          </div>
          <div className="sidebar-panel">
            <h3>操作</h3>
            <div className="sidebar-controls">
              <label>
                API Endpoint
                <input value={apiEndpoint} onChange={(e) => setApiEndpoint(e.target.value)} />
              </label>
              <label>
                アルゴリズム
                <select value={algorithm} onChange={(e) => setAlgorithm(e.target.value)}>
                  <option value="heuristic">Heuristic (P1)</option>
                  <option value="mcts" disabled>
                    MCTS (coming soon)
                  </option>
                  <option value="ml" disabled>
                    ML
                  </option>
                </select>
              </label>
              <button type="button" onClick={loadSample}>
                サンプルを読み込む
              </button>
              <button type="button" onClick={handleSubmit} disabled={loading}>
                {loading ? '計算中...' : 'evaluate_position を実行'}
              </button>
              {error && <p className="error">{error}</p>}
            </div>
          </div>
        </aside>
      </section>
      <section className="results">
        <h2>結果</h2>
        {response ? (
          <>
            <div className="results-grid">
              {([
                ['playerA', response.playerA] as const,
                ['playerB', response.playerB] as const,
              ]).map(([key, player]) => (
                <article className="player-card" key={key}>
                  <div className="player-header">
                    <div>
                      <p className="player-label">{key === 'playerA' ? '自分サイド' : '相手サイド'}</p>
                      <h3>{key === 'playerA' ? 'Player A' : 'Player B'}</h3>
                    </div>
                    <div className="win-gauge" role="img" aria-label="推定勝率ゲージ">
                      <div className="win-gauge-value">{formatPercentage(player.winRate)}</div>
                      <div className="win-gauge-bar" aria-hidden="true">
                        <div className="win-gauge-fill" style={{ width: `${player.winRate * 100}%` }} />
                      </div>
                      <span className="win-gauge-label">推定勝率</span>
                    </div>
                  </div>
                  {player.active.length === 0 ? (
                    <p className="hint">アクティブなポケモンがいません</p>
                  ) : (
                    <div className="pokemon-column">
                      {player.active.map((pokemon) => {
                        const spriteUrl = buildSpriteUrl(pokemon.name)
                        const displayName = formatPokemonDisplayName(pokemon.name)
                        return (
                          <div className="pokemon-card" key={`${key}-${pokemon.name}`}>
                            <div className="pokemon-header">
                              {spriteUrl ? (
                                <img
                                  src={spriteUrl}
                                  alt={pokemon.name}
                                  className="sprite"
                                  loading="lazy"
                                  width={72}
                                  height={72}
                                />
                              ) : null}
                              <div>
                                <h4>{displayName}</h4>
                                <p className="moves-label">おすすめ技</p>
                              </div>
                            </div>
                            <ul className="move-list">
                              {pokemon.suggestedMoves.length === 0 ? (
                                <li className="move-empty">まだおすすめ技がありません</li>
                              ) : (
                                pokemon.suggestedMoves.map((move) => {
                                  const moveInfo = getMoveInfo(move.move)
                                  const badgeStyle = getTypeBadgeStyle(moveInfo?.type)
                                  const targetLabel =
                                    describeTarget(move.target, key, slotNameMap) ?? '対象未指定'
                                  const moveScorePercent = Math.min(Math.max(move.score, 0), 1) * 100
                                  return (
                                    <li key={`${pokemon.name}-${move.move}-${move.target ?? 'none'}`}>
                                      <div className="move-row">
                                        <div className="move-text">
                                          <div className="move-title">
                                            <span className="move-name">{move.move}</span>
                                            {moveInfo?.type ? (
                                              <span
                                                className="type-badge"
                                                style={{ backgroundColor: badgeStyle.bg, color: badgeStyle.text }}
                                              >
                                                {moveInfo.type}
                                              </span>
                                            ) : null}
                                          </div>
                                          <div className="move-meta">
                                            <span>威力: {formatPower(moveInfo?.basePower)}</span>
                                            <span>分類: {translateCategory(moveInfo?.category)}</span>
                                            <span>対象: {targetLabel}</span>
                                          </div>
                                          {moveInfo?.shortDesc ? (
                                            <p className="move-effect">{moveInfo.shortDesc}</p>
                                          ) : null}
                                        </div>
                                        <span className="move-score">{formatScore(move.score)}</span>
                                      </div>
                                      <div className="move-progress" aria-hidden="true">
                                        <div className="move-progress-fill" style={{ width: `${moveScorePercent}%` }} />
                                      </div>
                                    </li>
                                  )
                                })
                              )}
                            </ul>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </article>
              ))}
            </div>
            {explanation ? (
              <div className="analysis-insights">
                {(['playerA', 'playerB'] as const).map((key) => (
                  <article className="insight-card" key={key}>
                    <h3>{key === 'playerA' ? '自分サイドの考察' : '相手サイドの考察'}</h3>
                    <ul>
                      {explanation[key].map((line, index) => (
                        <li key={`${key}-insight-${index}`}>{line}</li>
                      ))}
                    </ul>
                  </article>
                ))}
              </div>
            ) : null}
            <details className="raw-json">
              <summary>Raw JSON</summary>
              <pre>{JSON.stringify(response, null, 2)}</pre>
            </details>
          </>
        ) : (
          <p className="hint">まだ結果はありません。入力後に実行してください。</p>
        )}
      </section>
    </div>
  )
}

export default App
