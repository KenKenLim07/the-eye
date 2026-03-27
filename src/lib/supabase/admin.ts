import "server-only";

import { createClient } from "@supabase/supabase-js";

let _supabaseAdmin: ReturnType<typeof createClient> | null = null;

// Server-only admin client (service role). Never import this from client components.
// Lazy-init so builds don't fail in environments that don't set the service key.
export function getSupabaseAdmin() {
  if (_supabaseAdmin) return _supabaseAdmin;

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL as string | undefined;
  const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY as string | undefined;

  if (!supabaseUrl) {
    throw new Error("Missing NEXT_PUBLIC_SUPABASE_URL");
  }
  if (!supabaseServiceKey) {
    throw new Error("Missing SUPABASE_SERVICE_ROLE_KEY");
  }

  _supabaseAdmin = createClient(supabaseUrl, supabaseServiceKey, {
    auth: {
      persistSession: false,
      autoRefreshToken: false,
    },
  });

  return _supabaseAdmin;
}
