import * as vscode from 'vscode';
import type { Lockfile } from '../types';

/** Same cap the backend enforces by default (PROVENYX_MAX_SCAN_BYTES). */
export const MAX_LOCKFILE_BYTES = 10 * 1024 * 1024;

export function projectName(): string | undefined {
  return vscode.workspace.workspaceFolders?.[0]?.name;
}

export function isProjectLockfile(uri: vscode.Uri): boolean {
  return uri.path.endsWith('/package-lock.json') && !uri.path.includes('/node_modules/');
}

/** Finds package-lock.json files in the workspace, ignoring node_modules. */
export async function findLockfiles(): Promise<vscode.Uri[]> {
  const found = await vscode.workspace.findFiles('**/package-lock.json', '**/node_modules/**', 50);
  return found.sort((a, b) => a.path.length - b.path.length);
}

/** Reads and structurally validates a lockfile. Throws an Error with a user-facing message. */
export async function readLockfile(uri: vscode.Uri): Promise<Lockfile> {
  const { size } = await vscode.workspace.fs.stat(uri);
  if (size > MAX_LOCKFILE_BYTES) {
    throw new Error(`package-lock.json is ${(size / 1048576).toFixed(1)} MB; the limit is 10 MB.`);
  }
  const text = new TextDecoder('utf-8').decode(await vscode.workspace.fs.readFile(uri));
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error('package-lock.json is not valid JSON.');
  }
  return validateLockfile(data);
}

export function validateLockfile(data: unknown): Lockfile {
  if (typeof data !== 'object' || data === null || Array.isArray(data)) {
    throw new Error('package-lock.json must contain a JSON object.');
  }
  const lock = data as Lockfile;
  if (![1, 2, 3].includes(lock.lockfileVersion)) {
    throw new Error(`Unsupported lockfileVersion: ${String(lock.lockfileVersion)}. Expected 1, 2 or 3.`);
  }
  const section = lock.lockfileVersion === 1 ? 'dependencies' : 'packages';
  const value = lock[section];
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error(`lockfileVersion ${lock.lockfileVersion} requires a "${section}" object.`);
  }
  return lock;
}
