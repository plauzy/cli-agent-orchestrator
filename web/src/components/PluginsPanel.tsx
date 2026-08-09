import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Loader2, Package, Plus, Trash2 } from 'lucide-react'
import { api, type InstalledPlugin, type PluginFinding } from '../api'
import { ConfirmModal } from './ConfirmModal'

/**
 * Agent plugins panel (agent-plugins.org 1.0.0).
 *
 * Unrelated to CAO's `cao.plugins` EVENT-plugin system (decision D7).
 *
 * # This panel is an enforcement point, not a renderer
 *
 * Requirement 17.5 only requires the API to *report* which live sessions a
 * removal would affect. Left there, a panel that fired `DELETE /plugins/{name}`
 * straight off a click would satisfy 17.5 while gating nothing at all for a web
 * user, even though the CLI refuses to remove without confirmation.
 *
 * So this component is a second, independent enforcement point for the
 * warn-and-confirm behaviour Requirement 15 mandates: it renders the affected
 * sessions and skill names and **waits for the operator to confirm before the
 * DELETE request is issued**. It warns; it never refuses (Requirement 15.3).
 */

const SEVERITY_ORDER: Record<string, number> = { fatal: 0, skipped: 1, warning: 2, info: 3 }

function severityClasses(severity: string): string {
  switch (severity) {
    case 'fatal':
      return 'text-red-300 bg-red-900/30 border-red-800/50'
    case 'skipped':
      return 'text-amber-300 bg-amber-900/30 border-amber-800/50'
    case 'warning':
      return 'text-yellow-300 bg-yellow-900/30 border-yellow-800/50'
    default:
      return 'text-gray-300 bg-gray-800/50 border-gray-700/50'
  }
}

function FindingList({ findings }: { findings: PluginFinding[] }) {
  if (findings.length === 0) return null
  // Worst-first. Non-fatal findings are shown too (Requirement 17.2): they are
  // what explain why a skill the plugin ships is not available.
  const sorted = [...findings].sort(
    (a, b) => (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9),
  )
  return (
    <ul className="mt-2 space-y-1" data-testid="plugin-findings">
      {sorted.map((finding, index) => (
        <li
          key={`${finding.code}-${index}`}
          className={`text-xs border rounded-lg px-2 py-1 ${severityClasses(finding.severity)}`}
        >
          <span className="font-semibold uppercase mr-2">{finding.severity}</span>
          <span className="font-mono mr-2">{finding.code}</span>
          <span className="text-gray-400 mr-2">{finding.spec_ref}</span>
          <span>{finding.message}</span>
        </li>
      ))}
    </ul>
  )
}

