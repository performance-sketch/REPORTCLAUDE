export interface CampaignRow {
  campaign_id: string | null;
  campaign_name: string | null;
  spend: number;
  impressions: number;
  clicks: number;
  ctr: number | null;
  cpc: number | null;
  cpm: number | null;
  leads: number;
  purchases: number;
  conversion_value: number;
  roas: number | null;
}

export interface ProductRow {
  product_code: string | null;
  product_name: string | null;
  bookings_confirmed: number;
  revenue: number;
  avg_ticket: number | null;
}

export interface DailyMetaRow {
  date: string;
  spend: number;
  impressions: number;
  clicks: number;
  leads: number;
  purchases: number;
  conversion_value: number;
}

export interface DailyBookingRow {
  date: string;
  bookings_created: number;
  bookings_confirmed: number;
  bookings_cancelled: number;
  gross_revenue: number;
}

export interface OverviewKPI {
  date_start: string;
  date_end: string;
  meta_spend: number;
  confirmed_revenue: number;
  roas_real: number | null;
  bookings_created: number;
  bookings_confirmed: number;
  bookings_cancelled: number;
  cancellation_rate: number | null;
  cac: number | null;
  avg_ticket: number | null;
  clicks: number;
  ctr: number | null;
  cpc: number | null;
  cpm: number | null;
  click_to_booking_rate: number | null;
  revenue_per_click: number | null;
  daily_meta: DailyMetaRow[];
  daily_bookings: DailyBookingRow[];
  top_campaigns: CampaignRow[];
  top_products: ProductRow[];
}

export interface MetaAdsKPI {
  date_start: string;
  date_end: string;
  spend: number;
  impressions: number;
  reach: number;
  frequency: number | null;
  clicks: number;
  link_clicks: number;
  landing_page_views: number;
  ctr: number | null;
  cpc: number | null;
  cpm: number | null;
  leads: number;
  purchases: number;
  conversion_value: number;
  cpa: number | null;
  roas_meta: number | null;
  campaigns: CampaignRow[];
}

export interface BookingsKPI {
  date_start: string;
  date_end: string;
  bookings_created: number;
  bookings_confirmed: number;
  bookings_cancelled: number;
  cancellation_rate: number | null;
  gross_revenue: number;
  net_revenue: number;
  avg_ticket: number | null;
  total_pax: number;
  daily: DailyBookingRow[];
  by_product: ProductRow[];
  by_status: { order_status: string; count: number; revenue: number }[];
}

export interface FunnelKPI {
  date_start: string;
  date_end: string;
  impressions: number;
  clicks: number;
  landing_page_views: number;
  bookings_created: number;
  bookings_confirmed: number;
  confirmed_revenue: number;
  imp_to_click_rate: number | null;
  click_to_booking_rate: number | null;
  booking_to_confirmed_rate: number | null;
  cost_per_booking_created: number | null;
  cost_per_booking_confirmed: number | null;
  revenue_per_click: number | null;
  roas_real: number | null;
  by_campaign: CampaignRow[];
}

export interface SyncRecord {
  source: string;
  sync_type: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  records_processed: number;
  records_failed: number;
  error_message: string | null;
}

export interface SyncHealth {
  pending_events: number;
  error_events: number;
  recent_syncs: SyncRecord[];
}
