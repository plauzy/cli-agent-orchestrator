/**
 * Build-time feature flags for the web UI.
 *
 * Kept in its own module so a flag can be imported (and asserted in a test)
 * without dragging in the whole component tree that `App.tsx` pulls together.
 */

/**
 * Whether the agent-plugins ("Plugins") tab is offered.
 *
 * **OFF by default.** Decision M1 has not settled the naming of the
 * agent-plugin surfaces, and Requirement 16.5 forbids shipping them to end
 * users until it does. The panel, its API client, and the HTTP endpoints are all
 * built and tested; flipping this constant to `true` is the whole change once M1
 * lands.
 *
 * Typed `boolean` rather than left as the literal `false` so switching it does
 * not change the constant's type.
 *
 * Note this gates only the *tab*. The `/plugins/*` endpoints and the `cao
 * plugin` CLI group remain reachable for maintainers, mirroring the CLI group's
 * `hidden=True` (not advertised, still usable).
 */
export const PLUGINS_TAB_ENABLED: boolean = false
