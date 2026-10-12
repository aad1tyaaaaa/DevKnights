import { keccak256, stringToBytes } from "viem";

// Reference implementation of the canonical release manifest; must match backend/app/blockchain/manifest.py.
export const SCHEMA_VERSION = 1;

export function canonicalManifestJson(name: string, version: string, integrity: string): string {
  const manifest: Record<string, string | number> = { schema_version: SCHEMA_VERSION, name, version, integrity };
  const sorted = Object.fromEntries(Object.keys(manifest).sort().map((k) => [k, manifest[k]]));
  return JSON.stringify(sorted);
}

export function manifestHash(name: string, version: string, integrity: string): `0x${string}` {
  return keccak256(stringToBytes(canonicalManifestJson(name, version, integrity)));
}
