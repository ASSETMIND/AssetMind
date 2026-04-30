import { authHandlers } from './handlers/auth';
import { stockHandlers } from './handlers/stock';

/**
 * [Handlers 통합]
 * 분리된 각 도메인별 핸들러들을 하나로 통합하여 export 합니다.
 */
export const handlers = [...authHandlers, ...stockHandlers];
