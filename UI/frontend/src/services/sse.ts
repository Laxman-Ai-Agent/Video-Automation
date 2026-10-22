export interface ActivityEvent {
  id: string;
  projectId?: string;
  stageId?: string;
  agentId?: string;
  messageTelugu?: string;
  messageEnglish?: string;
  eventType: string;
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'success';
  percentage?: number;
  retryAttempt?: number;
  retryMax?: number;
  failingSubStage?: string;
  errorMessage?: string;
}

export type ConnectionStatus = 'connected' | 'reconnecting' | 'disconnected';

export function subscribeToEvents(
  projectId: string | null,
  onEvent: (event: ActivityEvent) => void,
  onStatusChange?: (status: ConnectionStatus) => void
): () => void {
  const url = projectId 
    ? `/projects/${projectId}/agent-communications/stream`
    : `/stream/events`;

  let eventSource: EventSource | null = null;
  let active = true;
  const seenEventIds = new Set<string>();

  try {
    if (onStatusChange) onStatusChange('reconnecting');
    eventSource = new EventSource(url);

    eventSource.onopen = () => {
      if (!active) return;
      if (onStatusChange) onStatusChange('connected');
    };

    eventSource.onmessage = (e) => {
      if (!active) return;
      try {
        const data = JSON.parse(e.data);
        const evtId = data.id || `evt-${data.timestamp || Date.now()}-${data.event_type || 'status'}`;
        
        // Deduplicate events to prevent duplicate state churn
        if (seenEventIds.has(evtId)) return;
        seenEventIds.add(evtId);
        if (seenEventIds.size > 250) {
          const firstKey = seenEventIds.values().next().value;
          if (firstKey) seenEventIds.delete(firstKey);
        }

        const pct = data.progress_percent !== undefined 
          ? data.progress_percent 
          : (data.percentage !== undefined ? data.percentage : (data.percent !== undefined ? data.percent : undefined));
        
        onEvent({
          id: evtId,
          projectId: data.project_id || projectId || undefined,
          stageId: data.stage_id,
          agentId: data.agent_id || data.sender_agent_id || data.source_agent_id,
          messageTelugu: data.telugu_status || data.telugu_activity || data.message_telugu,
          messageEnglish: data.message || data.content || data.technical_message || data.text,
          eventType: data.event_type || data.message_type || 'status_update',
          timestamp: data.timestamp || new Date().toISOString(),
          level: data.level || (data.event_type?.includes('error') ? 'error' : 'info'),
          percentage: pct !== undefined ? Number(pct) : undefined,
          retryAttempt: data.attempt !== undefined ? Number(data.attempt) : undefined,
          retryMax: data.max_attempts !== undefined ? Number(data.max_attempts) : undefined,
          failingSubStage: data.sub_stage || data.failing_sub_stage,
          errorMessage: data.error || (data.event_type?.includes('error') ? (data.message || data.content) : undefined)
        });
      } catch {
        // Fallback text event
        onEvent({
          id: `raw-${Date.now()}`,
          messageEnglish: e.data,
          eventType: 'raw',
          timestamp: new Date().toISOString(),
          level: 'info'
        });
      }
    };

    eventSource.onerror = () => {
      if (!active) return;
      if (onStatusChange) {
        if (eventSource?.readyState === EventSource.CONNECTING) {
          onStatusChange('reconnecting');
        } else {
          onStatusChange('disconnected');
        }
      }
    };
  } catch {
    if (onStatusChange) onStatusChange('disconnected');
  }

  return () => {
    active = false;
    if (eventSource) {
      eventSource.close();
    }
    if (onStatusChange) onStatusChange('disconnected');
  };
}
