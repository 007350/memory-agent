const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

export interface ToolCall {
  name: string;
  arguments: Record<string, any>;
  result: string;
  error: string;
  latency: number;
}

export interface UsedMemory {
  id: number | null;
  event_type: string;
  content: string;
  score: number;
}

export interface ChatResponse {
  answer: string;
  agent: string;
  sources: { file_path: string; reference_id: string }[];
  retrieval_mode: string;
  reflection_passed: boolean;
  reflection_count: number;
  latency: number;
  session_id: string;
  tool_calls: ToolCall[];
  used_memories?: UsedMemory[];
}

export interface Memory {
  id: number;
  session: string;
  type: string;
  content: string;
  created_at: number;
}

export interface UserProfile {
  user_id: string;
  profile: Record<string, string>;
}

export interface MemoryEvent {
  id: number;
  user_id: string;
  event_type: string;
  content: string;
  importance: number;
  expired_at: number | null;
  metadata: Record<string, unknown>;
  created_at: number;
  source?: string;
  feedback_score?: number;
  feedback_count?: number;
}

export async function sendChat(query: string, sessionId: string, userId: string, signal?: AbortSignal): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, session_id: sessionId, user_id: userId }),
  });
  if (signal?.aborted) {
    throw new Error('request_cancelled');
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.message ?? `Chat failed: ${res.status}`);
  }
  return res.json();
}

export async function insertDocument(text: string, fileSource: string): Promise<{ status: string; track_id: string }> {
  const res = await fetch(`${API_BASE}/documents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, file_source: fileSource }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.message ?? `Insert failed: ${res.status}`);
  }
  return res.json();
}

export async function getMemory(sessionId: string): Promise<Memory[]> {
  const res = await fetch(`${API_BASE}/memory/${sessionId}`);
  if (!res.ok) {
    console.warn('getMemory failed', res.status);
    return [];
  }
  const data = await res.json();
  return data.memories ?? [];
}

export async function clearMemory(sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/memory`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export async function deleteMemory(sessionId: string, memoryId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/memory/${encodeURIComponent(sessionId)}/item/${memoryId}`, { method: 'DELETE' });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.message ?? `deleteMemory failed: ${res.status}`);
  }
}

export async function expireMemoryEvent(userId: string, eventId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/memory/${encodeURIComponent(userId)}/events/${eventId}`, { method: 'DELETE' });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.message ?? `expireMemoryEvent failed: ${res.status}`);
  }
}

export async function getUserProfile(userId: string): Promise<UserProfile> {
  const res = await fetch(`${API_BASE}/memory/${encodeURIComponent(userId)}/profile`);
  if (!res.ok) {
    throw new Error(`getUserProfile failed: ${res.status}`);
  }
  return res.json();
}

export async function updateUserProfile(userId: string, profile: Record<string, string>): Promise<UserProfile> {
  const res = await fetch(`${API_BASE}/memory/${encodeURIComponent(userId)}/profile`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.message ?? `updateUserProfile failed: ${res.status}`);
  }
  return res.json();
}

export async function getMemoryEvents(userId: string, limit = 20, minImportance = 0): Promise<MemoryEvent[]> {
  const params = new URLSearchParams({ limit: String(limit), min_importance: String(minImportance) });
  const res = await fetch(`${API_BASE}/memory/${encodeURIComponent(userId)}/events?${params}`);
  if (!res.ok) {
    throw new Error(`getMemoryEvents failed: ${res.status}`);
  }
  const data = await res.json();
  return data.events ?? [];
}

export async function clearMemoryEvents(userId: string): Promise<void> {
  await fetch(`${API_BASE}/memory/${encodeURIComponent(userId)}/events`, { method: 'DELETE' });
}

export async function sendMemoryFeedback(userId: string, eventId: number, feedback: 'up' | 'down'): Promise<void> {
  const res = await fetch(`${API_BASE}/memory/${encodeURIComponent(userId)}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ event_id: eventId, feedback }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.message ?? `sendMemoryFeedback failed: ${res.status}`);
  }
}

export async function summarizeProfile(userId: string, summary?: string, source = 'manual'): Promise<UserProfile> {
  const res = await fetch(`${API_BASE}/memory/${encodeURIComponent(userId)}/summary`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ summary: summary ?? '', source }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.message ?? `summarizeProfile failed: ${res.status}`);
  }
  return res.json();
}

export async function rollbackProfile(userId: string): Promise<UserProfile> {
  const res = await fetch(`${API_BASE}/memory/${encodeURIComponent(userId)}/rollback`, { method: 'DELETE' });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.message ?? `rollbackProfile failed: ${res.status}`);
  }
  return res.json();
}


export async function uploadDocumentFile(file: File): Promise<{ status: string; track_id: string }> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/documents/upload`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail?.message ?? data?.message ?? `Upload failed: ${res.status}`);
  }
  return res.json();
}

export interface RoadmapStep {
  id: number;
  title: string;
  detail: string;
  done: boolean;
}

export interface Roadmap {
  id: number;
  user_id: string;
  doc_ref: string;
  title: string;
  steps: RoadmapStep[];
  created_at: number;
  updated_at: number;
}

export async function getRoadmaps(userId: string): Promise<Roadmap[]> {
  const res = await fetch(`${API_BASE}/roadmaps?user_id=${encodeURIComponent(userId)}`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.roadmaps ?? [];
}

export async function updateRoadmapStep(roadmapId: number, stepId: number, done: boolean): Promise<void> {
  const res = await fetch(`${API_BASE}/roadmaps/${roadmapId}/steps/${stepId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ done }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail ?? `updateRoadmapStep failed: ${res.status}`);
  }
}

export async function deleteRoadmap(roadmapId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/roadmaps/${roadmapId}`, { method: 'DELETE' });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail ?? `deleteRoadmap failed: ${res.status}`);
  }
}

export async function healthCheck(): Promise<{ status: string; lightrag: string }> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    return { status: 'error', lightrag: 'unknown' };
  }
  return res.json();
}
