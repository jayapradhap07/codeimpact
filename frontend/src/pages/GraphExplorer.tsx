import { useState, useEffect, useRef, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Network,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Minimize2,
  Search,
  Sparkles,
  ArrowRight,
  Code2,
  FileCode,
  Globe,
  CheckCircle2,
  Eye,
  EyeOff,
  Crosshair,
  Compass,
  Sliders,
  Layers,
  LayoutGrid,
} from 'lucide-react'
import * as d3 from 'd3'
import { useNavigate } from 'react-router-dom'
import { api } from '../services/api'
import type { Repository, GraphData, GraphNode, NodeType, EdgeType } from '../types'

// Rich curated node colors
const NODE_COLORS: Record<NodeType, string> = {
  file: '#38bdf8',       // Sky blue
  class: '#c084fc',      // Violet/Purple
  function: '#2dd4bf',   // Teal
  method: '#34d399',     // Emerald
  api: '#fbbf24',        // Amber
  component: '#f472b6',  // Pink
  test: '#a3e635',       // Lime
  variable: '#94a3b8',   // Slate
}

const NODE_ICONS: Record<NodeType, string> = {
  file: '📄',
  class: '🏛️',
  function: '⚡',
  method: '🔧',
  api: '🌐',
  component: '⚛️',
  test: '🧪',
  variable: '📦',
}

const NODE_SIZES: Record<NodeType, number> = {
  file: 12,
  class: 11,
  function: 8,
  method: 7,
  api: 11,
  component: 10,
  test: 8,
  variable: 5,
}

// Edge colors by relationship type
const EDGE_COLORS: Record<EdgeType, string> = {
  imports: '#38bdf8',    // Sky blue
  calls: '#34d399',      // Emerald green
  contains: '#818cf8',   // Indigo
  depends_on: '#fbbf24', // Amber
  inherits: '#f472b6',   // Pink
  uses: '#60a5fa',       // Blue
  tests: '#a3e635',      // Lime
}

type ViewPreset = 'all' | 'calls' | 'architecture' | 'api'
type SpacingMode = 'compact' | 'balanced' | 'spacious'
type ArchLayoutMode = 'tiered' | 'clustered'

interface ArchLayer {
  id: string
  name: string
  icon: string
  color: string
  description: string
  order: number
}

const ARCH_LAYERS: Record<string, ArchLayer> = {
  pages: { id: 'pages', name: 'UI Pages & Routes', icon: '📱', color: '#38bdf8', description: 'Page views, screens & router entrypoints', order: 0 },
  components: { id: 'components', name: 'UI Components', icon: '🧩', color: '#f472b6', description: 'Modular, reusable frontend views', order: 1 },
  state: { id: 'state', name: 'State & Context', icon: '⚡', color: '#fbbf24', description: 'Global state, context providers & hooks', order: 2 },
  api: { id: 'api', name: 'Controllers & Logic', icon: '🌐', color: '#34d399', description: 'Route controllers, handlers & services', order: 3 },
  models: { id: 'models', name: 'Data & Models', icon: '🗄️', color: '#c084fc', description: 'Database schemas, entities & persistence', order: 4 },
  core: { id: 'core', name: 'Core & Config', icon: '⚙️', color: '#94a3b8', description: 'Configurations, utilities & middleware', order: 5 },
}

function classifyNodeToLayer(node: GraphNode): ArchLayer {
  const p = (node.file_path || node.id || '').toLowerCase().replace(/\\/g, '/')
  const name = (node.name || '').toLowerCase()

  if (p.includes('/pages/') || p.includes('/views/') || p.includes('/screens/') || name === 'app' || name === 'main' || p.endsWith('app.jsx') || p.endsWith('app.tsx') || p.endsWith('main.jsx') || p.endsWith('main.tsx')) {
    return ARCH_LAYERS.pages
  }
  if (p.includes('/components/') || p.includes('/ui/') || p.includes('/widgets/') || node.node_type === 'component') {
    return ARCH_LAYERS.components
  }
  if (p.includes('/context/') || p.includes('/store/') || p.includes('/hooks/') || p.includes('/state/') || p.includes('/redux/') || name.includes('context') || name.includes('provider')) {
    return ARCH_LAYERS.state
  }
  if (p.includes('/controllers/') || p.includes('/routes/') || p.includes('/api/') || p.includes('/handlers/') || p.includes('/services/') || node.node_type === 'api' || name.includes('controller')) {
    return ARCH_LAYERS.api
  }
  if (p.includes('/models/') || p.includes('/db/') || p.includes('/schemas/') || p.includes('/entities/') || name.includes('model') || name.includes('schema')) {
    return ARCH_LAYERS.models
  }
  return ARCH_LAYERS.core
}

interface D3Node extends d3.SimulationNodeDatum {
  id: string
  name: string
  node_type: NodeType
  file_path: string | null
  color: string
  radius: number
  directory?: string
  layer: ArchLayer
  degree: number
}

interface D3Link extends d3.SimulationLinkDatum<D3Node> {
  source: string | D3Node
  target: string | D3Node
  edge_type: EdgeType
}

