/**
 * TanStack Query hooks: one per kind of data the pages need.
 *
 * "Real-time" works by polling: live views refetch every 5 seconds
 * (POLL_MS). All data access lives in this folder, so switching to
 * Server-Sent Events later would only change these files.
 */

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { type TimeRange, isLiveRange, resolveRange } from '../lib/time'
import { apiFetch, qs } from './client'
import type {
  Alert,
  AlertDefaults,
  AlertPage,
  AlertRule,
  AlertStatus,
  DashboardSummary,
  MultiSeries,
  NodeCreated,
  NodeDetail,
  NodeOut,
  ReadingPage,
  ReadingSeries,
  RuleChange,
  RuleInput,
  User,
} from './types'

export const POLL_MS = 5000

// ------------------------------------------------------------------ reads

export function useMe() {
  return useQuery({ queryKey: ['me'], queryFn: () => apiFetch<User>('/api/auth/me'), staleTime: 60_000 })
}

export function useDashboardSummary() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: () => apiFetch<DashboardSummary>('/api/dashboard/summary'),
    refetchInterval: POLL_MS,
  })
}

export function useNodes() {
  return useQuery({
    queryKey: ['nodes'],
    queryFn: () => apiFetch<NodeOut[]>('/api/nodes'),
    refetchInterval: POLL_MS,
  })
}

export function useNode(id: number) {
  return useQuery({
    queryKey: ['node', id],
    queryFn: () => apiFetch<NodeDetail>(`/api/nodes/${id}`),
    refetchInterval: POLL_MS,
  })
}

/** All fields of one node over a time range, for the Device detail charts. */
export function useNodeReadings(id: number, range: TimeRange, includeFlagged: boolean) {
  return useQuery({
    queryKey: ['readings', id, range, includeFlagged],
    queryFn: () => {
      const { from, to } = resolveRange(range)
      return apiFetch<ReadingSeries>(
        `/api/nodes/${id}/readings${qs({ from, to, include_flagged: includeFlagged, max_points: 500 })}`,
      )
    },
    refetchInterval: isLiveRange(range) ? POLL_MS : false,
    placeholderData: keepPreviousData,
  })
}

/** One field for several nodes (one line per node). */
export function useSeries(field: string, nodeIds: number[] | null, range: TimeRange, maxPoints = 300) {
  return useQuery({
    queryKey: ['series', field, nodeIds, range, maxPoints],
    queryFn: () => {
      const { from, to } = resolveRange(range)
      return apiFetch<MultiSeries>(
        `/api/readings/series${qs({ field, node_ids: nodeIds?.join(','), from, to, max_points: maxPoints })}`,
      )
    },
    enabled: nodeIds === null || nodeIds.length > 0,
    refetchInterval: isLiveRange(range) ? POLL_MS : false,
    placeholderData: keepPreviousData,
  })
}

export function useReadingsPage(nodeIds: number[], range: TimeRange, page: number, pageSize = 50) {
  return useQuery({
    queryKey: ['readings-page', nodeIds, range, page, pageSize],
    queryFn: () => {
      const { from, to } = resolveRange(range)
      return apiFetch<ReadingPage>(
        `/api/readings${qs({ node_ids: nodeIds.join(','), from, to, page, page_size: pageSize })}`,
      )
    },
    enabled: nodeIds.length > 0,
    placeholderData: keepPreviousData,
  })
}

export function useAlerts(params: { status?: AlertStatus | 'active'; nodeId?: number; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ['alerts', params],
    queryFn: () =>
      apiFetch<AlertPage>(
        `/api/alerts${qs({ status: params.status, node_id: params.nodeId, limit: params.limit, offset: params.offset })}`,
      ),
    refetchInterval: POLL_MS,
    placeholderData: keepPreviousData,
  })
}

export function useAlertRules(nodeId: number) {
  return useQuery({
    queryKey: ['rules', nodeId],
    queryFn: () => apiFetch<AlertRule[]>(`/api/nodes/${nodeId}/alert-rules`),
  })
}

export function useRuleHistory(nodeId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['rule-history', nodeId],
    queryFn: () => apiFetch<RuleChange[]>(`/api/nodes/${nodeId}/alert-rules/history`),
    enabled,
  })
}

export function useAlertDefaults() {
  return useQuery({
    queryKey: ['alert-defaults'],
    queryFn: () => apiFetch<AlertDefaults>('/api/alert-rules/defaults'),
    staleTime: Infinity,
  })
}

// ------------------------------------------------------------------ writes

export function useAcknowledgeAlert() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiFetch<Alert>(`/api/alerts/${id}/acknowledge`, { method: 'POST' }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['alerts'] })
      client.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export interface NewNode {
  name: string
  dev_eui: string
  description: string
  ref_lat: number | null
  ref_lon: number | null
  expected_interval_s: number
  rules: RuleInput[]
}

export function useCreateNode() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: NewNode) => apiFetch<NodeCreated>('/api/nodes', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['nodes'] })
      client.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useSetBaseline(nodeId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () =>
      apiFetch<{ node: NodeOut; updated_rules: AlertRule[] }>(`/api/nodes/${nodeId}/baseline`, {
        method: 'POST',
        body: JSON.stringify({ readings: 10 }),
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['node', nodeId] })
      client.invalidateQueries({ queryKey: ['rules', nodeId] })
      client.invalidateQueries({ queryKey: ['readings', nodeId] })
      client.invalidateQueries({ queryKey: ['rule-history', nodeId] })
    },
  })
}

function invalidateRules(client: ReturnType<typeof useQueryClient>, nodeId: number) {
  client.invalidateQueries({ queryKey: ['rules', nodeId] })
  client.invalidateQueries({ queryKey: ['rule-history', nodeId] })
}

export function useCreateRule(nodeId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: RuleInput) =>
      apiFetch<AlertRule>(`/api/nodes/${nodeId}/alert-rules`, { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => invalidateRules(client, nodeId),
  })
}

export function useUpdateRule(nodeId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<RuleInput> & { justification: string } }) =>
      apiFetch<AlertRule>(`/api/nodes/${nodeId}/alert-rules/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    onSuccess: () => invalidateRules(client, nodeId),
  })
}

export function useDeleteRule(nodeId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, justification }: { id: number; justification: string }) =>
      apiFetch<void>(`/api/nodes/${nodeId}/alert-rules/${id}${qs({ justification })}`, { method: 'DELETE' }),
    onSuccess: () => invalidateRules(client, nodeId),
  })
}
