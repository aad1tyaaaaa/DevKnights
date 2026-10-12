// Starts the FastAPI backend from its virtualenv: `npm run dev:backend` (Windows, macOS, Linux).
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const backend = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'backend');
const python = join(backend, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');

if (!existsSync(python)) {
  console.error(`Backend virtualenv not found at ${python}.
Create it once:
  cd backend
  python -m venv .venv
  ${process.platform === 'win32' ? '.\\.venv\\Scripts\\python.exe' : '.venv/bin/python'} -m pip install -r requirements.txt`);
  process.exit(1);
}

const child = spawn(python, ['-m', 'uvicorn', 'app.main:app', '--reload', '--port', '8000'], { cwd: backend, stdio: 'inherit' });
child.on('exit', (code) => process.exit(code ?? 0));
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
