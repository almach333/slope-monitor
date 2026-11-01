/** New device: register a node, place its reference position on a map, set its alert rules. */

import { type FormEvent, useEffect, useMemo, useState } from 'react'
import { CircleMarker, MapContainer, useMapEvents } from 'react-leaflet'
import { Link, useNavigate } from 'react-router'

import { useAlertDefaults, useCreateNode, useNodes } from '../api/queries'
import type { NodeCreated } from '../api/types'
import { CopyIcon } from '../components/Icons'
import { Modal } from '../components/Modal'
import { NewRulesEditor, type RuleDraft, draftFromRule, draftToInput, validateDraft } from '../components/RulesEditor'
import { DEFAULT_CENTRE, DarkTiles, nodePosition } from '../components/SiteMap'
import { Button, LoadingState, PageHeader, Panel, inputClass } from '../components/ui'

function ClickToPlace({ onPick }: { onPick: (lat: number, lon: number) => void }) {
  useMapEvents({ click: (e) => onPick(e.latlng.lat, e.latlng.lng) })
  return null
}

function ApiKeyDialog({ created, onDone }: { created: NodeCreated | null; onDone: () => void }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    if (!created) return
    try {
      await navigator.clipboard.writeText(created.api_key)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }
  return (
    <Modal open={created !== null} onClose={onDone} title="Device registered">
      {created && (
        <>
          <p className="text-sm text-slate-300">
            <span className="font-semibold text-white">{created.node.name}</span> was registered. Configure the node (or
            its LoRa bridge) to send this API key in the <span className="num">X-API-Key</span> header.
          </p>
          <div className="mt-4 flex items-center gap-2">
            <code className="num flex-1 overflow-x-auto rounded-lg border border-line bg-ink px-3 py-2 text-sm whitespace-nowrap text-accent">
              {created.api_key}
            </code>
            <Button onClick={copy}>
              <CopyIcon width={16} height={16} /> {copied ? 'Copied' : 'Copy'}
            </Button>
          </div>
          <div className="mt-4 rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn">
            This key will not be shown again. Only a hash of it is stored. If it is lost, a new key must be issued.
          </div>
          <div className="mt-5 flex justify-end">
            <Button variant="primary" onClick={onDone}>
              I’ve saved the key — open device
            </Button>
          </div>
        </>
      )}
    </Modal>
  )
}

