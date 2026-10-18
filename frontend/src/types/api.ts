/**
 * TypeScript types mirroring the SalesCompass AI backend schemas exactly.
 * See backend/app/auth/schemas.py, retrieval/api_schemas.py, generation/api_schemas.py
 */

// ── Auth ─────────────────────────────────────────────────────────────────────

export interface UserRegister {
  username: string;
  email: string;
  password: string;
  role?: string; // defaults to "user"
}

export interface UserLogin {
  username: string;
  password: string;
}

export type UserRole = 'ADMIN' | 'SALESMAN';
export type UserStatus = 'ACTIVE' | 'REVOKED';

export interface UserResponse {
  id: number;
  username: string;
  email: string;
  role: UserRole | string;
  status?: UserStatus | string;
}

// ── Search / Retrieval ───────────────────────────────────────────────────────

export interface SearchRequest {
  query: string;
  top_k?: number; // 1–100, default 5
  score_threshold?: number; // -1.0–1.0, default 0.0
  sku?: string | null;
  category?: string | null;
  manufacturer?: string | null;
  document_id?: number | null;
  conversation_id?: number | null;
}

export interface ChunkMetadata {
  sku: string | null;
  category: string | null;
  manufacturer: string | null;
  filename: string | null;
  page_number: number | null;
  sheet_name: string | null;
  row_number: number | null;
}

export interface RetrievedChunk {
  chunk_id: string | null;
  document_id: number | string | null;
  text: string;
  score: number;
  metadata: ChunkMetadata;
}

export interface SearchResponse {
  query: string;
  results: RetrievedChunk[];
  total_results: number;
}

// ── Ask / Generation ─────────────────────────────────────────────────────────

export interface SourceResponse {
  chunk_id: string | null;
  document_id: number | string | null;
  sku: string | null;
  filename: string | null;
}

export type SalesStage =
  | 'DISCOVERY'
  | 'PRODUCT_MATCHING'
  | 'DEAL_DISCUSSION'
  | 'DEAL_FINALIZED'
  | 'POST_SALE';

export type DealStatus = 'OPEN' | 'PROPOSED' | 'FINALIZED' | 'CANCELLED';

export interface CandidateProduct {
  sku: string;
  name: string;
  category?: string | null;
  manufacturer?: string | null;
  filename?: string | null;
  price?: string | null;
  snippet?: string | null;
}

export interface RecommendationItem {
  sku: string;
  name: string;
  category?: string | null;
  manufacturer?: string | null;
  type: 'cross_sell' | 'upsell';
  relevance_explanation: string;
  trade_off_note?: string | null;
  estimated_price?: string | null;
}

export interface RecommendationsPayload {
  finalised_deal?: {
    sku?: string | null;
    name?: string | null;
    quantity?: number | null;
    price?: string | null;
    finalized_at?: string | null;
  };
  cross_sells: RecommendationItem[];
  upsells: RecommendationItem[];
}

export interface SalesStateResponse {
  stage: SalesStage | string;
  product_category?: string | null;
  extracted_requirements: Record<string, any>;
  candidate_products: CandidateProduct[];
  selected_product?: CandidateProduct | null;
  agreed_quantity?: number | null;
  agreed_price?: string | null;
  deal_status: DealStatus | string;
  deal_finalized_at?: string | null;
  can_recommend_addons: boolean;
  recommendations?: RecommendationsPayload | null;
}

export interface AskResponse {
  query: string;
  answer: string;
  conversation_id: number;
  sources: SourceResponse[];
  sales_state?: SalesStateResponse | null;
  suggested_questions?: string[] | null;
}


// ── Upload ───────────────────────────────────────────────────────────────────

export interface IndexingError {
  chunk_id: string;
  error: string;
}

export interface UploadResponse {
  success: boolean;
  document_id: number;
  filename: string;
  chunks_created: number;
  chunks_indexed: number;
  chunks_index_failed: number;
  indexing_errors: IndexingError[];
}

// ── Admin ────────────────────────────────────────────────────────────────────

export interface AdminUserItem {
  id: number;
  username: string;
  email: string;
  role: UserRole | string;
  status: UserStatus | string;
  created_at: string | null;
  last_login: string | null;
}

export interface AdminUserListResponse {
  users: AdminUserItem[];
  total: number;
}

export interface QueryLog {
  id: number;
  user_id: number;
  query: string;
  timestamp: string; // ISO datetime string
}

// ── API errors ───────────────────────────────────────────────────────────────

export interface ApiError {
  detail: string;
}

// ── Conversations (Persisted in PostgreSQL) ─────────────────────────────────

export interface Conversation {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationMessageItem {
  id: number;
  role: MessageRole;
  content: string;
  sources?: SourceResponse[] | null;
  created_at: string;
}

export interface ConversationDetail {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ConversationMessageItem[];
  sales_state?: SalesStateResponse | null;
}


export type MessageRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  sources?: SourceResponse[];
  timestamp: Date;
  isError?: boolean;
}
