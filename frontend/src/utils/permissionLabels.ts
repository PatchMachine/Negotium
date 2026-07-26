const PERMISSION_LABELS: Record<string, string> = {
  '*': '전체 권한',
  'admin:api_keys': 'API 키 관리',
  'admin:users': '사용자·조직 관리',
  'admin:local_llm': '로컬 AI 모델 관리',
  'admin:hr_evaluation': '인사평가 관리',
  'admin:mcp': 'MCP 도구 관리',
  'admin:integrations': '외부 서비스 연동 관리',
  'admin:token_limits': 'AI 토큰 한도 관리',
  'memory:write': '메모리·업무 정보 수정',
  'llm:chat': 'AI 어시스턴트 사용',
  'documents:write': '문서 생성·수정',
  'documents:read': '문서 열람',
  'uploads:write': '파일 업로드',
  'work:read': '업무 정보 열람',
  'patch_records:read': '패치 기록 열람',
  'patch_records:write': '패치 기록 작성·수정',
};

export function permissionLabel(permission: string): string {
  return PERMISSION_LABELS[permission] ?? permission;
}
