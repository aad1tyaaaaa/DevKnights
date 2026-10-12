import { keccak256, stringToBytes } from "viem";

/** Release id used by ReleaseRegistry: keccak256 of the UTF-8 string "<name>@<version>". */
export function releaseId(name: string, version: string): `0x${string}` {
  return keccak256(stringToBytes(`${name}@${version}`));
}