export default function GraphExplorer() {
  const navigate = useNavigate()
  const svgRef = useRef<SVGSVGElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const [repos, setRepos] = useState<Repository[]>([])
  const [selectedRepo, setSelectedRepo] = useState<number | null>(null)
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [loading, setLoading] = useState(false)

  // Fullscreen, Spacing & Architecture Layout States
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [spacingMode, setSpacingMode] = useState<SpacingMode>('balanced')
  const [archLayoutMode, setArchLayoutMode] = useState<ArchLayoutMode>('tiered')

  // Filters & Presets
  const [viewPreset, setViewPreset] = useState<ViewPreset>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [hideIsolated, setHideIsolated] = useState(true)
  const [focusNeighborhoodNodeId, setFocusNeighborhoodNodeId] = useState<string | null>(null)

  const [filterTypes, setFilterTypes] = useState<Set<NodeType>>(
    new Set(['file', 'class', 'function', 'method', 'api', 'component', 'test'])
  )
  const [filterEdges, setFilterEdges] = useState<Set<EdgeType>>(
    new Set(['calls', 'imports', 'contains', 'depends_on', 'inherits', 'uses', 'tests'])
  )

  // Selection & Inspector
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [hoveredNode, setHoveredNode] = useState<D3Node | null>(null)

  const simulationRef = useRef<d3.Simulation<D3Node, D3Link> | null>(null)
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const gRef = useRef<d3.Selection<SVGGElement, unknown, null, undefined> | null>(null)

  // Listen for ESC key to exit fullscreen
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isFullscreen])

  // Fetch repositories
  useEffect(() => {
    api.listRepositories().then((res) => {
      const ready = res.repositories.filter((r) => r.status === 'ready')
      setRepos(ready)
      if (ready.length > 0) setSelectedRepo(ready[0].id)
    }).catch(() => {})
  }, [])

  // Load graph on repo change
  useEffect(() => {
    if (selectedRepo) {
      loadGraph(selectedRepo)
      setSelectedNode(null)
      setFocusNeighborhoodNodeId(null)
    }
  }, [selectedRepo])

  async function loadGraph(repoId: number) {
    setLoading(true)
    try {
      const data = await api.getRepositoryGraph(repoId)
      setGraphData(data)
    } catch {
      setGraphData(null)
    } finally {
      setLoading(false)
    }
  }

  // Preset switch handler
  const handlePresetChange = (preset: ViewPreset) => {
    setViewPreset(preset)
    if (preset === 'all') {
      setFilterTypes(new Set(['file', 'class', 'function', 'method', 'api', 'component', 'test']))
      setFilterEdges(new Set(['calls', 'imports', 'contains', 'depends_on', 'inherits', 'uses', 'tests']))
      setHideIsolated(true)
    } else if (preset === 'calls') {
      setFilterTypes(new Set(['function', 'method', 'api', 'component']))
      setFilterEdges(new Set(['calls', 'depends_on', 'uses']))
      setHideIsolated(true)
    } else if (preset === 'architecture') {
      // In Architecture view, include files, components, classes, and APIs with all dependency flows
      setFilterTypes(new Set(['file', 'class', 'api', 'component']))
      setFilterEdges(new Set(['imports', 'depends_on', 'calls', 'uses', 'inherits', 'contains']))
      setHideIsolated(false) // Show all architecture modules in their respective layers
    } else if (preset === 'api') {
      setFilterTypes(new Set(['api', 'function', 'method', 'class']))
      setFilterEdges(new Set(['depends_on', 'calls', 'contains']))
      setHideIsolated(true)
    }
  }

  // Pre-calculate node connections for inspector and neighborhood focus
  const nodeConnections = useMemo(() => {
    if (!graphData) return { callers: new Map<string, GraphNode[]>(), callees: new Map<string, GraphNode[]>() }
    const nodeMap = new Map(graphData.nodes.map((n) => [n.id, n]))
    const callers = new Map<string, GraphNode[]>()
    const callees = new Map<string, GraphNode[]>()

    graphData.nodes.forEach((n) => {
      callers.set(n.id, [])
      callees.set(n.id, [])
    })

    graphData.edges.forEach((e) => {
      const srcNode = nodeMap.get(e.source)
      const tgtNode = nodeMap.get(e.target)
      if (srcNode && tgtNode) {
        callees.get(e.source)?.push(tgtNode)
        callers.get(e.target)?.push(srcNode)
      }
    })

    return { callers, callees }
  }, [graphData])

  // Spacing Configuration Parameters
  const spacingConfig = useMemo(() => {
    if (spacingMode === 'compact') {
      return {
        charge: -180,
        collideRadius: 18,
        containsDist: 40,
        callsDist: 90,
        otherDist: 110,
        clusterRadiusMult: 0.35,
      }
    } else if (spacingMode === 'spacious') {
      return {
        charge: -650,
        collideRadius: 44,
        containsDist: 90,
        callsDist: 210,
        otherDist: 260,
        clusterRadiusMult: 0.58,
      }
    }
    // Balanced default
    return {
      charge: -380,
      collideRadius: 28,
      containsDist: 60,
      callsDist: 145,
      otherDist: 180,
      clusterRadiusMult: 0.46,
    }
  }, [spacingMode])

  // Render D3 Graph & Architecture
  useEffect(() => {
    if (!graphData || !svgRef.current || !containerRef.current) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const container = containerRef.current
    const width = container.clientWidth
    const height = container.clientHeight

    const isArchTiered = viewPreset === 'architecture' && archLayoutMode === 'tiered'

    // Node degree map across allowed edges
    const degreeMap = new Map<string, number>()
    graphData.edges.forEach((e) => {
      if (filterEdges.has(e.edge_type)) {
        degreeMap.set(e.source, (degreeMap.get(e.source) || 0) + 1)
        degreeMap.set(e.target, (degreeMap.get(e.target) || 0) + 1)
      }
    })

    // Filter nodes by type and isolated toggle
    let filteredNodes = graphData.nodes.filter((n) => {
      const matchesType = filterTypes.has(n.node_type)
      const degree = degreeMap.get(n.id) || 0
      const isConnected = degree > 0
      if (hideIsolated && !isConnected && !isArchTiered) return false

      const matchesSearch = !searchQuery.trim() ||
        n.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (n.file_path && n.file_path.toLowerCase().includes(searchQuery.toLowerCase()))
      return matchesType && matchesSearch
    })

    // If Neighborhood Focus is active, limit strictly to 2-hop radius around target
    if (focusNeighborhoodNodeId) {
      const neighborhood = new Set<string>([focusNeighborhoodNodeId])
      graphData.edges.forEach((e) => {
        if (e.source === focusNeighborhoodNodeId) neighborhood.add(e.target)
        if (e.target === focusNeighborhoodNodeId) neighborhood.add(e.source)
      })
      const hop1 = Array.from(neighborhood)
      graphData.edges.forEach((e) => {
        if (hop1.includes(e.source)) neighborhood.add(e.target)
        if (hop1.includes(e.target)) neighborhood.add(e.source)
      })
      filteredNodes = filteredNodes.filter((n) => neighborhood.has(n.id))
    }

    const nodeIds = new Set(filteredNodes.map((n) => n.id))
    const filteredEdges = graphData.edges.filter(
      (e) => filterEdges.has(e.edge_type) && nodeIds.has(e.source) && nodeIds.has(e.target)
    )

    // Format D3 Nodes
    const nodes: D3Node[] = filteredNodes.slice(0, 450).map((n) => {
      const cleanPath = (n.file_path || '').replace(/\\/g, '/')
      const parts = cleanPath.split('/')
      const directory = parts.length > 2 ? parts.slice(0, parts.length - 1).join('/') : ''
      const degree = degreeMap.get(n.id) || 0
      const layer = classifyNodeToLayer(n)

      const baseRadius = NODE_SIZES[n.node_type] || 7
      const sizeBoost = Math.min(degree * 0.45, 6)

      return {
        id: n.id,
        name: n.name,
        node_type: n.node_type,
        file_path: n.file_path,
        color: isArchTiered ? layer.color : (NODE_COLORS[n.node_type] || '#94a3b8'),
        radius: baseRadius + sizeBoost,
        directory,
        layer,
        degree,
      }
    })

    const limitedNodeIds = new Set(nodes.map((n) => n.id))
    const links: D3Link[] = filteredEdges
      .filter((e) => limitedNodeIds.has(e.source) && limitedNodeIds.has(e.target))
      .slice(0, 900)
      .map((e) => ({
        source: e.source,
        target: e.target,
        edge_type: e.edge_type,
      }))

    // Build Adjacency Map for quick neighbor spotlighting
    const adjacency = new Map<string, Set<string>>()
    nodes.forEach((n) => adjacency.set(n.id, new Set()))
    links.forEach((l) => {
      const s = typeof l.source === 'string' ? l.source : l.source.id
      const t = typeof l.target === 'string' ? l.target : l.target.id
      adjacency.get(s)?.add(t)
      adjacency.get(t)?.add(s)
    })

    // Defs & Patterns for High-End Grid Canvas
    const defs = svg.append('defs')

    // Subtle Dot-Matrix Grid Pattern
    const pattern = defs.append('pattern')
      .attr('id', 'graph-grid-pattern')
      .attr('width', 32)
      .attr('height', 32)
      .attr('patternUnits', 'userSpaceOnUse')

    pattern.append('circle')
      .attr('cx', 2)
      .attr('cy', 2)
      .attr('r', 1.2)
      .attr('fill', 'rgba(255, 255, 255, 0.08)')

    // Markers for directional arrows
    Object.entries(EDGE_COLORS).forEach(([type, color]) => {
      defs.append('marker')
        .attr('id', `arrow-${type}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 22)
        .attr('refY', 0)
        .attr('markerWidth', 5.5)
        .attr('markerHeight', 5.5)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-3.5L7.5,0L0,3.5')
        .attr('fill', color)
        .attr('opacity', 0.85)
    })

    // Canvas Background with Grid
    svg.append('rect')
      .attr('width', '100%')
      .attr('height', '100%')
      .attr('fill', '#070b12')

    svg.append('rect')
      .attr('width', '100%')
      .attr('height', '100%')
      .attr('fill', 'url(#graph-grid-pattern)')
      .style('pointer-events', 'none')

    // Setup Zoom container
    const g = svg.append('g')
    gRef.current = g

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.08, 6])
      .on('zoom', (event) => g.attr('transform', event.transform))

    zoomRef.current = zoom
    svg.call(zoom)

    // ── ARCHITECTURE TIERED LAYOUT ENGINE ──
    if (isArchTiered) {
      // Group nodes by Layer
      const layerGroups = new Map<string, D3Node[]>()
      Object.keys(ARCH_LAYERS).forEach((k) => layerGroups.set(k, []))
      nodes.forEach((n) => {
        layerGroups.get(n.layer.id)?.push(n)
      })

      // Active layers that contain nodes
      const activeLayers = Object.values(ARCH_LAYERS).filter(
        (l) => (layerGroups.get(l.id) || []).length > 0
      )

      const colWidth = 260
      const colGap = 60
      const startX = Math.max(60, (width - (activeLayers.length * (colWidth + colGap) - colGap)) / 2)
      const startY = 80

      const layerBoxesGroup = g.append('g').attr('class', 'arch-layer-boxes')

      // Calculate positions per layer
      activeLayers.forEach((layer, colIndex) => {
        const layerNodes = layerGroups.get(layer.id) || []
        const x = startX + colIndex * (colWidth + colGap)
        const rowHeight = 52
        const boxHeight = Math.max(220, layerNodes.length * rowHeight + 90)

        // Draw Layer Bounding Box Card
        const box = layerBoxesGroup.append('g').attr('class', 'arch-layer-card')

        box.append('rect')
          .attr('x', x - 18)
          .attr('y', startY - 35)
          .attr('width', colWidth + 36)
          .attr('height', boxHeight)
          .attr('rx', 14)
          .attr('fill', 'rgba(15, 23, 42, 0.55)')
          .attr('stroke', `${layer.color}45`)
          .attr('stroke-width', 1.2)
          .attr('filter', 'drop-shadow(0 10px 30px rgba(0, 0, 0, 0.5))')

        // Layer Header Banner
        box.append('rect')
          .attr('x', x - 18)
          .attr('y', startY - 35)
          .attr('width', colWidth + 36)
          .attr('height', 42)
          .attr('rx', 14)
          .attr('fill', `${layer.color}15`)

        box.append('text')
          .text(`${layer.icon}  ${layer.name}`)
          .attr('x', x - 4)
          .attr('y', startY - 10)
          .attr('fill', '#f8fafc')
          .attr('font-size', '12px')
          .attr('font-weight', '700')
          .attr('font-family', 'var(--font-sans)')

        box.append('text')
          .text(`${layerNodes.length} modules`)
          .attr('x', x + colWidth + 8)
          .attr('y', startY - 10)
          .attr('text-anchor', 'end')
          .attr('fill', layer.color)
          .attr('font-size', '10.5px')
          .attr('font-weight', '600')

        // Position nodes inside the layer tier
        layerNodes.forEach((nodeItem, rowIndex) => {
          nodeItem.x = x + colWidth / 2
          nodeItem.y = startY + 45 + rowIndex * rowHeight
        })
      })

      // Links with Smooth Curved Paths between Layers
      const linkGroup = g.append('g').attr('class', 'links')
      const nodeMap = new Map(nodes.map((n) => [n.id, n]))

      const link = linkGroup
        .selectAll('path')
        .data(links)
        .enter()
        .append('path')
        .attr('fill', 'none')
        .attr('stroke', (d) => EDGE_COLORS[d.edge_type] || 'rgba(148, 163, 184, 0.45)')
        .attr('stroke-width', (d) => (d.edge_type === 'imports' || d.edge_type === 'calls' ? 1.8 : 1.3))
        .attr('stroke-opacity', 0.55)
        .attr('marker-end', (d) => `url(#arrow-${d.edge_type})`)
        .attr('d', (d: any) => {
          const s = nodeMap.get(typeof d.source === 'string' ? d.source : d.source.id)
          const t = nodeMap.get(typeof d.target === 'string' ? d.target : d.target.id)
          if (!s || !t || s.x === undefined || s.y === undefined || t.x === undefined || t.y === undefined) return ''
          
          const isLeftToRight = t.x >= s.x
          const startX = isLeftToRight ? s.x + 95 : s.x - 95
          const startY = s.y
          const endX = isLeftToRight ? t.x - 95 : t.x + 95
          const endY = t.y
          const dx = endX - startX
          const cx1 = startX + dx * 0.45
          const cy1 = startY
          const cx2 = startX + dx * 0.55
          const cy2 = endY
          return `M ${startX} ${startY} C ${cx1} ${cy1} ${cx2} ${cy2} ${endX} ${endY}`
        })

      // Node Items
      const nodeGroup = g.append('g').attr('class', 'nodes')
      const node = nodeGroup
        .selectAll('g')
        .data(nodes)
        .enter()
        .append('g')
        .attr('class', 'node-item')
        .attr('transform', (d) => `translate(${d.x},${d.y})`)
        .style('cursor', 'pointer')

      // Node Pill Box
      node
        .append('rect')
        .attr('x', -95)
        .attr('y', -16)
        .attr('width', 190)
        .attr('height', 32)
        .attr('rx', 8)
        .attr('fill', 'rgba(10, 15, 28, 0.92)')
        .attr('stroke', (d) => d.color)
        .attr('stroke-width', 1.3)
        .attr('filter', 'drop-shadow(0 4px 12px rgba(0, 0, 0, 0.4))')

      // Icon & Name inside Node Card
      node
        .append('text')
        .attr('x', -82)
        .attr('y', 4)
        .text((d) => NODE_ICONS[d.node_type] || '📄')
        .attr('font-size', '12px')

      node
        .append('text')
        .attr('x', -62)
        .attr('y', 4)
        .text((d) => (d.name.length > 18 ? d.name.slice(0, 16) + '…' : d.name))
        .attr('fill', '#f8fafc')
        .attr('font-size', '10.5px')
        .attr('font-weight', '600')
        .attr('font-family', 'var(--font-mono)')

      // Interaction: Hover highlights connections while keeping all other nodes comfortably visible
      node
        .on('click', (_event, d) => {
          const original = graphData.nodes.find((n) => n.id === d.id)
          if (original) setSelectedNode(original)
        })
        .on('mouseover', function (_event, d) {
          setHoveredNode(d)
          const connected = adjacency.get(d.id) || new Set()

          // Keep other nodes comfortably visible at 0.65 opacity instead of hiding them
          node.style('opacity', (n) => (n.id === d.id || connected.has(n.id) ? 1 : 0.65))
          
          // Highlight hovered node
          d3.select(this)
            .select('rect')
            .attr('stroke', '#ffffff')
            .attr('stroke-width', 2.2)
            .attr('filter', `drop-shadow(0 0 16px ${d.color})`)

          // Highlight connected neighbor nodes
          node.filter((n) => connected.has(n.id))
            .select('rect')
            .attr('stroke', '#ffffff')
            .attr('stroke-width', 1.8)

          // Highlight connected links
          link
            .attr('stroke-opacity', (l: any) => {
              const s = l.source.id || l.source
              const t = l.target.id || l.target
              return s === d.id || t === d.id ? 1 : 0.18
            })
            .attr('stroke-width', (l: any) => {
              const s = l.source.id || l.source
              const t = l.target.id || l.target
              return s === d.id || t === d.id ? 2.6 : 1.0
            })
        })
        .on('mouseout', function () {
          setHoveredNode(null)
          node.style('opacity', 1)
          node.select('rect')
            .attr('stroke', (d: any) => d.color)
            .attr('stroke-width', 1.3)
            .attr('filter', 'drop-shadow(0 4px 12px rgba(0, 0, 0, 0.4))')

          link
            .attr('stroke-opacity', 0.55)
            .attr('stroke-width', (d) => (d.edge_type === 'imports' || d.edge_type === 'calls' ? 1.8 : 1.3))
        })

      return
    }

    // ── PHYSICS FORCE GRAPH ENGINE (ALL RELATIONS / CALL GRAPH / API) ──
    const directoryMap = new Map<string, { x: number; y: number }>()
    const uniqueDirs = Array.from(new Set(nodes.map((n) => n.directory || 'root')))
    uniqueDirs.forEach((dir, idx) => {
      const angle = (idx / Math.max(1, uniqueDirs.length)) * 2 * Math.PI
      const radius = Math.min(width, height) * spacingConfig.clusterRadiusMult
      directoryMap.set(dir, {
        x: width / 2 + radius * Math.cos(angle),
        y: height / 2 + radius * Math.sin(angle),
      })
    })

    const simulation = d3.forceSimulation<D3Node>(nodes)
      .force(
        'link',
        d3.forceLink<D3Node, D3Link>(links)
          .id((d) => d.id)
          .distance((d) => (
            d.edge_type === 'contains'
              ? spacingConfig.containsDist
              : d.edge_type === 'calls'
              ? spacingConfig.callsDist
              : spacingConfig.otherDist
          ))
          .strength((d) => (d.edge_type === 'contains' ? 0.65 : 0.35))
      )
      .force('charge', d3.forceManyBody().strength(spacingConfig.charge).distanceMax(550))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius((d: any) => d.radius + spacingConfig.collideRadius).iterations(3))
      .force('cluster', (alpha) => {
        nodes.forEach((n) => {
          const target = directoryMap.get(n.directory || 'root')
          if (target && n.x && n.y) {
            n.vx = (n.vx || 0) + (target.x - n.x) * alpha * 0.035
            n.vy = (n.vy || 0) + (target.y - n.y) * alpha * 0.035
          }
        })
      })

    simulationRef.current = simulation

    // Link Elements
    const linkGroup = g.append('g').attr('class', 'links')
    const link = linkGroup
      .selectAll('line')
      .data(links)
      .enter()
      .append('line')
      .attr('stroke', (d) => EDGE_COLORS[d.edge_type] || 'rgba(148, 163, 184, 0.35)')
      .attr('stroke-width', (d) => (d.edge_type === 'calls' ? 1.6 : d.edge_type === 'imports' ? 1.4 : 1.1))
      .attr('stroke-dasharray', (d) => (d.edge_type === 'contains' ? '3,3' : 'none'))
      .attr('stroke-opacity', 0.45)
      .attr('marker-end', (d) => `url(#arrow-${d.edge_type})`)

    // Node Elements
    const nodeGroup = g.append('g').attr('class', 'nodes')
    const node = nodeGroup
      .selectAll('g')
      .data(nodes)
      .enter()
      .append('g')
      .attr('class', 'node-item')
      .style('cursor', 'pointer')

    // Outer Halo Ring for Major Nodes
    node
      .filter((d) => d.radius >= 11 || d.node_type === 'api' || d.node_type === 'file' || d.node_type === 'class')
      .append('circle')
      .attr('r', (d) => d.radius + 4)
      .attr('fill', 'none')
      .attr('stroke', (d) => d.color)
      .attr('stroke-width', 1.2)
      .attr('stroke-opacity', 0.25)

    // Main Node Circle
    const circle = node
      .append('circle')
      .attr('r', (d) => d.radius)
      .attr('fill', (d) => d.color)
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 1.4)
      .attr('stroke-opacity', 0.75)

    // Node Labels with Background Pills for Ultimate Legibility
    const labelGroup = g.append('g').attr('class', 'labels')
    const label = labelGroup
      .selectAll('g')
      .data(nodes.filter((n) => n.radius >= 8 || n.node_type === 'file' || n.node_type === 'api' || n.node_type === 'class'))
      .enter()
      .append('g')
      .attr('class', 'graph-node-label-group')
      .style('pointer-events', 'none')

    label
      .append('rect')
      .attr('rx', 4)
      .attr('ry', 4)
      .attr('fill', 'rgba(10, 15, 28, 0.82)')
      .attr('stroke', (d) => `${d.color}40`)
      .attr('stroke-width', 0.8)
      .attr('x', (d) => d.radius + 4)
      .attr('y', -8.5)
      .attr('height', 17)
      .attr('width', (d) => {
        const text = d.name.length > 22 ? d.name.slice(0, 20) + '…' : d.name
        return text.length * 6.6 + 10
      })

    label
      .append('text')
      .text((d) => (d.name.length > 22 ? d.name.slice(0, 20) + '…' : d.name))
      .attr('dx', (d) => d.radius + 9)
      .attr('dy', 4)
      .attr('fill', '#f8fafc')
      .attr('font-size', '10px')
      .attr('font-weight', '500')
      .attr('font-family', 'var(--font-mono)')

    // Interactivity: Click & Hover
    node
      .on('click', (_event, d) => {
        const original = graphData.nodes.find((n) => n.id === d.id)
        if (original) setSelectedNode(original)
      })
      .on('mouseover', function (_event, d) {
        setHoveredNode(d)
        const connected = adjacency.get(d.id) || new Set()

        // Keep other nodes comfortably visible at 0.65 opacity
        node.style('opacity', (n) => (n.id === d.id || connected.has(n.id) ? 1 : 0.65))
        d3.select(this)
          .select('circle')
          .attr('stroke', '#ffffff')
          .attr('stroke-width', 2.8)
          .attr('filter', `drop-shadow(0 0 14px ${d.color})`)

        link
          .attr('stroke-opacity', (l: any) => {
            const s = l.source.id || l.source
            const t = l.target.id || l.target
            return s === d.id || t === d.id ? 1 : 0.15
          })
          .attr('stroke-width', (l: any) => {
            const s = l.source.id || l.source
            const t = l.target.id || l.target
            return s === d.id || t === d.id ? 2.8 : 0.9
          })

        label.style('opacity', (n) => (n.id === d.id || connected.has(n.id) ? 1 : 0.65))
      })
      .on('mouseout', function () {
        setHoveredNode(null)
        node.style('opacity', 1)
        d3.select(this)
          .select('circle')
          .attr('stroke', '#ffffff')
          .attr('stroke-width', 1.4)
          .attr('filter', null)

        link
          .attr('stroke-opacity', 0.45)
          .attr('stroke-width', (d) => (d.edge_type === 'calls' ? 1.6 : d.edge_type === 'imports' ? 1.4 : 1.1))

        label.style('opacity', 1)
      })
      .call(
        d3.drag<SVGGElement, D3Node>()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart()
            d.fx = d.x
            d.fy = d.y
          })
          .on('drag', (event, d) => {
            d.fx = event.x
            d.fy = event.y
          })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0)
            d.fx = null
            d.fy = null
          })
      )

    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y)

      node.attr('transform', (d) => `translate(${d.x},${d.y})`)
      label.attr('transform', (d) => `translate(${d.x},${d.y})`)
    })

    return () => {
      simulation.stop()
    }
  }, [graphData, filterTypes, filterEdges, searchQuery, hideIsolated, focusNeighborhoodNodeId, spacingConfig, isFullscreen, viewPreset, archLayoutMode])

  // Filter toggle helpers
  const toggleNodeType = (type: NodeType) => {
    setFilterTypes((prev) => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  const toggleEdgeType = (type: EdgeType) => {
    setFilterEdges((prev) => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  const handleZoom = (direction: 'in' | 'out' | 'reset') => {
    if (!svgRef.current || !zoomRef.current) return
    const svg = d3.select(svgRef.current)
    if (direction === 'in') {
      svg.transition().duration(300).call(zoomRef.current.scaleBy, 1.35)
    } else if (direction === 'out') {
      svg.transition().duration(300).call(zoomRef.current.scaleBy, 0.65)
    } else {
      svg.transition().duration(400).call(zoomRef.current.transform, d3.zoomIdentity)
    }
  }

  const handleAnalyzeComponent = (node: GraphNode) => {
    navigate('/analysis', {
      state: {
        repoId: selectedRepo,
        targetFunction: node.name,
        targetFile: node.file_path,
        initialQuery: `Analyze changes to ${node.name} in ${node.file_path || ''}`,
      },
    })
  }

  return (
    <>
      {/* Top Header (Hidden in Fullscreen) */}
      {!isFullscreen && (
        <div className="page-header" style={{ marginBottom: 16 }}>
          <div>
            <h2>Graph Explorer</h2>
            <p>Multi-relational knowledge graph mapping AST symbols, call chains, imports, and API flows</p>
          </div>
        </div>
      )}

      {/* Main Container (Regular or Fullscreen Overlay) */}
      <div
        style={{
          position: isFullscreen ? 'fixed' : 'relative',
          inset: isFullscreen ? 0 : 'auto',
          zIndex: isFullscreen ? 9999 : 'auto',
          background: isFullscreen ? '#060910' : 'transparent',
          padding: isFullscreen ? 16 : 0,
          display: 'flex',
          flexDirection: 'column',
          height: isFullscreen ? '100vh' : 'auto',
          overflow: isFullscreen ? 'hidden' : 'visible',
        }}
      >
        {/* Top Control Bar */}
        <div
          className="glass-card"
          style={{
            padding: '10px 14px',
            marginBottom: 12,
            display: 'flex',
            gap: 10,
            alignItems: 'center',
            flexWrap: 'wrap',
            background: isFullscreen ? 'rgba(15, 23, 42, 0.95)' : undefined,
          }}
        >
          {/* Repo Selector */}
          <select
            className="form-input"
            style={{ width: 190, height: 34, fontSize: '0.8rem' }}
            value={selectedRepo || ''}
            onChange={(e) => setSelectedRepo(Number(e.target.value))}
          >
            <option value="">Select repository...</option>
            {repos.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} ({r.file_count} files)
              </option>
            ))}
          </select>

          {/* View Mode Presets */}
          <div style={{ display: 'flex', background: 'rgba(255, 255, 255, 0.04)', borderRadius: 'var(--radius-md)', padding: 2 }}>
            <button
              className={`btn btn-sm ${viewPreset === 'all' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: '0.74rem', height: 30 }}
              onClick={() => handlePresetChange('all')}
            >
              All Relations
            </button>
            <button
              className={`btn btn-sm ${viewPreset === 'calls' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: '0.74rem', height: 30 }}
              onClick={() => handlePresetChange('calls')}
            >
              ⚡ Call Graph
            </button>
            <button
              className={`btn btn-sm ${viewPreset === 'architecture' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: '0.74rem', height: 30 }}
              onClick={() => handlePresetChange('architecture')}
            >
              📁 Architecture
            </button>
            <button
              className={`btn btn-sm ${viewPreset === 'api' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: '0.74rem', height: 30 }}
              onClick={() => handlePresetChange('api')}
            >
              🌐 API Map
            </button>
          </div>

          {/* Architecture Layout Options (When in Architecture preset) */}
          {viewPreset === 'architecture' ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'rgba(56, 189, 248, 0.1)', border: '1px solid rgba(56, 189, 248, 0.3)', borderRadius: 'var(--radius-md)', padding: '2px 6px' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--accent-blue-light)', fontWeight: 700, paddingRight: 4 }}>
                Layout:
              </span>
              <button
                className={`btn btn-sm ${archLayoutMode === 'tiered' ? 'btn-primary' : 'btn-ghost'}`}
                style={{ fontSize: '0.7rem', height: 26, padding: '0 8px', gap: 4 }}
                onClick={() => setArchLayoutMode('tiered')}
              >
                <Layers size={12} /> Tiered Layers
              </button>
              <button
                className={`btn btn-sm ${archLayoutMode === 'clustered' ? 'btn-primary' : 'btn-ghost'}`}
                style={{ fontSize: '0.7rem', height: 26, padding: '0 8px', gap: 4 }}
                onClick={() => setArchLayoutMode('clustered')}
              >
                <LayoutGrid size={12} /> Cluster Graph
              </button>
            </div>
          ) : (
            /* Node Spacing Selector for Force Graphs */
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'rgba(255, 255, 255, 0.04)', borderRadius: 'var(--radius-md)', padding: '2px 6px' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, paddingRight: 4 }}>
                Spacing:
              </span>
              {(['compact', 'balanced', 'spacious'] as SpacingMode[]).map((mode) => (
                <button
                  key={mode}
                  className={`btn btn-sm ${spacingMode === mode ? 'btn-primary' : 'btn-ghost'}`}
                  style={{ fontSize: '0.7rem', height: 26, padding: '0 7px', textTransform: 'capitalize' }}
                  onClick={() => setSpacingMode(mode)}
                >
                  {mode}
                </button>
              ))}
            </div>
          )}

          {/* Search Input */}
          <div style={{ position: 'relative', width: 200 }}>
            <Search size={13} style={{ position: 'absolute', left: 9, top: 10, color: 'var(--text-muted)' }} />
            <input
              type="text"
              className="form-input"
              style={{ paddingLeft: 28, fontSize: '0.78rem', height: 32 }}
              placeholder="Search symbols..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                style={{ position: 'absolute', right: 8, top: 7, background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                ✕
              </button>
            )}
          </div>

          {/* Hide Isolated Nodes Toggle (when not in tiered architecture) */}
          {viewPreset !== 'architecture' && (
            <button
              className={`btn btn-sm ${hideIsolated ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: '0.74rem', height: 32, gap: 5 }}
              onClick={() => setHideIsolated(!hideIsolated)}
              title="Toggle visibility of orphan nodes with 0 connections"
            >
              {hideIsolated ? <EyeOff size={13} /> : <Eye size={13} />}
              {hideIsolated ? 'Isolated Hidden' : 'Show Isolated'}
            </button>
          )}

          {/* Reset Neighborhood Focus */}
          {focusNeighborhoodNodeId && (
            <button
              className="btn btn-sm btn-ghost"
              style={{ fontSize: '0.74rem', height: 32, color: 'var(--accent-amber)', borderColor: 'var(--accent-amber)' }}
              onClick={() => setFocusNeighborhoodNodeId(null)}
            >
              <Crosshair size={13} /> Clear Focus
            </button>
          )}

          {/* Zoom & Fullscreen Controls */}
          <div style={{ display: 'flex', gap: 4, marginLeft: 'auto', alignItems: 'center' }}>
            <button className="btn btn-ghost btn-sm" onClick={() => handleZoom('in')} title="Zoom In" style={{ height: 32, width: 32, padding: 0 }}>
              <ZoomIn size={15} />
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => handleZoom('out')} title="Zoom Out" style={{ height: 32, width: 32, padding: 0 }}>
              <ZoomOut size={15} />
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => handleZoom('reset')} title="Reset View" style={{ height: 32, width: 32, padding: 0 }}>
              <Compass size={15} />
            </button>
            <div style={{ width: 1, height: 18, background: 'var(--border-primary)', margin: '0 2px' }} />
            {/* Fullscreen Toggle Button */}
            <button
              className={`btn btn-sm ${isFullscreen ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setIsFullscreen(!isFullscreen)}
              title={isFullscreen ? 'Exit Fullscreen (ESC)' : 'Expand Fullscreen'}
              style={{
                height: 32,
                gap: 5,
                fontSize: '0.74rem',
                fontWeight: 600,
                color: isFullscreen ? '#ffffff' : 'var(--accent-teal)',
                borderColor: isFullscreen ? undefined : 'var(--accent-teal)',
              }}
            >
              {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
              {isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
            </button>
          </div>
        </div>

        {/* Filter Pills Bar */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          {/* Node Filters */}
          <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-muted)', marginRight: 2 }}>
              Nodes:
            </span>
            {(Object.keys(NODE_COLORS) as NodeType[]).map((type) => {
              const active = filterTypes.has(type)
              return (
                <button
                  key={type}
                  className={`btn btn-sm ${active ? '' : 'btn-ghost'}`}
                  style={{
                    background: active ? `${NODE_COLORS[type]}22` : 'rgba(255, 255, 255, 0.02)',
                    color: active ? NODE_COLORS[type] : 'var(--text-muted)',
                    borderColor: active ? `${NODE_COLORS[type]}50` : 'var(--border-primary)',
                    fontSize: '0.69rem',
                    padding: '1px 7px',
                    height: 24,
                    borderRadius: 12,
                  }}
                  onClick={() => toggleNodeType(type)}
                >
                  <span style={{ marginRight: 3, fontSize: '0.7rem' }}>{NODE_ICONS[type]}</span>
                  {type}
                </button>
              )
            })}
          </div>

          <div style={{ width: 1, height: 16, background: 'var(--border-primary)' }} />

          {/* Edge Filters */}
          <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-muted)', marginRight: 2 }}>
              Edges:
            </span>
            {(Object.keys(EDGE_COLORS) as EdgeType[]).map((type) => {
              const active = filterEdges.has(type)
              return (
                <button
                  key={type}
                  className={`btn btn-sm ${active ? '' : 'btn-ghost'}`}
                  style={{
                    background: active ? `${EDGE_COLORS[type]}22` : 'rgba(255, 255, 255, 0.02)',
                    color: active ? EDGE_COLORS[type] : 'var(--text-muted)',
                    borderColor: active ? `${EDGE_COLORS[type]}50` : 'var(--border-primary)',
                    fontSize: '0.69rem',
                    padding: '1px 7px',
                    height: 24,
                    borderRadius: 12,
                  }}
                  onClick={() => toggleEdgeType(type)}
                >
                  <span
                    style={{
                      width: 9,
                      height: 2.5,
                      background: EDGE_COLORS[type],
                      display: 'inline-block',
                      marginRight: 4,
                      borderRadius: 1,
                    }}
                  />
                  {type}
                </button>
              )
            })}
          </div>
        </div>

        {/* Main Canvas & Inspector Layout */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: selectedNode ? '1fr 370px' : '1fr',
            gap: 16,
            flex: isFullscreen ? 1 : 'none',
            height: isFullscreen ? 'calc(100vh - 120px)' : '680px',
            minHeight: 0,
          }}
        >
          <div
            className="graph-container"
            ref={containerRef}
            style={{
              position: 'relative',
              height: '100%',
              borderRadius: 'var(--radius-lg)',
              overflow: 'hidden',
              border: '1px solid var(--border-primary)',
              boxShadow: 'inset 0 0 40px rgba(0, 0, 0, 0.6)',
            }}
          >
            {loading ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 12 }}>
                <div className="spinner" />
                <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Calculating graph layout & relationships...</span>
              </div>
            ) : !graphData ? (
              <div className="empty-state" style={{ height: '100%' }}>
                <Network size={44} style={{ color: 'var(--accent-blue)', opacity: 0.8 }} />
                <h3>No graph data available</h3>
                <p>Select a repository to explore its architectural knowledge graph.</p>
              </div>
            ) : (
              <>
                <svg
                  ref={svgRef}
                  style={{ width: '100%', height: '100%', display: 'block' }}
                />

                {/* Floating Hover Tooltip */}
                <AnimatePresence>
                  {hoveredNode && (
                    <motion.div
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      style={{
                        position: 'absolute',
                        top: 14,
                        left: 14,
                        background: 'rgba(10, 15, 28, 0.94)',
                        backdropFilter: 'blur(12px)',
                        border: `1px solid ${hoveredNode.color}70`,
                        borderRadius: 'var(--radius-md)',
                        padding: '9px 14px',
                        fontSize: '0.78rem',
                        pointerEvents: 'none',
                        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.6), 0 0 15px rgba(0,0,0,0.4)',
                        zIndex: 10,
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: '0.85rem' }}>{NODE_ICONS[hoveredNode.node_type]}</span>
                        <span style={{ fontWeight: 700, color: '#f8fafc' }}>{hoveredNode.name}</span>
                        <span style={{ fontSize: '0.68rem', color: hoveredNode.color, textTransform: 'uppercase', fontWeight: 700, marginLeft: 2 }}>
                          [{hoveredNode.node_type}]
                        </span>
                      </div>
                      <div style={{ fontSize: '0.72rem', color: hoveredNode.layer.color, marginTop: 2, fontWeight: 600 }}>
                        Layer: {hoveredNode.layer.icon} {hoveredNode.layer.name}
                      </div>
                      {hoveredNode.file_path && (
                        <div className="mono" style={{ color: '#94a3b8', fontSize: '0.7rem', marginTop: 3 }}>
                          {hoveredNode.file_path.replace(/\\/g, '/')}
                        </div>
                      )}
                      <div style={{ marginTop: 4, fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                        {hoveredNode.degree} active connections · Click to inspect
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Bottom Status Indicator */}
                <div
                  style={{
                    position: 'absolute',
                    bottom: 12,
                    right: 14,
                    background: 'rgba(10, 15, 28, 0.85)',
                    backdropFilter: 'blur(8px)',
                    border: '1px solid var(--border-primary)',
                    borderRadius: 'var(--radius-md)',
                    padding: '5px 12px',
                    fontSize: '0.73rem',
                    color: 'var(--text-muted)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  <span>{graphData.nodes.length} nodes · {graphData.edges.length} edges</span>
                  <span style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--accent-teal)' }} />
                  <span style={{ textTransform: 'capitalize' }}>
                    {viewPreset === 'architecture' ? `Architecture: ${archLayoutMode}` : `Spacing: ${spacingMode}`}
                  </span>
                </div>
              </>
            )}
          </div>

          {/* Interactive Node Inspector Panel */}
          <AnimatePresence>
            {selectedNode && (
              <motion.div
                className="glass-card"
                style={{
                  padding: 20,
                  height: '100%',
                  overflowY: 'auto',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 16,
                  background: isFullscreen ? 'rgba(15, 23, 42, 0.96)' : undefined,
                  border: '1px solid var(--border-primary)',
                }}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
              >
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                  <div>
                    <span
                      style={{
                        fontSize: '0.68rem',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        color: NODE_COLORS[selectedNode.node_type],
                        letterSpacing: '0.08em',
                        background: `${NODE_COLORS[selectedNode.node_type]}20`,
                        padding: '2px 8px',
                        borderRadius: 4,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                      }}
                    >
                      <span>{NODE_ICONS[selectedNode.node_type]}</span>
                      {selectedNode.node_type}
                    </span>
                    <h3 style={{ fontWeight: 700, fontSize: '1.1rem', marginTop: 6, wordBreak: 'break-all' }}>
                      {selectedNode.name}
                    </h3>
                    <div style={{ fontSize: '0.75rem', color: 'var(--accent-blue-light)', marginTop: 4, fontWeight: 500 }}>
                      {classifyNodeToLayer(selectedNode).icon} {classifyNodeToLayer(selectedNode).name}
                    </div>
                  </div>
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => setSelectedNode(null)}
                    style={{ color: 'var(--text-muted)', padding: '4px 8px' }}
                  >
                    ✕
                  </button>
                </div>

                {/* Quick Actions */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <button
                    className="btn btn-sm btn-ghost"
                    style={{ fontSize: '0.74rem', gap: 4, borderColor: 'var(--border-primary)' }}
                    onClick={() => setFocusNeighborhoodNodeId(selectedNode.id)}
                  >
                    <Crosshair size={13} style={{ color: 'var(--accent-teal)' }} />
                    Focus Subgraph
                  </button>
                  <button
                    className="btn btn-sm btn-primary"
                    style={{ fontSize: '0.74rem', gap: 4 }}
                    onClick={() => handleAnalyzeComponent(selectedNode)}
                  >
                    <Sparkles size={13} />
                    Analyze Impact
                  </button>
                </div>

                {/* Details List */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, fontSize: '0.8rem' }}>
                  {selectedNode.file_path && (
                    <div>
                      <div className="form-label" style={{ marginBottom: 2 }}>File Path</div>
                      <div className="mono" style={{ color: 'var(--accent-blue-light)', fontSize: '0.73rem', wordBreak: 'break-all' }}>
                        {selectedNode.file_path.replace(/\\/g, '/')}
                      </div>
                    </div>
                  )}

                  {selectedNode.start_line && (
                    <div>
                      <div className="form-label" style={{ marginBottom: 2 }}>Line Range</div>
                      <div>L{selectedNode.start_line} – L{selectedNode.end_line}</div>
                    </div>
                  )}

                  {/* Callers / Incoming Connections */}
                  <div>
                    <div className="form-label" style={{ marginBottom: 4 }}>
                      Callers & Consumers ({(nodeConnections.callers.get(selectedNode.id) || []).length})
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 140, overflowY: 'auto' }}>
                      {(nodeConnections.callers.get(selectedNode.id) || []).length === 0 ? (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>No direct callers found</span>
                      ) : (
                        nodeConnections.callers.get(selectedNode.id)?.map((caller, idx) => (
                          <div
                            key={idx}
                            onClick={() => setSelectedNode(caller)}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 6,
                              padding: '5px 8px',
                              background: 'rgba(255, 255, 255, 0.03)',
                              borderRadius: 'var(--radius-sm)',
                              cursor: 'pointer',
                              fontSize: '0.74rem',
                            }}
                            className="hover-card"
                          >
                            <span style={{ fontSize: '0.75rem' }}>{NODE_ICONS[caller.node_type]}</span>
                            <span style={{ fontWeight: 600, color: '#e2e8f0', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {caller.name}
                            </span>
                            <ArrowRight size={12} style={{ color: 'var(--text-muted)' }} />
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Callees / Outgoing Connections */}
                  <div>
                    <div className="form-label" style={{ marginBottom: 4 }}>
                      Dependencies & Calls ({(nodeConnections.callees.get(selectedNode.id) || []).length})
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 140, overflowY: 'auto' }}>
                      {(nodeConnections.callees.get(selectedNode.id) || []).length === 0 ? (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>No outgoing calls</span>
                      ) : (
                        nodeConnections.callees.get(selectedNode.id)?.map((callee, idx) => (
                          <div
                            key={idx}
                            onClick={() => setSelectedNode(callee)}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 6,
                              padding: '5px 8px',
                              background: 'rgba(255, 255, 255, 0.03)',
                              borderRadius: 'var(--radius-sm)',
                              cursor: 'pointer',
                              fontSize: '0.74rem',
                            }}
                            className="hover-card"
                          >
                            <span style={{ fontSize: '0.75rem' }}>{NODE_ICONS[callee.node_type]}</span>
                            <span style={{ fontWeight: 600, color: '#e2e8f0', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {callee.name}
                            </span>
                            <ArrowRight size={12} style={{ color: 'var(--text-muted)' }} />
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Metadata */}
                  {selectedNode.metadata && Object.keys(selectedNode.metadata).length > 0 && (
                    <div>
                      <div className="form-label" style={{ marginBottom: 4 }}>Attributes</div>
                      {Object.entries(selectedNode.metadata).map(([k, v]) => (
                        v && (
                          <div
                            key={k}
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              padding: '4px 0',
                              borderBottom: '1px solid var(--border-primary)',
                              fontSize: '0.72rem',
                            }}
                          >
                            <span style={{ color: 'var(--text-muted)' }}>{k}</span>
                            <span
                              style={{
                                color: 'var(--text-secondary)',
                                maxWidth: 160,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                            </span>
                          </div>
                        )
                      ))}
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </>
  )
}
