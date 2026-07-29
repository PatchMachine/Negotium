import { requestJson } from './http';
import type { AutomationConfig, AutomationStatus, NotificationsPayload } from './types';

export function fetchAutomationStatus(): Promise<AutomationStatus> {
  return requestJson<AutomationStatus>('/api/automation/config');
}

export function saveAutomationConfig(config: AutomationConfig): Promise<AutomationStatus> {
  return requestJson<AutomationStatus>('/api/automation/config', {
    method: 'PUT',
    body: JSON.stringify(config),
  });
}

export function runAutomationJobs(jobs: string[]): Promise<{ executed: string[] }> {
  return requestJson<{ executed: string[] }>('/api/automation/run', {
    method: 'POST',
    body: JSON.stringify({ jobs }),
  });
}

export function fetchNotifications(): Promise<NotificationsPayload> {
  return requestJson<NotificationsPayload>('/api/notifications');
}

export function markNotificationsRead(ids: string[]): Promise<{ marked: number }> {
  return requestJson<{ marked: number }>('/api/notifications/read', {
    method: 'POST',
    body: JSON.stringify({ ids }),
  });
}
