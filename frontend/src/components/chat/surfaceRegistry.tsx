import { lazy, type ComponentType } from 'react';

/**
 * Screens that can be mounted *inside* the chat thread.
 *
 * These are the same lazy-loaded page components the sidebar renders — only the
 * container changes, from a full page to a card in the conversation. That is
 * what makes chat-first possible without rewriting any of the pages.
 *
 * The ids match `UI_SURFACES` in `app/services/ui_surface_service.py`, which is
 * the authority on which surfaces exist and who may open them.
 */

const DocumentAutomationPage = lazy(() => import('../DocumentAutomationPage'));
const DocumentsViewerPage = lazy(() => import('../DocumentsViewerPage'));
const HandoverPage = lazy(() => import('../HandoverPage'));
const HiringPage = lazy(() => import('../HiringPage'));
const ProgressLogPage = lazy(() => import('../ProgressLogPage'));
const SkillsPage = lazy(() => import('../SkillsPage'));
const UploadPage = lazy(() => import('../UploadPage'));
const WorkItemsPage = lazy(() => import('../WorkItemsPage'));
const WorkSchedulePage = lazy(() => import('../WorkSchedulePage'));
const WorkflowStatusPage = lazy(() => import('../WorkflowStatusPage'));

/**
 * Dense admin tables (인사관리, 접근제어, API 키) are deliberately absent: they
 * are worse inside a chat bubble than on their own screen, so they stay routed.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- each page has
// its own prop shape; the backend `prop_schema` is the contract.
export const surfaceComponents: Record<string, ComponentType<any>> = {
  documents: DocumentAutomationPage,
  'documents-viewer': DocumentsViewerPage,
  handover: HandoverPage,
  hiring: HiringPage,
  progress: ProgressLogPage,
  skills: SkillsPage,
  uploads: UploadPage,
  work: WorkItemsPage,
  'work-schedule': WorkSchedulePage,
  'workflow-status': WorkflowStatusPage,
};

export function canRenderInline(component: string): boolean {
  return component in surfaceComponents;
}