export function NewDevicePage() {
  const navigate = useNavigate()
  const defaults = useAlertDefaults()
  const nodes = useNodes()
  const create = useCreateNode()

  const [name, setName] = useState('')
  const [devEui, setDevEui] = useState('')
  const [description, setDescription] = useState('')
  const [lat, setLat] = useState('')
  const [lon, setLon] = useState('')
  const [intervalS, setIntervalS] = useState('60')
  const [drafts, setDrafts] = useState<RuleDraft[] | null>(null)
  const [created, setCreated] = useState<NodeCreated | null>(null)
  const [submitted, setSubmitted] = useState(false)

  // Pre-fill the rules editor with the default rules (battery, acceleration, slope angle, tilt).
  useEffect(() => {
    if (defaults.data && drafts === null) setDrafts(defaults.data.rules.map(draftFromRule))
  }, [defaults.data, drafts])

  const centre = useMemo(() => {
    const pts = (nodes.data ?? []).map(nodePosition).filter((p): p is [number, number] => p !== null)
    if (!pts.length) return DEFAULT_CENTRE
    return [pts.reduce((s, p) => s + p[0], 0) / pts.length, pts.reduce((s, p) => s + p[1], 0) / pts.length] as [number, number]
  }, [nodes.data])

  const errors: Record<string, string> = {}
  if (!name.trim()) errors.name = 'Name is required'
  if (!/^[0-9a-fA-F]{16}$/.test(devEui)) errors.devEui = 'dev_eui must be 16 hexadecimal characters'
  if (lat && (Number.isNaN(Number(lat)) || Math.abs(Number(lat)) > 90)) errors.lat = 'Latitude must be between -90 and 90'
  if (lon && (Number.isNaN(Number(lon)) || Math.abs(Number(lon)) > 180)) errors.lon = 'Longitude must be between -180 and 180'
  if (!Number.isInteger(Number(intervalS)) || Number(intervalS) < 5) errors.interval = 'Interval must be a whole number ≥ 5 seconds'
  const ruleErrors = (drafts ?? []).map((d) => validateDraft(d)).filter(Boolean)
  const valid = Object.keys(errors).length === 0 && ruleErrors.length === 0

  const submit = (e: FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
    if (!valid) return
    create.mutate(
      {
        name: name.trim(),
        dev_eui: devEui.toLowerCase(),
        description: description.trim(),
        ref_lat: lat ? Number(lat) : null,
        ref_lon: lon ? Number(lon) : null,
        expected_interval_s: Number(intervalS),
        rules: (drafts ?? []).map(draftToInput),
      },
      { onSuccess: setCreated },
    )
  }

  const fieldError = (key: string) =>
    submitted && errors[key] ? <div className="mt-1 text-xs text-crit">{errors[key]}</div> : null
  const pos: [number, number] | null = lat && lon && !errors.lat && !errors.lon ? [Number(lat), Number(lon)] : null

  return (
    <>
      <div className="mb-2 text-sm">
        <Link to="/devices" className="text-muted hover:text-white">
          ← Devices
        </Link>
      </div>
      <PageHeader eyebrow="Register a node" title="New device" />

      <form onSubmit={submit} noValidate className="space-y-6">
        <div className="grid gap-6 xl:grid-cols-2">
          <Panel title="Device">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="text-sm text-slate-300">
                Name
                <input className={`${inputClass} mt-1`} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. N7 East bench" />
                {fieldError('name')}
              </label>
              <label className="text-sm text-slate-300">
                dev_eui
                <input
                  className={`${inputClass} num mt-1`}
                  value={devEui}
                  maxLength={16}
                  onChange={(e) => setDevEui(e.target.value.trim())}
                  placeholder="70b3d57ed0000007"
                />
                {fieldError('devEui')}
              </label>
              <label className="text-sm text-slate-300 sm:col-span-2">
                Description
                <textarea rows={2} className={`${inputClass} mt-1`} value={description} onChange={(e) => setDescription(e.target.value)} />
              </label>
              <label className="text-sm text-slate-300">
                Reference latitude
                <input className={`${inputClass} num mt-1`} value={lat} onChange={(e) => setLat(e.target.value)} placeholder="click the map" />
                {fieldError('lat')}
              </label>
              <label className="text-sm text-slate-300">
                Reference longitude
                <input className={`${inputClass} num mt-1`} value={lon} onChange={(e) => setLon(e.target.value)} placeholder="click the map" />
                {fieldError('lon')}
              </label>
              <label className="text-sm text-slate-300">
                Expected interval (s)
                <input className={`${inputClass} num mt-1`} value={intervalS} onChange={(e) => setIntervalS(e.target.value)} />
                {fieldError('interval')}
              </label>
              <p className="self-end text-xs text-muted">
                Offline after 3 × interval without data. If no reference position is given, it is set from the node’s
                first GPS fixes.
              </p>
            </div>
          </Panel>

          <Panel title="Reference position" eyebrow="Click the map to place the node" bodyClassName="p-0">
            <div className="h-80 overflow-hidden rounded-b-xl">
              <MapContainer center={centre} zoom={16} className="h-full w-full">
                <DarkTiles />
                <ClickToPlace
                  onPick={(la, lo) => {
                    setLat(la.toFixed(7))
                    setLon(lo.toFixed(7))
                  }}
                />
                {(nodes.data ?? []).map((n) => {
                  const p = nodePosition(n)
                  return p ? (
                    <CircleMarker key={n.id} center={p} radius={5} pathOptions={{ color: '#64748b', fillOpacity: 0.6, weight: 1 }} />
                  ) : null
                })}
                {pos && <CircleMarker center={pos} radius={9} pathOptions={{ color: '#2dd4bf', fillColor: '#2dd4bf', fillOpacity: 0.9 }} />}
              </MapContainer>
            </div>
          </Panel>
        </div>

        <Panel title="Alert conditions" eyebrow="Battery, acceleration, slope angle and tilt">
          {drafts === null ? <LoadingState /> : <NewRulesEditor drafts={drafts} onChange={setDrafts} />}
        </Panel>

        {create.isError && (
          <div className="rounded-lg border border-crit/40 bg-crit/10 px-3 py-2 text-sm text-crit" role="alert">
            {create.error.message}
          </div>
        )}
        {submitted && !valid && (
          <div className="text-sm text-crit">Please fix the highlighted fields{ruleErrors.length ? ' and alert rules' : ''}.</div>
        )}
        <div className="flex justify-end gap-2">
          <Button onClick={() => navigate('/devices')}>Cancel</Button>
          <Button type="submit" variant="primary" disabled={create.isPending}>
            {create.isPending ? 'Registering…' : 'Register device'}
          </Button>
        </div>
      </form>

      <ApiKeyDialog created={created} onDone={() => created && navigate(`/devices/${created.node.id}`)} />
    </>
  )
}
