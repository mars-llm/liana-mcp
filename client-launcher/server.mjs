#!/usr/bin/env node
// Local compatibility launcher only. No package downloads or protocol handling.
import {spawn} from 'node:child_process';
import {existsSync} from 'node:fs';
import {dirname, isAbsolute, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const python = join(root, '.venv', 'bin', 'python');
const args = process.argv.slice(2);
if (args.length !== 2 || args[0] !== '--config' || !isAbsolute(args[1]) ||
    !existsSync(args[1]) || !existsSync(python)) {
  process.stderr.write('Expected a prepared local environment and --config /absolute/private/file.\n');
  process.exit(2);
}
const child = spawn(python, ['-m', 'liana_mcp.cli', ...args], {
  cwd: root,
  stdio: 'inherit',
  env: {PATH: '/usr/bin:/bin', OTEL_SDK_DISABLED: 'true'},
});
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
child.on('error', () => {
  process.stderr.write('The experimental local MCP server did not start.\n');
  process.exit(1);
});
child.on('exit', code => process.exit(code ?? 1));
