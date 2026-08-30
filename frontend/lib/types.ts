// API response types matching backend schemas

export interface ItemTags {
  colors: string[];
  primary_color?: string;
  pattern?: string;
  material?: string;
  style: string[];
  season: string[];
  formality?: string;
  fit?: string;
  occasion?: string[];
  brand?: string;
  condition?: string;
  features?: string[];
  logprobs_confidence?: number;
}

export type ItemMetadataField =
  | 'type'
  | 'subtype'
  | 'colors'
  | 'primary_color'
  | 'material'
  | 'pattern'
  | 'season'
  | 'formality'
  | 'style';

export interface ItemFieldMetadata {
  confidence?: number;
  provenance: 'auto' | 'user_edited' | 'user_confirmed';
  edited_at?: string;
  confirmed_at?: string;
}

export interface ItemMetadataUpdate {
  type: string;
  subtype?: string;
  primary_color?: string;
  tags: Partial<ItemTags>;
  confirm_fields: ItemMetadataField[];
}

export type ItemUpdateData = Omit<Partial<Item>, 'tags'> & {
  tags?: Partial<ItemTags>;
  confirm_fields?: ItemMetadataField[];
};

export interface Item {
  id: string;
  user_id: string;
  type: string;
  subtype?: string;
  name?: string;
  brand?: string;
  notes?: string;
  purchase_date?: string;
  purchase_price?: number;
  favorite: boolean;
  image_path: string;
  thumbnail_path?: string;
  medium_path?: string;
  original_image_path?: string | null;
  image_url?: string;
  thumbnail_url?: string;
  medium_url?: string;
  tags: ItemTags;
  colors: string[];
  primary_color?: string;
  pattern?: string;
  material?: string;
  style: string[];
  formality?: string;
  season: string[];
  status: 'processing' | 'ready' | 'error' | 'archived';
  ai_processed: boolean;
  ai_confidence?: number;
  field_metadata: Partial<Record<ItemMetadataField, ItemFieldMetadata>>;
  ai_description?: string;
  ai_error?: string | null;
  ai_started_at?: string | null;
  tagging_status: 'pending' | 'tagged';
  tagged_by?: 'auto' | 'manual' | null;
  tagged_at?: string | null;
  wear_count: number;
  last_worn_at?: string;
  last_suggested_at?: string;
  suggestion_count: number;
  acceptance_count: number;
  wears_since_wash: number;
  last_washed_at?: string;
  wash_interval?: number;
  needs_wash: boolean;
  effective_wash_interval: number;
  additional_images: ItemImage[];
  gallery_images?: ItemGalleryImage[];
  is_archived: boolean;
  archived_at?: string;
  archive_reason?: string;
  created_at: string;
  updated_at: string;
  background_removal?: BackgroundRemovalMetadata | null;
}

export interface ItemGalleryImage {
  id: string;
  source_item_id: string;
  image_path: string;
  thumbnail_path?: string;
  medium_path?: string;
  is_primary: boolean;
  position: number;
  created_at: string;
  image_url: string;
  thumbnail_url?: string;
  medium_url?: string;
}

export interface DuplicateMatchItem {
  id: string;
  type: string;
  name?: string;
  image_path: string;
  thumbnail_path?: string;
  image_url: string;
  thumbnail_url?: string;
  created_at: string;
}

export interface DuplicateMatch {
  id: string;
  item_low_id: string;
  item_high_id: string;
  status: 'pending' | 'merged' | 'kept_separate';
  canonical_item_id: string | null;
  cosine_score: number | null;
  matcher_revision: string;
  evidence: Record<string, unknown>;
  decided_at?: string | null;
  created_at: string;
  updated_at: string;
  item_low: DuplicateMatchItem;
  item_high: DuplicateMatchItem;
}

export interface BackgroundRemovalMetadata {
  outcome: 'accepted' | 'low_quality' | 'unsupported' | 'failed';
  mode: 'scene' | 'garment';
  provider?: string | null;
  provider_version?: string | null;
  model?: string | null;
  garment_category?: 'upper' | 'lower' | 'full' | null;
  transparent_path?: string | null;
  warning?: string | null;
  metrics: Record<string, number>;
}

export interface RemoveBackgroundResponse extends Item {
  background_removal: BackgroundRemovalMetadata;
}

