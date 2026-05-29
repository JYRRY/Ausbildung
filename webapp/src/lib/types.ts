/** Mirrors jyry/webapp/schemas.py — keep in sync when the API changes. */

export type NotificationMode = "per_send" | "daily" | "off";
export type Plan = "free" | "plus" | "pro" | "max";

export interface Subscription {
  plan: Plan;
  status: string;
  started_at: string | null;
  expires_at: string | null;
  emails_sent_today: number;
  daily_quota: number;
  auto_renew: boolean;
}

export interface Me {
  id: number;
  email: string | null;
  google_picture: string | null;
  full_name: string | null;
  gmail_address: string | null;
  has_app_password: boolean;
  telegram_id: number | null;
  telegram_linked: boolean;
  is_admin: boolean;
  is_active: boolean;
  onboarding_complete: boolean;
  notification_mode: NotificationMode | null;
  accepted_terms_at: string | null;
  accepted_paid_terms_at: string | null;
  trial_started_at: string | null;
  subscription: Subscription | null;
}

export interface Application {
  id: number;
  job_title: string | null;
  sent_at: string | null;
  status: string;
  error_message: string | null;
  created_at: string;
}

export interface ApplicationsPage {
  items: Application[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminUserRow {
  id: number;
  email: string | null;
  full_name: string | null;
  telegram_id: number | null;
  plan: Plan;
  is_active: boolean;
  is_admin: boolean;
  onboarding_complete: boolean;
  notification_mode: NotificationMode | null;
  created_at: string;
  last_seen_at: string | null;
  emails_sent_today: number;
  emails_sent_total: number;
}

export interface AdminUsersPage {
  items: AdminUserRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminStats {
  users_total: number;
  users_active: number;
  users_by_plan: Record<Plan, number>;
  emails_sent_today: number;
  emails_sent_total: number;
}