export function PluginsPanel() {
  const [plugins, setPlugins] = useState<InstalledPlugin[]>([])
  const [warning, setWarning] = useState('')
  const [swept, setSwept] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [source, setSource] = useState('')
  const [ref, setRef] = useState('')
  const [subdir, setSubdir] = useState('')
  const [installing, setInstalling] = useState(false)
  const [installMessage, setInstallMessage] = useState<string | null>(null)

  // Removal is a two-step flow by construction: `pending` holds the plugin the
  // operator asked to remove, and the DELETE is only issued from the modal's
  // confirm handler.
  const [pending, setPending] = useState<InstalledPlugin | null>(null)
  const [purgeData, setPurgeData] = useState(false)
  const [removing, setRemoving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.listPlugins()
      setPlugins(data.plugins)
      setWarning(data.untrusted_content_warning)
      setSwept(data.swept ?? [])
      setError(null)
    } catch (e: any) {
      setError(e?.detail || e?.message || 'Failed to load agent plugins')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const install = async () => {
    if (!source.trim()) return
    setInstalling(true)
    setInstallMessage(null)
    try {
      const result = await api.installPlugin({
        source: source.trim(),
        ref: ref.trim() || undefined,
        subdir: subdir.trim() || undefined,
      })
      setInstallMessage(
        `Installed '${result.name}'` +
          (result.projected_skill_names.length
            ? ` — projected ${result.projected_skill_names.join(', ')}`
            : ' — no skills projected'),
      )
      setSource('')
      setRef('')
      setSubdir('')
      await load()
    } catch (e: any) {
      // A 422 carries the full validation report; surface the server's message.
      setInstallMessage(e?.detail || e?.message || 'Install failed')
    } finally {
      setInstalling(false)
    }
  }

  const confirmRemove = async () => {
    if (!pending) return
    setRemoving(true)
    try {
      await api.removePlugin(pending.name, purgeData)
      setPending(null)
      setPurgeData(false)
      await load()
    } catch (e: any) {
      setError(e?.detail || e?.message || 'Failed to remove agent plugin')
      setPending(null)
    } finally {
      setRemoving(false)
    }
  }

  const pendingDetails = useMemo(() => {
    if (!pending) return []
    const details: { label: string; value: string }[] = [
      {
        label: 'Skills withdrawn',
        value: pending.projected_skill_names.length
          ? pending.projected_skill_names.join(', ')
          : 'none',
      },
    ]
    for (const session of pending.affected_sessions) {
      details.push({
        label: `Live session ${session.session_name} (${session.provider})`,
        value: `terminal ${session.terminal_id} can reach ${session.skill_names.join(', ')}`,
      })
    }
    return details
  }, [pending])

  return (
    <div className="space-y-6">
      {/* Requirement 22.1: stated at or before the point of install. */}
      {warning && (
        <div
          className="flex items-start gap-3 text-sm text-amber-200 bg-amber-900/20 border border-amber-800/50 rounded-xl px-4 py-3"
          data-testid="untrusted-warning"
        >
          <AlertTriangle size={16} className="shrink-0 mt-0.5" />
          <span>{warning}</span>
        </div>
      )}

      {/* Install affordance (Requirement 17.3): a GitHub URL is the headline case. */}
      <section className="bg-gray-900/60 border border-gray-800 rounded-xl p-4">
        <h2 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <Plus size={15} /> Install a plugin
        </h2>
        <div className="grid gap-2 md:grid-cols-[2fr_1fr_1fr_auto]">
          <input
            aria-label="Plugin source"
            placeholder="https://github.com/owner/repo  or  /path/to/plugin"
            value={source}
            onChange={e => setSource(e.target.value)}
            className="bg-gray-950 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
          />
          <input
            aria-label="Git ref"
            placeholder="ref (optional)"
            value={ref}
            onChange={e => setRef(e.target.value)}
            className="bg-gray-950 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
          />
          <input
            aria-label="Subdirectory"
            placeholder="subdir (optional)"
            value={subdir}
            onChange={e => setSubdir(e.target.value)}
            className="bg-gray-950 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
          />
          <button
            onClick={install}
            disabled={installing || !source.trim()}
            className="inline-flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg px-4 py-2"
          >
            {installing ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
            Install
          </button>
        </div>
        {installMessage && (
          <p className="mt-2 text-xs text-gray-300" data-testid="install-message">
            {installMessage}
          </p>
        )}
      </section>

      {swept.length > 0 && (
        <p className="text-xs text-gray-400" data-testid="swept-notice">
          Swept {swept.length} dangling projected skill link(s): {swept.join(', ')}
        </p>
      )}

      {error && (
        <p className="text-sm text-red-300" data-testid="plugins-error">
          {error}
        </p>
      )}

      {/* Installed set (Requirement 17.2) */}
      <section>
        <h2 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <Package size={15} /> Installed plugins
        </h2>

        {loading ? (
          <p className="text-sm text-gray-500">Loading…</p>
        ) : plugins.length === 0 ? (
          <p className="text-sm text-gray-500" data-testid="plugins-empty">
            No agent plugins installed
          </p>
        ) : (
          <ul className="space-y-3">
            {plugins.map(plugin => (
              <li
                key={plugin.name}
                className="bg-gray-900/60 border border-gray-800 rounded-xl p-4"
                data-testid={`plugin-${plugin.name}`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-white">{plugin.name}</span>
                      {plugin.version && (
                        <span className="text-xs text-gray-400">v{plugin.version}</span>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-gray-400">
                      Skills:{' '}
                      {plugin.projected_skill_names.length
                        ? plugin.projected_skill_names.join(', ')
                        : 'none projected'}
                    </p>
                    {plugin.affected_sessions.length > 0 && (
                      <p
                        className="mt-1 text-xs text-amber-300"
                        data-testid={`plugin-${plugin.name}-affected`}
                      >
                        {plugin.affected_sessions.length} live session(s) can reach its skills
                      </p>
                    )}
                    <FindingList findings={plugin.findings} />
                  </div>
                  <button
                    onClick={() => {
                      setPurgeData(false)
                      setPending(plugin)
                    }}
                    aria-label={`Remove ${plugin.name}`}
                    className="shrink-0 inline-flex items-center gap-2 text-sm text-red-300 hover:text-red-200 border border-red-900/60 hover:border-red-700 rounded-lg px-3 py-1.5"
                  >
                    <Trash2 size={14} /> Remove
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/*
        The confirmation gate. `pending` is set by the Remove button and the
        DELETE is only issued from onConfirm, so no code path reaches the API
        without the operator having seen the impact first.

        The confirm label is deliberately distinct from the per-row
        "Remove <name>" button so the two are unambiguous to assistive
        technology and to tests.
      */}
      <ConfirmModal
        open={pending !== null}
        title={`Remove '${pending?.name ?? ''}'?`}
        message={
          pending && pending.affected_sessions.length > 0
            ? 'This plugin provides skills that live sessions can currently reach. Those agents may attempt to load a skill that no longer resolves.'
            : 'This removes the plugin and withdraws the skills it projects.'
        }
        details={pendingDetails}
        confirmLabel={purgeData ? 'Remove and delete data' : 'Remove plugin'}
        variant={pending && pending.affected_sessions.length > 0 ? 'danger' : 'warning'}
        loading={removing}
        onConfirm={confirmRemove}
        onCancel={() => {
          setPending(null)
          setPurgeData(false)
        }}
      />
    </div>
  )
}
