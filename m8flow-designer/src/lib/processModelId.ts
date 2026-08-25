/**
 * Process model identifiers use `/` on disk and in API `id` fields.
 * React Router path segments and the backend detail route use `:` instead.
 */
export function encodeProcessModelId(id: string): string {
  return id.split('/').join(':');
}

export function decodeProcessModelId(encoded: string): string {
  return encoded.split(':').join('/');
}