export interface ItemListResponse {
  items: Item[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface TaggingProgress {
  processing: number;
  queued: number;
  analyzing: number;
  failed: number;
  completed: number;
  total: number;
}

export interface ItemFilter {
  type?: string;
  subtype?: string;
  colors?: string[];
  status?: string;
  favorite?: boolean;
  needs_wash?: boolean;
  is_archived?: boolean;
  search?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  ids?: string;
}

export interface StyleProfile {
  casual: number;
  formal: number;
  sporty: number;
  minimalist: number;
  bold: number;
}

export interface AIEndpoint {
  name: string;
  url: string;
  vision_model: string;
  text_model: string;
  enabled: boolean;
}

export interface Preferences {
  color_favorites: string[];
  color_avoid: string[];
  style_profile: StyleProfile;
  default_occasion: string;
  temperature_unit: 'celsius' | 'fahrenheit';
  temperature_sensitivity: 'low' | 'normal' | 'high';
  cold_threshold: number;
  hot_threshold: number;
  layering_preference: 'minimal' | 'moderate' | 'heavy';
  avoid_repeat_days: number;
  prefer_underused_items: boolean;
  variety_level: 'low' | 'moderate' | 'high';
  ai_endpoints: AIEndpoint[];
}

// Color options for the app
// Hex values tuned for typical clothing colors, not pure/saturated colors
export const CLOTHING_COLORS = [
  { name: 'Black', value: 'black', hex: '#1a1a1a' },
  { name: 'Charcoal', value: 'charcoal', hex: '#36454F' },
  { name: 'Gray', value: 'gray', hex: '#808080' },
  { name: 'White', value: 'white', hex: '#FAFAFA' },
  { name: 'Cream', value: 'cream', hex: '#F5F5DC' },
  { name: 'Beige', value: 'beige', hex: '#D4C4A8' },
  { name: 'Tan', value: 'tan', hex: '#C9B896' },
  { name: 'Khaki', value: 'khaki', hex: '#A89F6B' },
  { name: 'Olive', value: 'olive', hex: '#707B52' },
  { name: 'Army Green', value: 'army-green', hex: '#5B6340' },
  { name: 'Green', value: 'green', hex: '#4A7C59' },
  { name: 'Teal', value: 'teal', hex: '#367588' },
  { name: 'Navy', value: 'navy', hex: '#1B2A4A' },
  { name: 'Blue', value: 'blue', hex: '#4A7DB8' },
  { name: 'Brown', value: 'brown', hex: '#8B5A3C' },
  { name: 'Dark Brown', value: 'dark-brown', hex: '#5C4033' },
  { name: 'Burgundy', value: 'burgundy', hex: '#722F37' },
  { name: 'Red', value: 'red', hex: '#C44536' },
  { name: 'Pink', value: 'pink', hex: '#E8A0B0' },
  { name: 'Purple', value: 'purple', hex: '#6B5B7A' },
  { name: 'Yellow', value: 'yellow', hex: '#D4A84B' },
  { name: 'Orange', value: 'orange', hex: '#D2691E' },
] as const;

// Clothing types (alphabetized by label). Must match the TYPE vocabulary set in
// clothing_analysis.txt, order carries no meaning there.
export const CLOTHING_TYPES = [
  { label: 'Accessories', value: 'accessories' },
  { label: 'Bag', value: 'bag' },
  { label: 'Belt', value: 'belt' },
  { label: 'Blazer', value: 'blazer' },
  { label: 'Blouse', value: 'blouse' },
  { label: 'Boots', value: 'boots' },
  { label: 'Cardigan', value: 'cardigan' },
  { label: 'Coat', value: 'coat' },
  { label: 'Dress', value: 'dress' },
  { label: 'Hat', value: 'hat' },
  { label: 'Hoodie', value: 'hoodie' },
  { label: 'Jacket', value: 'jacket' },
  { label: 'Jeans', value: 'jeans' },
  { label: 'Jumpsuit', value: 'jumpsuit' },
  { label: 'Pants', value: 'pants' },
  { label: 'Polo', value: 'polo' },
  { label: 'Sandals', value: 'sandals' },
  { label: 'Scarf', value: 'scarf' },
  { label: 'Shirt', value: 'shirt' },
  { label: 'Shoes', value: 'shoes' },
  { label: 'Shorts', value: 'shorts' },
  { label: 'Skirt', value: 'skirt' },
  { label: 'Sneakers', value: 'sneakers' },
  { label: 'Socks', value: 'socks' },
  { label: 'Suit', value: 'suit' },
  { label: 'Sweater', value: 'sweater' },
  { label: 'T-Shirt', value: 't-shirt' },
  { label: 'Tank Top', value: 'tank-top' },
  { label: 'Tie', value: 'tie' },
  { label: 'Top', value: 'top' },
  { label: 'Vest', value: 'vest' },
] as const;

export const OCCASIONS = [
  { label: 'Casual', value: 'casual' },
  { label: 'Office', value: 'office' },
  { label: 'Formal', value: 'formal' },
  { label: 'Date', value: 'date' },
  { label: 'Sporty', value: 'sporty' },
  { label: 'Outdoor', value: 'outdoor' },
] as const;

// Family types
export interface FamilyMember {
  id: string;
  display_name: string;
  email: string;
  avatar_url?: string;
  role: 'admin' | 'member';
  created_at: string;  // When user joined the family
}

export interface PendingInvite {
  id: string;
  email: string;
  created_at: string;  // When invite was sent
  expires_at: string;
}

export interface Family {
  id: string;
  name: string;
  invite_code: string;
  members: FamilyMember[];
  pending_invites: PendingInvite[];
  created_at: string;
}

export interface FamilyCreateResponse {
  id: string;
  name: string;
  invite_code: string;
  role: string;
}

export interface JoinFamilyResponse {
  family_id: string;
  family_name: string;
  role: string;
}

// Multi-image types
export interface ItemImage {
  id: string;
  item_id: string;
  image_path: string;
  thumbnail_path?: string;
  medium_path?: string;
  position: number;
  created_at: string;
  image_url: string;
  thumbnail_url?: string;
  medium_url?: string;
}

// Wash tracking types
export interface WashHistoryEntry {
  id: string;
  item_id: string;
  washed_at: string;
  method?: string;
  notes?: string;
  created_at: string;
}

// Family rating types
export interface FamilyRating {
  id: string;
  user_id: string;
  user_display_name: string;
  user_avatar_url?: string;
  rating: number;
  comment?: string;
  created_at: string;
}

// Outfit types
export interface OutfitItem {
  id: string;
  type: string;
  subtype?: string;
  name?: string;
  primary_color?: string;
  colors: string[];
  image_path: string;
  thumbnail_path?: string;
  image_url?: string;
  thumbnail_url?: string;
  transparent_url?: string | null;
  layer_type?: string;
  position: number;
}

export interface WeatherData {
  temperature: number;
  feels_like: number;
  humidity: number;
  precipitation_chance: number;
  condition: string;
}

export interface FeedbackSummary {
  rating?: number;
  comment?: string;
  worn_at?: string;
}

export type OutfitSource = 'scheduled' | 'on_demand' | 'manual' | 'pairing' | 'external';

export interface Outfit {
  id: string;
  replaces_outfit_id?: string | null;
  refined_from_outfit_id?: string | null;
  occasion: string;
  target_style?: string | null;
  scheduled_for: string;
  status: 'pending' | 'sent' | 'viewed' | 'accepted' | 'rejected' | 'skipped' | 'expired';
  source: OutfitSource;
  reasoning?: string | null;
  style_notes?: string | null;
  season?: string | null;
  formality?: string | null;
  palette?: string[] | null;
  notes?: string | null;
  highlights?: string[] | null;
  weather?: WeatherData | null;
  generation_context?: OutfitGenerationContext | null;
  items: OutfitItem[];
  feedback?: FeedbackSummary | null;
  family_ratings?: FamilyRating[] | null;
  family_rating_average?: number | null;
  family_rating_count?: number | null;
  created_at: string;
}

export interface SuggestRequest {
  occasion: string;
  weather_override?: {
    temperature: number;
    feels_like?: number;
    humidity: number;
    precipitation_chance: number;
    condition: string;
  };
  exclude_items?: string[];
  include_items?: string[];
}

export interface StyleBatchRequest {
  target_style: string;
  count: number;
  occasion: string;
  scheduled_for?: string;
  time_of_day?: 'morning' | 'afternoon' | 'evening' | 'night' | 'full day' | null;
  activity?: string | null;
  constraints?: {
    required_item_ids: string[];
    excluded_item_ids: string[];
    avoided_colors: string[];
    note: string | null;
  };
}

export interface OutfitGenerationContext {
  time_of_day?: string | null;
  activity?: string | null;
  constraints?: {
    required_item_ids?: string[];
    excluded_item_ids?: string[];
    avoided_colors?: string[];
    note?: string | null;
  };
  applied_preferences?: Record<string, unknown>;
  refinement?: {
    instruction: string;
    turn: number;
    root_outfit_id: string;
    parent_outfit_id: string;
  };
}

export interface StyleBatchResponse {
  outfits: Outfit[];
  model?: string | null;
}

// Pairing types
export interface SourceItem {
  id: string;
  type: string;
  subtype?: string;
  name?: string;
  primary_color?: string;
  image_path: string;
  thumbnail_path?: string;
  image_url?: string;
  thumbnail_url?: string;
}

export interface Pairing extends Outfit {
  source_item?: SourceItem;
}

export interface PairingListResponse {
  pairings: Pairing[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface GeneratePairingsRequest {
  num_pairings: number;
}

export interface GeneratePairingsResponse {
  generated: number;
  pairings: Pairing[];
}
