/**
 * Build-time feature flags for the web UI.
 *
 * Kept in its own module so a flag can be imported (and asserted in a test)
 * without dragging in the whole component tree that `App.tsx` pulls together.
 */

/**
 * Whether the agent-plugins ("Plugins") tab is offered.
 *
 * **OFF by default.** The CLI group and the `/plugins*` routes graduated (#1393), but the
 * web tab did not: it is a separate build-time switch with its own review (panel, API
 * client and the `/plugins/*` endpoints are built and tested). Their verb is decision M1,
 * recorded by the issue author in #573. Flipping this constant is the web UI's half of
 * the release.
 *
 * Typed `boolean` rather than left as the literal `false` so switching it does
 * not change the constant's type and does not make the `filter` below look like
 * dead code to the type checker.
 *
 * Note this gates only the *tab*. The `/plugins/*` endpoints and the `cao plugin` CLI
 * group carry their own gate, the `CAO_AGENT_PLUGINS_ENABLED` environment variable,
 * which is on by default and closes with `0`, `false`, `no` or `off`.
 */
export const PLUGINS_TAB_ENABLED: boolean = false
