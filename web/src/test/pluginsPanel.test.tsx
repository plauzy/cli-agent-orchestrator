import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { PluginsPanel } from '../components/PluginsPanel'
import { PLUGINS_TAB_ENABLED } from '../featureFlags'

/**
 * The load-bearing test in this file is
 * "clicking Remove issues no DELETE until the operator confirms".
 *
 * Requirement 17.5 only obliges the API to *report* which live sessions a
 * removal affects. A panel that fired DELETE straight off a click would satisfy
 * 17.5 while gating nothing for a web user, even though the CLI refuses to
 * remove without confirmation. The panel is therefore a second, independent
 * enforcement point for Requirement 15's warn-and-confirm behaviour, and that
 * is what is asserted here.
 */

const WARNING =
  'Installing an agent plugin runs untrusted code and content from that source. ' +
  'CAO does not verify plugin authorship or integrity: there is no signing and ' +
  'no provenance check. Only install plugins from sources you trust.'

const PLUGIN_WITH_LIVE_SESSION = {
  name: 'example',
  version: '1.0.0',
  schema_id: 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json',
  source: { kind: 'path', location: '/src/example', ref: null, subdir: null },
  resolved_ref: null,
  installed_at: '2026-01-01T00:00:00+00:00',
  skill_names: ['alpha', 'beta'],
  projected_skill_names: ['alpha'],
  findings: [
    {
      severity: 'skipped',
      code: 'projection.preexisting_skill',
      spec_ref: '§7.1',
      message: "not projecting skill 'beta': a built-in skill of that name already exists",
      path: 'beta',
    },
  ],
  affected_sessions: [
    {
      terminal_id: 'abcd1234',
      session_name: 'cao-demo',
      provider: 'kiro_cli',
      agent_profile: 'dev',
      skill_names: ['alpha'],
    },
  ],
}

