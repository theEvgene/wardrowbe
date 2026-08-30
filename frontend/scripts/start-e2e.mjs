import { cpSync, existsSync } from 'node:fs';
import { spawn } from 'node:child_process';
import path from 'node:path';

const root = process.cwd();
const standalone = path.join(root, '.next', 'standalone');
const staticSource = path.join(root, '.next', 'static');
const publicSource = path.join(root, 'public');

if (!existsSync(path.join(standalone, 'server.js'))) {
  throw new Error('Missing standalone build. Run `npm run build` before browser E2E.');
}

cpSync(staticSource, path.join(standalone, '.next', 'static'), {
  recursive: true,
  force: true,
});
if (existsSync(publicSource)) {
  cpSync(publicSource, path.join(standalone, 'public'), {
    recursive: true,
    force: true,
  });
}

const server = spawn(process.execPath, [path.join(standalone, 'server.js')], {
  env: {
    ...process.env,
    HOSTNAME: '127.0.0.1',
    PORT: '3100',
  },
  stdio: 'inherit',
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => server.kill(signal));
}

server.on('exit', (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  process.exit(code ?? 1);
});
