// Lint config for web/app.js — the RockForge web UI's client-side script — and web/highway3d.js
// (extracted from index.html's inline <script> so it can be linted at all;
// see CLAUDE.md's "Web UI" section). Browser-globals script, not a module —
// the file relies on top-level `function`/`const` declarations being visible
// to inline event-handler attributes and to each other in load order.
module.exports = [
  {
    files: ["web/app.js", "web/highway3d.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: {
        window: "readonly",
        document: "readonly",
        console: "readonly",
        fetch: "readonly",
        navigator: "readonly",
        location: "readonly",
        history: "readonly",
        localStorage: "readonly",
        sessionStorage: "readonly",
        FormData: "readonly",
        Blob: "readonly",
        URL: "readonly",
        URLSearchParams: "readonly",
        Event: "readonly",
        Image: "readonly",
        Audio: "readonly",
        AudioContext: "readonly",
        OfflineAudioContext: "readonly",
        AudioBuffer: "readonly",
        requestAnimationFrame: "readonly",
        cancelAnimationFrame: "readonly",
        setInterval: "readonly",
        clearInterval: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        addEventListener: "readonly",
        removeEventListener: "readonly",
        alert: "readonly",
        confirm: "readonly",
        prompt: "readonly",
        performance: "readonly",
        structuredClone: "readonly",
        ResizeObserver: "readonly",
      },
    },
    rules: {
      // Real-bug categories only — this file predates any lint config and is
      // not being reformatted wholesale; a stylistic ruleset would drown the
      // signal in churn unrelated to correctness.
      "no-undef": "error",
      "no-unused-vars": ["warn", { args: "none", varsIgnorePattern: "^_" }],
      "no-redeclare": "error",
      "no-dupe-keys": "error",
      "no-dupe-args": "error",
      "no-const-assign": "error",
      "no-unreachable": "error",
      "no-fallthrough": "error",
      "no-import-assign": "error",
      "no-self-assign": "error",
      "no-setter-return": "error",
      "use-isnan": "error",
      "valid-typeof": "error",
    },
  },
];