describe('PluginsPanel', () => {
  let calls: { url: string; method: string; body?: any }[]
  let listPayload: any

  const mockFetch = vi.fn(async (url: string, opts?: any) => {
    const method = opts?.method || 'GET'
    calls.push({
      url,
      method,
      body: opts?.body ? JSON.parse(opts.body) : undefined,
    })

    if (url === '/plugins' && method === 'GET') {
      return { ok: true, status: 200, json: () => Promise.resolve(listPayload) }
    }
    if (url === '/plugins' && method === 'POST') {
      return {
        ok: true,
        status: 201,
        json: () =>
          Promise.resolve({
            installed: true,
            name: 'newly-installed',
            version: '2.0.0',
            projected_skill_names: ['gamma'],
            report: {},
            findings: [],
            refreshed_agents: 0,
            untrusted_content_warning: WARNING,
          }),
      }
    }
    if (url.startsWith('/plugins/') && method === 'DELETE') {
      return {
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            success: true,
            name: 'example',
            removed: true,
            purged_data: false,
            withdrawn_skill_names: ['alpha'],
            affected_sessions: [],
            refreshed_agents: 0,
          }),
      }
    }
    return { ok: false, status: 404, statusText: 'Not Found', json: () => Promise.resolve({}) }
  })

  beforeEach(() => {
    calls = []
    listPayload = {
      plugins: [PLUGIN_WITH_LIVE_SESSION],
      swept: [],
      untrusted_content_warning: WARNING,
    }
    vi.stubGlobal('fetch', mockFetch)
  })
  afterEach(() => vi.restoreAllMocks())

  const deleteCalls = () => calls.filter(c => c.method === 'DELETE')

  it('renders the installed set with its projected skills (Req 17.2)', async () => {
    render(<PluginsPanel />)

    expect(await screen.findByText('example')).toBeInTheDocument()
    expect(screen.getByText('v1.0.0')).toBeInTheDocument()
    expect(screen.getByText(/Skills:\s*alpha/)).toBeInTheDocument()
  })

  it('renders non-fatal findings, not just fatal ones (Req 17.2)', async () => {
    render(<PluginsPanel />)

    await screen.findByText('example')
    const findings = screen.getByTestId('plugin-findings')

    expect(findings).toHaveTextContent('projection.preexisting_skill')
    expect(findings).toHaveTextContent('§7.1')
    expect(findings).toHaveTextContent('skipped')
  })

  it('states the untrusted-content warning (Req 22.1)', async () => {
    render(<PluginsPanel />)

    const warning = await screen.findByTestId('untrusted-warning')

    expect(warning).toHaveTextContent('untrusted code and content')
    expect(warning).toHaveTextContent('no signing')
  })

  it('offers an install-from-GitHub-URL affordance (Req 17.3)', async () => {
    render(<PluginsPanel />)
    await screen.findByText('example')

    const input = screen.getByLabelText('Plugin source')
    fireEvent.change(input, { target: { value: 'https://github.com/owner/repo' } })
    fireEvent.click(screen.getByRole('button', { name: /^Install$/ }))

    await waitFor(() => {
      const post = calls.find(c => c.url === '/plugins' && c.method === 'POST')
      expect(post?.body?.source).toBe('https://github.com/owner/repo')
    })
  })

  it('passes ref and subdir through when supplied', async () => {
    render(<PluginsPanel />)
    await screen.findByText('example')

    fireEvent.change(screen.getByLabelText('Plugin source'), {
      target: { value: 'https://github.com/owner/repo' },
    })
    fireEvent.change(screen.getByLabelText('Git ref'), { target: { value: 'v1.2.3' } })
    fireEvent.change(screen.getByLabelText('Subdirectory'), {
      target: { value: 'agent-plugin/cao' },
    })
    fireEvent.click(screen.getByRole('button', { name: /^Install$/ }))

    await waitFor(() => {
      const post = calls.find(c => c.url === '/plugins' && c.method === 'POST')
      expect(post?.body).toMatchObject({ ref: 'v1.2.3', subdir: 'agent-plugin/cao' })
    })
  })

  it('surfaces the live sessions a removal would affect (Req 17.5)', async () => {
    render(<PluginsPanel />)

    await screen.findByText('example')

    expect(screen.getByTestId('plugin-example-affected')).toHaveTextContent(
      '1 live session(s) can reach its skills',
    )
  })

  // ── The enforcement point ────────────────────────────────────────────────

  it('issues NO DELETE when Remove is clicked — it only opens the gate', async () => {
    render(<PluginsPanel />)
    await screen.findByText('example')

    fireEvent.click(screen.getByRole('button', { name: 'Remove example' }))

    // The confirmation is showing...
    expect(await screen.findByText("Remove 'example'?")).toBeInTheDocument()
    // ...and nothing has been sent.
    expect(deleteCalls()).toHaveLength(0)
  })

  it('shows the affected sessions and skills inside the confirmation', async () => {
    render(<PluginsPanel />)
    await screen.findByText('example')

    fireEvent.click(screen.getByRole('button', { name: 'Remove example' }))

    await screen.findByText("Remove 'example'?")
    expect(screen.getByText(/Live session cao-demo \(kiro_cli\)/)).toBeInTheDocument()
    expect(screen.getByText(/terminal abcd1234 can reach alpha/)).toBeInTheDocument()
    expect(screen.getByText('Skills withdrawn')).toBeInTheDocument()
  })

  it('issues the DELETE only after the operator confirms', async () => {
    render(<PluginsPanel />)
    await screen.findByText('example')

    fireEvent.click(screen.getByRole('button', { name: 'Remove example' }))
    await screen.findByText("Remove 'example'?")
    expect(deleteCalls()).toHaveLength(0)

    fireEvent.click(screen.getByRole('button', { name: 'Remove plugin' }))

    await waitFor(() => expect(deleteCalls()).toHaveLength(1))
    expect(deleteCalls()[0].url).toBe('/plugins/example')
  })

  it('issues no DELETE when the operator cancels (Req 15.3 — warns, never forces)', async () => {
    render(<PluginsPanel />)
    await screen.findByText('example')

    fireEvent.click(screen.getByRole('button', { name: 'Remove example' }))
    await screen.findByText("Remove 'example'?")
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() =>
      expect(screen.queryByText("Remove 'example'?")).not.toBeInTheDocument(),
    )
    expect(deleteCalls()).toHaveLength(0)
  })

  it('reloads the installed set after a confirmed removal', async () => {
    render(<PluginsPanel />)
    await screen.findByText('example')
    const listsBefore = calls.filter(c => c.url === '/plugins' && c.method === 'GET').length

    fireEvent.click(screen.getByRole('button', { name: 'Remove example' }))
    await screen.findByText("Remove 'example'?")
    listPayload = { plugins: [], swept: [], untrusted_content_warning: WARNING }
    fireEvent.click(screen.getByRole('button', { name: 'Remove plugin' }))

    await waitFor(() => expect(screen.getByTestId('plugins-empty')).toBeInTheDocument())
    const listsAfter = calls.filter(c => c.url === '/plugins' && c.method === 'GET').length
    expect(listsAfter).toBeGreaterThan(listsBefore)
  })

  it('renders an empty state when nothing is installed', async () => {
    listPayload = { plugins: [], swept: [], untrusted_content_warning: WARNING }
    render(<PluginsPanel />)

    expect(await screen.findByTestId('plugins-empty')).toBeInTheDocument()
  })

  it('reports swept dangling links', async () => {
    listPayload = { plugins: [], swept: ['stale-skill'], untrusted_content_warning: WARNING }
    render(<PluginsPanel />)

    expect(await screen.findByTestId('swept-notice')).toHaveTextContent('stale-skill')
  })
})

describe('Plugins tab gating', () => {
  it('is disabled by default pending decision M1 (Req 16.5)', () => {
    // Flipping this to true is the whole change once M1 lands.
    expect(PLUGINS_TAB_ENABLED).toBe(false)
  })
})
