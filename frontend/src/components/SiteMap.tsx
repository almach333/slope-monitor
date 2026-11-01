/** Shared Leaflet pieces: dark basemap tiles and the placeholder site centre. */

import { useEffect, useRef } from 'react'
import { TileLayer, useMap } from 'react-leaflet'

import type { NodeOut } from '../api/types'

/** Placeholder site centre (UQ St Lucia) used when there are no nodes yet — not a real mine. */
export const DEFAULT_CENTRE: [number, number] = [-27.4975, 153.0137]

/**
 * OpenStreetMap standard tiles, darkened with a CSS filter (.dark-tiles in
 * index.css) to match the theme. OSM's tile usage policy allows light use
 * like this prototype, with attribution; a production system should use a
 * paid/self-hosted tile service. (CARTO's dark tiles now need an API key.)
 * Tiles need an internet connection; without one, the markers still work on
 * a blank background.
 */
export function DarkTiles() {
  return (
    <TileLayer
      url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      maxZoom={19}
      className="dark-tiles"
      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    />
  )
}

/** Current position of a node: latest GPS fix, falling back to its reference position. */
export function nodePosition(node: NodeOut): [number, number] | null {
  const lat = node.latest?.values.lat ?? node.ref_lat
  const lon = node.latest?.values.lon ?? node.ref_lon
  return lat != null && lon != null ? [lat, lon] : null
}

/** Zoom the map to fit the given points once (site scale, not world scale). */
export function FitBounds({ points }: { points: [number, number][] }) {
  const map = useMap()
  const done = useRef(false)
  useEffect(() => {
    if (done.current || points.length === 0) return
    done.current = true
    if (points.length === 1) map.setView(points[0], 17)
    else map.fitBounds(points, { padding: [70, 70], maxZoom: 18 })
  }, [map, points])
  return null
}
