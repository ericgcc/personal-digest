// Compatibility entry point for the scheduled-agent interface.
//
// The application now lives in `src/`. This file exists solely so the documented
// invocation `node --env-file=.env tools/digest_runner.mjs <command>` keeps working for
// the scheduled-task agent; it forwards to the CLI and owns no logic of its own.

import "../src/cli/digest.mjs";