const VISITOR_ID_STORAGE_KEY = 'xhs_pdf_visitor_id';

function generateVisitorId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }

  return `visitor_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

export function getOrCreateVisitorId(): string {
  const existingId = window.localStorage.getItem(VISITOR_ID_STORAGE_KEY);
  if (existingId) {
    return existingId;
  }

  const visitorId = generateVisitorId();
  window.localStorage.setItem(VISITOR_ID_STORAGE_KEY, visitorId);
  return visitorId;
}

export async function trackVisit(apiBaseUrl: string, visitorId: string, path: string): Promise<void> {
  await fetch(`${apiBaseUrl}/api/track-visit`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      visitorId,
      path,
    }),
  });
}
