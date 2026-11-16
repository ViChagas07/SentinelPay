const documents = new Map<string, File>();

export function rememberDocument(analysisId: string, file: File): void {
  documents.set(analysisId, file);
}

export function peekDocument(analysisId: string): File | null {
  return documents.get(analysisId) ?? null;
}

export function takeDocument(analysisId: string): File | null {
  const file = documents.get(analysisId) ?? null;

  if (file) {
    documents.delete(analysisId);
  }

  return file;
}

export function forgetDocument(analysisId: string): void {
  documents.delete(analysisId);
}
